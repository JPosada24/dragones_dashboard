"""Avisos a familias y al staff: bandeja en la plataforma, correo automático y WhatsApp con un clic.

Los avisos se generan aquí (por evento o por el worker) y se envían aparte: un correo caído nunca rompe
la operación que lo originó. Cada aviso tiene una `clave` única, así que generarlo dos veces no lo duplica.
"""
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.config import get_settings
from app.core.correo import Correo
from app.core.fechas import formato_fecha, formato_pesos
from app.models.acceso import Rol, Usuario
from app.models.alumnos import Alumno, Inscripcion
from app.models.asistencia import Justificacion, Multa
from app.models.notificaciones import Notificacion
from app.services import alumnos, auditoria, configuracion
from app.services.errores import Conflicto, NoEncontrado

MAX_INTENTOS_CORREO = 5
# Tipos que además se ofrecen para enviar por WhatsApp (lo más importante; el resto va por correo y bandeja).
TIPOS_WHATSAPP = {"recordatorio_inscripcion", "inscripcion_vencida", "multa", "aviso_mora", "mora"}


@dataclass(frozen=True)
class Destinatario:
    nombre: str
    usuario_id: uuid.UUID | None
    email: str | None
    telefono: str | None


# ---------- A quién se avisa ----------
def destinatarios_de_alumno(db: Session, alumno: Alumno) -> list[Destinatario]:
    """Los acudientes y, si es mayor de edad, el propio alumno. Se omite a quien no tiene ningún canal."""
    personas = [(v.acudiente.nombres, v.acudiente.usuario_id, v.acudiente.email, v.acudiente.telefono)
                for v in alumno.vinculos]
    if not alumnos.es_menor(db, alumno.fecha_nacimiento):
        personas.append((alumno.nombres, alumno.usuario_id, alumno.email, alumno.telefono))
    vistos, resultado = set(), []
    for nombre, usuario_id, email, telefono in personas:
        if email is None and usuario_id is not None:
            cuenta = db.get(Usuario, usuario_id)
            email = cuenta.email if cuenta else None
        destino = Destinatario(nombre, usuario_id, email, telefono)
        llave = (usuario_id, email, telefono)
        if llave in vistos or not any(llave):
            continue
        vistos.add(llave)
        resultado.append(destino)
    return resultado


def staff_de_rama(db: Session, rama: str) -> list[Destinatario]:
    """SuperAdmin y Admin activos, más los entrenadores de esa rama. Solo bandeja y correo."""
    filas = db.scalars(select(Usuario).join(Usuario.rol).where(
        Usuario.activo.is_(True),
        or_(Rol.codigo.in_(("SUPERADMIN", "ADMIN")), (Rol.codigo == "ENTRENADOR") & (Usuario.rama == rama)),
    ))
    return [Destinatario(u.nombre, u.id, u.email, None) for u in filas]


# ---------- Crear avisos ----------
def avisar(
    db: Session, destinatarios: list[Destinatario], *, tipo: str, clave: str, titulo: str, mensaje: str,
    alumno_id: uuid.UUID | None = None,
) -> int:
    """Crea un aviso por destinatario (idempotente por `clave`). Devuelve cuántos son nuevos."""
    club = get_settings().club_nombre
    nuevos = 0
    for d in destinatarios:
        quien = d.usuario_id or d.email or d.telefono
        whatsapp = "pendiente" if (tipo in TIPOS_WHATSAPP and d.telefono) else "no_aplica"
        if d.usuario_id is None and d.email is None and whatsapp == "no_aplica":
            continue  # no hay por dónde entregárselo
        fila = {
            "id": uuid.uuid4(), "clave": f"{clave}:{quien}"[:200], "tipo": tipo, "titulo": titulo[:150],
            "mensaje": f"Hola {d.nombre}. {mensaje}\n\n— {club}"[:1000], "alumno_id": alumno_id,
            "usuario_id": d.usuario_id, "email_destino": d.email,
            "email_estado": "pendiente" if d.email else "no_aplica", "email_intentos": 0,
            "telefono_destino": d.telefono, "whatsapp_estado": whatsapp,
        }
        # ON CONFLICT DO NOTHING: si ya existe ese aviso para esa persona, no se repite (ni falla la transacción).
        # RETURNING devuelve solo las filas realmente insertadas (rowcount no es fiable aquí).
        sentencia = insert(Notificacion).values(**fila).on_conflict_do_nothing(index_elements=["clave"])
        nuevos += len(db.execute(sentencia.returning(Notificacion.id)).all())
    return nuevos


