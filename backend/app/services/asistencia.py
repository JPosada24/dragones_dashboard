"""Sesiones de entrenamiento, asistencia, justificaciones y cierre diario (ausencias y multas)."""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import ColumnElement, false, or_, select, true
from sqlalchemy.orm import Session

from app.core import fechas
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, Inscripcion
from app.models.asistencia import Asistencia, Justificacion, Multa, Sesion
from app.models.dominio import ESTADOS_VIGENTES
from app.services import alumnos, auditoria, configuracion, multas, notificaciones
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado, Prohibido

def _auditar(db: Session, accion: str, entidad: str, entidad_id, actor_id, ip, **extra) -> None:
    auditoria.registrar(
        db, accion=accion, entidad=entidad, entidad_id=str(entidad_id), usuario_id=actor_id, ip=ip, **extra,
    )


def _hhmm(t: time) -> str:
    return t.strftime("%H:%M")


def momento_cierre(db: Session, sesion: Sesion) -> datetime:
    return fechas.en_zona(sesion.fecha, time.fromisoformat(configuracion.obtener(db, "hora_cierre_asistencia")))


# ---------- Visibilidad ----------
VER_SESIONES = ("alumnos.ver_todos", "alumnos.ver_rama", "alumnos.ver_propios")


def filtro_sesiones_visibles(usuario: Usuario) -> ColumnElement[bool]:
    """El entrenamiento es general: lo ve cualquiera que pueda ver alumnos. Las filas de la planilla sí se
    limitan (Entrenador: su rama; Miembro: los suyos)."""
    return true() if set(usuario.permisos_codigos) & set(VER_SESIONES) else false()


def obtener_visible(db: Session, usuario: Usuario, sesion_id: uuid.UUID) -> Sesion:
    sesion = db.scalar(select(Sesion).where(Sesion.id == sesion_id, filtro_sesiones_visibles(usuario)))
    if sesion is None:
        raise NoEncontrado("Sesión no encontrada.")
    return sesion


def listar(
    db: Session, usuario: Usuario, *, desde: date | None, hasta: date | None, skip: int, limit: int
) -> list[Sesion]:
    q = select(Sesion).where(filtro_sesiones_visibles(usuario))
    if desde:
        q = q.where(Sesion.fecha >= desde)
    if hasta:
        q = q.where(Sesion.fecha <= hasta)
    return list(db.scalars(q.order_by(Sesion.fecha, Sesion.hora_inicio).offset(skip).limit(limit)))


def esperados(db: Session, sesion: Sesion) -> list[Alumno]:
    """Alumnos que deben asistir (ambas ramas): activos, con inscripción vigente desde antes de la sesión."""
    return list(db.scalars(
        select(Alumno).join(Inscripcion, Inscripcion.alumno_id == Alumno.id).where(
            Alumno.activo.is_(True),
            Inscripcion.anio == sesion.fecha.year, Inscripcion.estado.in_(ESTADOS_VIGENTES),
            Inscripcion.fecha_inscripcion <= sesion.fecha,
        ).order_by(Alumno.apellidos, Alumno.nombres)
    ))


def esperados_visibles(db: Session, usuario: Usuario, sesion: Sesion) -> list[Alumno]:
    """Los esperados que este usuario puede ver: todos (Admin/SA), su rama (Entrenador) o los suyos (Miembro)."""
    visibles = set(db.scalars(select(Alumno.id).where(alumnos.filtro_visibles(usuario))))
    return [a for a in esperados(db, sesion) if a.id in visibles]


def _esperado(db: Session, sesion: Sesion, alumno_id: uuid.UUID) -> Alumno:
    alumno = next((a for a in esperados(db, sesion) if a.id == alumno_id), None)
    if alumno is None:
        raise ErrorNegocio("El alumno no tiene una inscripción vigente para esta sesión.")
    return alumno


def _asistencia(db: Session, sesion_id: uuid.UUID, alumno_id: uuid.UUID) -> Asistencia | None:
    return db.scalar(select(Asistencia).where(Asistencia.sesion_id == sesion_id, Asistencia.alumno_id == alumno_id))


def _justificacion_viva(db: Session, sesion_id: uuid.UUID, alumno_id: uuid.UUID) -> Justificacion | None:
    return db.scalar(select(Justificacion).where(
        Justificacion.sesion_id == sesion_id, Justificacion.alumno_id == alumno_id,
        Justificacion.estado.in_(("pendiente", "aprobada")),
    ))