def _alumno(db: Session, alumno_id: uuid.UUID) -> Alumno:
    return db.get(Alumno, alumno_id)


def multa_generada(db: Session, multa: Multa) -> None:
    alumno = _alumno(db, multa.alumno_id)
    plazo = multa.sesion.fecha + timedelta(days=configuracion.obtener(db, "dias_para_justificar"))
    avisar(
        db, destinatarios_de_alumno(db, alumno), tipo="multa", clave=f"multa:{multa.id}", alumno_id=alumno.id,
        titulo="Multa por inasistencia",
        mensaje=(f"{alumno.nombres} no asistió ni justificó la sesión del {formato_fecha(multa.sesion.fecha)}. "
                 f"Se generó una multa de {formato_pesos(multa.valor)}. Si hubo un motivo, puedes justificarla "
                 f"hasta el {formato_fecha(plazo)}."),
    )


def justificacion_revisada(db: Session, j: Justificacion) -> None:
    alumno = _alumno(db, j.alumno_id)
    aprobada = j.estado == "aprobada"
    detalle = "Queda como asistencia justificada." if aprobada else f"Motivo: {j.comentario}."
    avisar(
        db, destinatarios_de_alumno(db, alumno), tipo="justificacion", clave=f"justificacion:{j.id}",
        alumno_id=alumno.id, titulo=f"Justificación {'aprobada' if aprobada else 'rechazada'}",
        mensaje=(f"La justificación de {alumno.nombres} para la sesión del {formato_fecha(j.sesion.fecha)} fue "
                 f"{'aprobada' if aprobada else 'rechazada'}. {detalle}"),
    )


def inscripcion_vencida(db: Session, i: Inscripcion) -> None:
    alumno = _alumno(db, i.alumno_id)
    avisar(
        db, destinatarios_de_alumno(db, alumno), tipo="inscripcion_vencida", clave=f"inscripcion_vencida:{i.id}",
        alumno_id=alumno.id, titulo="Inscripción vencida",
        mensaje=(f"La inscripción de {alumno.nombres} fue rechazada porque el plazo de pago terminó el "
                 f"{formato_fecha(i.fecha_limite_pago)} con un saldo de {formato_pesos(i.saldo)}. "
                 "Comunícate con el club si necesitas una prórroga."),
    )


# ---------- Avisos programados (los genera el worker) ----------
def recordatorios_inscripcion(db: Session) -> int:
    """Recuerda el pago X días antes del vencimiento ("recordatorios_dias_antes", p. ej. [7, 1]).

    Se usa el umbral más cercano que ya aplica: si el worker estuvo apagado, se pone al día sin mandar dos a la vez.
    La clave incluye la fecha límite: tras una prórroga vuelven a salir los recordatorios.
    """
    dias = sorted(configuracion.obtener(db, "recordatorios_dias_antes"))
    if not dias:
        return 0
    hoy = fechas.hoy()
    nuevos = 0
    pendientes = db.scalars(select(Inscripcion).where(
        Inscripcion.estado == "pendiente_pago", Inscripcion.fecha_limite_pago >= hoy,
        Inscripcion.fecha_limite_pago <= hoy + timedelta(days=dias[-1]),
    )).unique()
    for i in pendientes:
        if i.saldo <= 0:
            continue
        faltan = (i.fecha_limite_pago - hoy).days
        umbral = next((d for d in dias if faltan <= d), None)
        if umbral is None:
            continue
        cuando = "hoy" if faltan == 0 else ("mañana" if faltan == 1 else f"en {faltan} días")
        alumno = i.alumno
        nuevos += avisar(
            db, destinatarios_de_alumno(db, alumno), tipo="recordatorio_inscripcion", alumno_id=alumno.id,
            clave=f"recordatorio_inscripcion:{i.id}:{i.fecha_limite_pago.isoformat()}:{umbral}",
            titulo="Recordatorio: pago de inscripción",
            mensaje=(f"Te recordamos que la inscripción de {alumno.nombres} vence {cuando} "
                     f"({formato_fecha(i.fecha_limite_pago)}). Saldo pendiente: {formato_pesos(i.saldo)}."),
        )
    return nuevos