def _fijar_asistencia(
    db: Session, sesion: Sesion, alumno_id: uuid.UUID, estado: str, origen: str, actor_id: uuid.UUID | None
) -> Asistencia:
    fila = _asistencia(db, sesion.id, alumno_id)
    if fila is None:
        fila = Asistencia(sesion_id=sesion.id, alumno_id=alumno_id, estado=estado, origen=origen, marcado_por=actor_id)
        db.add(fila)
    else:
        fila.estado, fila.origen, fila.marcado_por = estado, origen, actor_id
    db.flush()
    return fila


def _verificar_abierta(sesion: Sesion) -> None:
    if sesion.cancelada:
        raise ErrorNegocio("La sesión fue cancelada.")
    if sesion.cerrada_en is not None:
        raise ErrorNegocio("La asistencia de esta sesión ya se cerró; para cambiarla usa la corrección.")


# ---------- Sesiones extra y cancelación ----------
def crear_extra(
    db: Session, *, fecha: date, hora_inicio: time, hora_fin: time, lugar: str | None, actor: Usuario, ip: str | None,
) -> Sesion:
    """Una sesión fuera del horario semanal (p. ej. para reponer un festivo)."""
    if hora_fin <= hora_inicio:
        raise ErrorNegocio("La hora de fin debe ser posterior a la de inicio.")
    if fecha < fechas.hoy():
        raise ErrorNegocio("No se pueden crear sesiones en fechas pasadas.")
    if db.scalar(select(Sesion.id).where(Sesion.fecha == fecha, Sesion.hora_inicio == hora_inicio)):
        raise Conflicto("Ya hay una sesión ese día a esa hora.")
    sesion = Sesion(fecha=fecha, hora_inicio=hora_inicio, hora_fin=hora_fin, lugar=lugar, creado_por=actor.id)
    db.add(sesion)
    db.flush()
    _auditar(
        db, "sesion.crear", "sesion", sesion.id, actor.id, ip,
        despues={"fecha": fecha.isoformat(), "hora_inicio": _hhmm(hora_inicio), "hora_fin": _hhmm(hora_fin)},
    )
    return sesion


def cancelar(db: Session, sesion: Sesion, *, motivo: str, actor: Usuario, ip: str | None) -> Sesion:
    """Cancelación a mano (otro evento del club). Festivos y torneos los cancela la programación automática."""
    if sesion.cancelada:
        raise Conflicto("La sesión ya estaba cancelada.")
    sesion.cancelada, sesion.causa_cancelacion, sesion.motivo_cancelacion = True, "manual", motivo
    # Si ya se había cerrado, las multas pendientes de esa sesión dejan de tener sentido.
    for multa in db.scalars(select(Multa).where(Multa.sesion_id == sesion.id, Multa.estado == "pendiente")):
        multas.anular_si_pendiente(
            db, sesion.id, multa.alumno_id, motivo=f"Sesión cancelada: {motivo}", actor_id=actor.id, ip=ip
        )
    db.flush()
    _auditar(db, "sesion.cancelar", "sesion", sesion.id, actor.id, ip, despues={"motivo": motivo})
    return sesion


def reactivar(db: Session, sesion: Sesion, *, actor: Usuario, ip: str | None) -> Sesion:
    """Deshace una cancelación (hecha por error, o para entrenar un festivo).

    Solo antes del cierre de esa sesión: después, el cierre multaría a todos sin haber podido marcar.
    Las de torneo o cambio de horario no: la programación automática las volvería a cancelar.
    """
    if not sesion.cancelada:
        raise Conflicto("La sesión no está cancelada.")
    if sesion.causa_cancelacion == "torneo":
        raise ErrorNegocio("Esta sesión se canceló por un torneo: cancela el torneo o crea una sesión extra.")
    if sesion.causa_cancelacion == "horario":
        raise ErrorNegocio("Ese día ya no está en el horario de entrenamiento: crea una sesión extra.")
    if sesion.cerrada_en is not None or fechas.ahora() >= momento_cierre(db, sesion):
        raise ErrorNegocio("Ya pasó el cierre de esa sesión: no se puede reactivar.")
    antes = {"causa": sesion.causa_cancelacion, "motivo": sesion.motivo_cancelacion}
    sesion.cancelada, sesion.causa_cancelacion, sesion.motivo_cancelacion = False, None, None
    db.flush()
    _auditar(db, "sesion.reactivar", "sesion", sesion.id, actor.id, ip, antes=antes)
    return sesion


# ---------- Planilla ----------
@dataclass
class FilaPlanilla:
    alumno: Alumno
    asistencia: str | None
    justificacion: str | None
    multa: str | None


def planilla(db: Session, usuario: Usuario, sesion: Sesion) -> list[FilaPlanilla]:
    """Estado de cada alumno esperado que el usuario puede ver (Entrenador: su rama; Miembro: los suyos)."""
    lista = esperados_visibles(db, usuario, sesion)
    asistencias = {a.alumno_id: a.estado for a in db.scalars(select(Asistencia).where(Asistencia.sesion_id == sesion.id))}
    justificaciones: dict[uuid.UUID, str] = {}
    for j in db.scalars(select(Justificacion).where(Justificacion.sesion_id == sesion.id).order_by(Justificacion.creado_en)):
        justificaciones[j.alumno_id] = j.estado  # queda la más reciente
    multas_ = {
        m.alumno_id: m.estado
        for m in db.scalars(select(Multa).where(Multa.sesion_id == sesion.id, Multa.estado != "anulada"))
    }
    return [FilaPlanilla(a, asistencias.get(a.id), justificaciones.get(a.id), multas_.get(a.id)) for a in lista]


# ---------- Marcar asistencia ----------
def marcar_grupo(
    db: Session, sesion: Sesion, *, marcas: list[tuple[uuid.UUID, str]], actor: Usuario, ip: str | None
) -> None:
    _verificar_abierta(sesion)
    if sesion.fecha > fechas.hoy():
        raise ErrorNegocio("No se puede marcar la asistencia de una sesión futura.")
    ids = {a.id for a in esperados_visibles(db, actor, sesion)}  # el Entrenador, solo su rama
    ajenos = [str(alumno_id) for alumno_id, _ in marcas if alumno_id not in ids]
    if ajenos:
        raise ErrorNegocio(f"Estos alumnos no están en la planilla que puedes marcar: {', '.join(ajenos)}")
    for alumno_id, estado in marcas:
        _fijar_asistencia(db, sesion, alumno_id, estado, "grupo", actor.id)
    _auditar(
        db, "asistencia.marcar_grupo", "sesion", sesion.id, actor.id, ip,
        despues={"marcas": [{"alumno_id": str(a), "estado": e} for a, e in marcas]},
    )


def marcar_propia(db: Session, sesion: Sesion, *, alumno_id: uuid.UUID, actor: Usuario, ip: str | None) -> None:
    """El alumno (o su acudiente) marca "presente", solo el día de la sesión y en su horario."""
    if not alumnos.es_propio(db, actor, alumno_id):
        raise NoEncontrado("Alumno no encontrado.")
    _verificar_abierta(sesion)
    _esperado(db, sesion, alumno_id)
    antes = timedelta(minutes=configuracion.obtener(db, "minutos_marcar_antes"))
    inicio = fechas.en_zona(sesion.fecha, sesion.hora_inicio)
    fin = fechas.en_zona(sesion.fecha, sesion.hora_fin)
    if not (inicio - antes <= fechas.ahora() <= fin):
        raise ErrorNegocio(
            f"Solo puedes marcar tu asistencia el {fechas.formato_fecha(sesion.fecha)} entre las "
            f"{_hhmm((inicio - antes).time())} y las {_hhmm(sesion.hora_fin)}."
        )
    existente = _asistencia(db, sesion.id, alumno_id)
    if existente is not None and existente.origen != "propia":
        raise Conflicto("Tu asistencia ya la registró el entrenador.")
    if existente is not None:
        raise Conflicto("Ya marcaste tu asistencia.")
    _fijar_asistencia(db, sesion, alumno_id, "presente", "propia", actor.id)
    _auditar(db, "asistencia.marcar_propia", "sesion", sesion.id, actor.id, ip, despues={"alumno_id": str(alumno_id)})