def alertas_inasistencia(db: Session) -> int:
    """Avisa al staff una vez por racha de inasistencias seguidas."""
    from app.services import asistencia  # import local: asistencia también usa este módulo

    nuevos = 0
    for a in asistencia.alertas(db, None):
        nuevos += avisar(
            db, staff_de_rama(db, a.alumno.rama), tipo="alerta_inasistencia", alumno_id=a.alumno.id,
            clave=f"alerta_inasistencia:{a.alumno.id}:{a.desde.isoformat()}",
            titulo="Alerta de inasistencias",
            mensaje=(f"{a.alumno.nombres} {a.alumno.apellidos} (rama {a.alumno.rama}) acumula "
                     f"{a.inasistencias_seguidas} inasistencias seguidas sin justificar, desde el "
                     f"{formato_fecha(a.desde)}."),
        )
    return nuevos


# ---------- Envío de correos (worker) ----------
def enviar_correos(db: Session, correo: Correo, *, ahora: datetime, lote: int = 50) -> tuple[int, int]:
    """Envía los correos pendientes. Un fallo se reintenta con espera creciente; tras 5 intentos queda "fallido"."""
    filas = db.scalars(
        select(Notificacion)
        .where(Notificacion.email_estado == "pendiente",
               or_(Notificacion.email_proximo_intento.is_(None), Notificacion.email_proximo_intento <= ahora))
        .order_by(Notificacion.creado_en).limit(lote)
        .with_for_update(skip_locked=True)
    ).all()
    asunto_club = get_settings().club_nombre
    enviados = fallidos = 0
    for n in filas:
        try:
            correo.enviar(n.email_destino, f"[{asunto_club}] {n.titulo}", n.mensaje)
        except Exception as e:  # noqa: BLE001  (cualquier error del proveedor se registra y se reintenta)
            n.email_intentos += 1
            n.email_error = f"{type(e).__name__}: {e}"[:255]
            if n.email_intentos >= MAX_INTENTOS_CORREO:
                n.email_estado = "fallido"
                fallidos += 1
            else:
                n.email_proximo_intento = ahora + timedelta(minutes=2 ** n.email_intentos)
        else:
            n.email_estado, n.email_enviado_en, n.email_error = "enviado", ahora, None
            enviados += 1
    db.flush()
    return enviados, fallidos


# ---------- Bandeja ----------
def mias(db: Session, usuario: Usuario, *, solo_no_leidas: bool, limit: int) -> list[Notificacion]:
    q = select(Notificacion).where(Notificacion.usuario_id == usuario.id)
    if solo_no_leidas:
        q = q.where(Notificacion.leida_en.is_(None))
    return list(db.scalars(q.order_by(Notificacion.creado_en.desc()).limit(limit)))


def marcar_leida(db: Session, usuario: Usuario, notificacion_id: uuid.UUID) -> Notificacion:
    n = db.get(Notificacion, notificacion_id)
    if n is None or n.usuario_id != usuario.id:  # solo las propias; las ajenas "no existen"
        raise NoEncontrado("Notificación no encontrada.")
    if n.leida_en is None:
        n.leida_en = fechas.ahora()
    return n


def marcar_todas_leidas(db: Session, usuario: Usuario) -> int:
    filas = mias(db, usuario, solo_no_leidas=True, limit=1000)
    for n in filas:
        n.leida_en = fechas.ahora()
    return len(filas)


# ---------- WhatsApp (manual con enlace) ----------
def enlace_whatsapp(telefono: str, texto: str) -> str:
    """Enlace wa.me que abre WhatsApp con el mensaje escrito. Números colombianos de 10 dígitos llevan el 57."""
    digitos = re.sub(r"\D", "", telefono)
    if not telefono.startswith("+") and len(digitos) == 10 and digitos.startswith("3"):
        digitos = "57" + digitos
    return f"https://wa.me/{digitos}?text={quote(texto)}"


def cola_whatsapp(db: Session, *, limit: int) -> list[Notificacion]:
    return list(db.scalars(
        select(Notificacion).where(Notificacion.whatsapp_estado == "pendiente")
        .order_by(Notificacion.creado_en).limit(limit)
    ))


def marcar_whatsapp(
    db: Session, notificacion_id: uuid.UUID, *, accion: str, actor: Usuario, ip: str | None
) -> Notificacion:
    n = db.get(Notificacion, notificacion_id)
    if n is None:
        raise NoEncontrado("Notificación no encontrada.")
    if n.whatsapp_estado != "pendiente":
        raise Conflicto("Ese aviso no está pendiente de WhatsApp.")
    n.whatsapp_estado = accion
    n.whatsapp_marcado_por, n.whatsapp_marcado_en = actor.id, fechas.ahora()
    auditoria.registrar(
        db, accion=f"notificacion.whatsapp_{accion}", entidad="notificacion", entidad_id=str(n.id),
        usuario_id=actor.id, ip=ip,
    )
    return n