def corregir(
    db: Session, sesion: Sesion, *, alumno_id: uuid.UUID, estado: str, motivo: str, actor: Usuario, ip: str | None
) -> None:
    """Cambia una asistencia ya cerrada y ajusta la multa en consecuencia."""
    if sesion.cancelada:
        raise ErrorNegocio("La sesión fue cancelada.")
    if sesion.cerrada_en is None:
        raise ErrorNegocio("La sesión aún no se ha cerrado: marca la asistencia normalmente.")
    if _asistencia(db, sesion.id, alumno_id) is None:
        _esperado(db, sesion, alumno_id)
    anterior = _asistencia(db, sesion.id, alumno_id)
    antes = anterior.estado if anterior else None
    _fijar_asistencia(db, sesion, alumno_id, estado, "correccion", actor.id)
    if estado == "ausente":
        multas.generar(db, sesion, alumno_id, actor_id=actor.id, ip=ip)
    else:
        multas.anular_si_pendiente(
            db, sesion.id, alumno_id, motivo=f"Corrección de asistencia: {motivo}", actor_id=actor.id, ip=ip
        )
    _auditar(
        db, "asistencia.corregir", "sesion", sesion.id, actor.id, ip,
        antes={"alumno_id": str(alumno_id), "estado": antes},
        despues={"alumno_id": str(alumno_id), "estado": estado, "motivo": motivo},
    )


# ---------- Justificaciones ----------
def justificar(
    db: Session, sesion: Sesion, *, alumno_id: uuid.UUID, motivo: str, actor: Usuario, ip: str | None
) -> Justificacion:
    staff = "asistencia.marcar_grupo" in actor.permisos_codigos
    if staff:
        alumnos.obtener_visible(db, actor, alumno_id)  # el Entrenador, solo de su rama
    elif not alumnos.es_propio(db, actor, alumno_id):
        raise NoEncontrado("Alumno no encontrado.")
    if sesion.cancelada:
        raise ErrorNegocio("La sesión fue cancelada: no hace falta justificar.")
    _esperado(db, sesion, alumno_id)
    if not staff:
        plazo = sesion.fecha + timedelta(days=configuracion.obtener(db, "dias_para_justificar"))
        if fechas.hoy() > plazo:
            raise ErrorNegocio(
                f"El plazo para justificar esta sesión venció el {fechas.formato_fecha(plazo)}. Habla con el entrenador."
            )
    asistencia = _asistencia(db, sesion.id, alumno_id)
    if asistencia is not None and asistencia.estado == "presente":
        raise Conflicto("El alumno ya está marcado como presente en esta sesión.")
    if _justificacion_viva(db, sesion.id, alumno_id) is not None:
        raise Conflicto("Ya hay una justificación pendiente o aprobada para esta sesión.")
    j = Justificacion(sesion_id=sesion.id, alumno_id=alumno_id, motivo=motivo, estado="pendiente", creada_por=actor.id)
    db.add(j)
    db.flush()
    # El motivo puede traer datos de salud: no se copia a la auditoría.
    _auditar(
        db, "justificacion.crear", "justificacion", j.id, actor.id, ip,
        despues={"sesion_id": str(sesion.id), "alumno_id": str(alumno_id)},
    )
    return j


def listar_justificaciones(
    db: Session, usuario: Usuario, *, estado: str | None, alumno_id: uuid.UUID | None, skip: int, limit: int
) -> list[Justificacion]:
    q = select(Justificacion).join(Justificacion.alumno).join(Justificacion.sesion).where(
        alumnos.filtro_visibles(usuario)
    )
    if estado:
        q = q.where(Justificacion.estado == estado)
    if alumno_id:
        q = q.where(Justificacion.alumno_id == alumno_id)
    q = q.order_by(Sesion.fecha.desc(), Justificacion.creado_en).offset(skip).limit(limit)
    return list(db.scalars(q).unique())


def obtener_justificacion(db: Session, usuario: Usuario, justificacion_id: uuid.UUID) -> Justificacion:
    j = db.scalar(
        select(Justificacion).join(Justificacion.alumno)
        .where(Justificacion.id == justificacion_id, alumnos.filtro_visibles(usuario))
    )
    if j is None:
        raise NoEncontrado("Justificación no encontrada.")
    return j


def revisar(
    db: Session, j: Justificacion, *, aprobar: bool, comentario: str | None, actor: Usuario, ip: str | None
) -> Justificacion:
    if j.estado != "pendiente":
        raise Conflicto("La justificación ya fue revisada.")
    j.estado = "aprobada" if aprobar else "rechazada"
    j.revisada_por, j.revisada_en, j.comentario = actor.id, fechas.ahora(), comentario
    sesion = j.sesion
    if aprobar:
        _fijar_asistencia(db, sesion, j.alumno_id, "justificado", "justificacion", actor.id)
        multas.anular_si_pendiente(
            db, sesion.id, j.alumno_id, motivo="Justificación aprobada", actor_id=actor.id, ip=ip
        )
    elif sesion.cerrada_en is not None and not sesion.cancelada:
        # Rechazada después del cierre: la ausencia queda en firme y se genera la multa.
        actual = _asistencia(db, sesion.id, j.alumno_id)
        if actual is None or actual.estado != "presente":
            _fijar_asistencia(db, sesion, j.alumno_id, "ausente", "justificacion", actor.id)
            multas.generar(db, sesion, j.alumno_id, actor_id=actor.id, ip=ip)
    db.flush()
    _auditar(
        db, "justificacion.revisar", "justificacion", j.id, actor.id, ip,
        despues={"estado": j.estado, "comentario": comentario},
    )
    notificaciones.justificacion_revisada(db, j)
    return j


# ---------- Cierre diario ----------
@dataclass
class ResultadoCierre:
    sesiones: int = 0
    ausencias: int = 0
    multas: int = 0


def cerrar(db: Session, *, ahora: datetime, actor_id: uuid.UUID | None = None, ip: str | None = None) -> ResultadoCierre:
    """Cierra las sesiones cuya hora de cierre ya pasó: quien no marcó ni justificó queda ausente y con multa.

    Una justificación pendiente deja la decisión para cuando se revise. La llamará el worker cada noche.
    """
    resultado = ResultadoCierre()
    candidatas = db.scalars(
        select(Sesion)
        .where(Sesion.cancelada.is_(False), Sesion.cerrada_en.is_(None), Sesion.fecha <= ahora.date())
        .order_by(Sesion.fecha)
        .with_for_update(skip_locked=True)  # dos cierres simultáneos no procesan la misma sesión
    ).all()
    for sesion in candidatas:
        if momento_cierre(db, sesion) > ahora:
            continue
        ausentes = generadas = 0
        for alumno in esperados(db, sesion):
            actual = _asistencia(db, sesion.id, alumno.id)
            if actual is not None and actual.estado in ("presente", "justificado"):
                continue
            justificacion = _justificacion_viva(db, sesion.id, alumno.id)
            if justificacion is not None and justificacion.estado == "aprobada":
                _fijar_asistencia(db, sesion, alumno.id, "justificado", "justificacion", None)
                continue
            if justificacion is not None:  # pendiente: se decide al revisarla
                continue
            if actual is None:
                _fijar_asistencia(db, sesion, alumno.id, "ausente", "cierre", None)
            ausentes += 1
            if multas.generar(db, sesion, alumno.id, actor_id=actor_id, ip=ip) is not None:
                generadas += 1
        sesion.cerrada_en = ahora
        db.flush()
        _auditar(
            db, "sesion.cerrar", "sesion", sesion.id, actor_id, ip,
            despues={"ausencias": ausentes, "multas": generadas},
        )
        resultado.sesiones += 1
        resultado.ausencias += ausentes
        resultado.multas += generadas
    return resultado


# ---------- Alertas ----------
@dataclass
class Alerta:
    alumno: Alumno
    inasistencias_seguidas: int
    desde: date  # fecha de la primera ausencia de la racha (identifica la racha)


def alertas(db: Session, usuario: Usuario | None) -> list[Alerta]:
    """Alumnos con N o más ausencias seguidas (la justificada rompe la racha), según
    "inasistencias_consecutivas_aviso". Con usuario=None (el worker) revisa todo el club."""
    minimo = configuracion.obtener(db, "inasistencias_consecutivas_aviso")
    if minimo <= 0:
        return []
    candidatos = db.scalars(
        select(Alumno).join(Inscripcion, Inscripcion.alumno_id == Alumno.id).where(
            alumnos.filtro_visibles(usuario) if usuario is not None else true(), Alumno.activo.is_(True),
            Inscripcion.anio == fechas.hoy().year, Inscripcion.estado.in_(ESTADOS_VIGENTES),
        ).order_by(Alumno.apellidos, Alumno.nombres)
    ).all()
    resultado = []
    for alumno in candidatos:
        filas = db.execute(
            select(Asistencia.estado, Sesion.fecha).join(Sesion, Sesion.id == Asistencia.sesion_id)
            .where(Asistencia.alumno_id == alumno.id, Sesion.cancelada.is_(False))
            .order_by(Sesion.fecha.desc(), Sesion.hora_inicio.desc())
            .limit(60)
        ).all()
        racha, desde = 0, None
        for estado, fecha in filas:
            if estado != "ausente":
                break
            racha, desde = racha + 1, fecha
        if racha >= minimo:
            resultado.append(Alerta(alumno, racha, desde))
    return resultado
