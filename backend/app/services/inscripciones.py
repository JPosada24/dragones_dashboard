"""Inscripciones: plazo de pago (configurable), prórrogas y ciclo de estados."""
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.fechas import formato_fecha, formato_pesos, hoy
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, Inscripcion, PagoInscripcion, Prorroga
from app.models.dominio import ESTADOS_VIGENTES
from app.services import alumnos, auditoria, configuracion
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado, Prohibido

ETIQUETAS = {
    "pendiente_pago": "pendiente de pago",
    "activo": "activo",
    "a_expulsar": "a expulsar",
    "expulsado": "expulsado",
    "rechazado": "rechazado",
}

# Cambios de estado manuales permitidos -> permiso que exige cada uno.
# pendiente_pago -> activo NO está aquí: solo ocurre al registrar el pago dentro del plazo.
TRANSICIONES: dict[tuple[str, str], str] = {
    ("pendiente_pago", "rechazado"): "inscripciones.gestionar",
    ("activo", "a_expulsar"): "inscripciones.gestionar",
    ("a_expulsar", "activo"): "inscripciones.gestionar",
    ("a_expulsar", "expulsado"): "expulsion.confirmar",
}


def _resumen(i: Inscripcion) -> dict[str, Any]:
    return {
        "estado": i.estado,
        "fecha_limite_pago": i.fecha_limite_pago.isoformat(),
        "fecha_pago": i.fecha_pago.isoformat() if i.fecha_pago else None,
        "monto_pagado": i.monto_pagado,
        "causa_rechazo": i.causa_rechazo,
        "motivo": i.motivo,
    }


def _auditar(db: Session, accion: str, i: Inscripcion, actor_id: uuid.UUID | None, ip: str | None, **extra) -> None:
    auditoria.registrar(
        db, accion=accion, entidad="inscripcion", entidad_id=str(i.id), usuario_id=actor_id, ip=ip, **extra,
    )


def _verificar_sin_vigente(db: Session, alumno_id: uuid.UUID, anio: int, excluir: uuid.UUID | None = None) -> None:
    q = select(Inscripcion.id).where(
        Inscripcion.alumno_id == alumno_id, Inscripcion.anio == anio, Inscripcion.estado.in_(ESTADOS_VIGENTES)
    )
    if excluir is not None:
        q = q.where(Inscripcion.id != excluir)
    if db.scalar(q) is not None:
        raise Conflicto(f"El alumno ya tiene una inscripción vigente para {anio}.")


# ---------- Consultas ----------
def listar(
    db: Session, usuario: Usuario, *, estado: str | None, anio: int | None, rama: str | None,
    alumno_id: uuid.UUID | None, skip: int, limit: int,
) -> list[Inscripcion]:
    q = select(Inscripcion).join(Inscripcion.alumno).where(alumnos.filtro_visibles(usuario))
    if estado:
        q = q.where(Inscripcion.estado == estado)
    if anio:
        q = q.where(Inscripcion.anio == anio)
    if rama:
        q = q.where(Inscripcion.rama == rama)
    if alumno_id:
        q = q.where(Inscripcion.alumno_id == alumno_id)
    q = q.order_by(Inscripcion.fecha_inscripcion.desc(), Alumno.apellidos).offset(skip).limit(limit)
    return list(db.scalars(q).unique())


def obtener_visible(db: Session, usuario: Usuario, inscripcion_id: uuid.UUID) -> Inscripcion:
    i = db.scalar(
        select(Inscripcion).join(Inscripcion.alumno)
        .where(Inscripcion.id == inscripcion_id, alumnos.filtro_visibles(usuario))
    )
    if i is None:
        raise NoEncontrado("Inscripción no encontrada.")
    return i


# ---------- Acciones ----------
def crear(
    db: Session, *, alumno_id: uuid.UUID, fecha_inscripcion: date | None, actor: Usuario, ip: str | None
) -> Inscripcion:
    hoy_ = hoy()
    if "inscripciones.gestionar" in actor.permisos_codigos:
        alumno = db.get(Alumno, alumno_id)
        if alumno is None:
            raise NoEncontrado("Alumno no encontrado.")
    else:
        # El Entrenador inscribe solo alumnos de su rama, y siempre con la fecha de hoy.
        alumno = alumnos.obtener_visible(db, actor, alumno_id)
        if fecha_inscripcion is not None and fecha_inscripcion != hoy_:
            raise Prohibido("Solo un Admin puede registrar una inscripción con otra fecha.")

    fecha = fecha_inscripcion or hoy_
    if fecha > hoy_:
        raise ErrorNegocio("La fecha de inscripción no puede ser futura.")
    if not alumno.activo:
        raise ErrorNegocio("El alumno está inactivo.")
    if alumnos.es_menor(db, alumno.fecha_nacimiento, fecha) and not alumno.vinculos:
        raise ErrorNegocio("El alumno es menor de edad: necesita al menos un acudiente para inscribirse.")
    _verificar_sin_vigente(db, alumno.id, fecha.year)

    plazo = configuracion.obtener(db, "plazo_pago_dias")
    valor = configuracion.obtener(db, "valor_inscripcion")
    inscripcion = Inscripcion(
        alumno=alumno,
        anio=fecha.year,
        rama=alumno.rama,
        fecha_inscripcion=fecha,
        fecha_limite_pago=fecha + timedelta(days=plazo),
        valor=valor,
        # Si el SuperAdmin pone la inscripción gratis (valor 0), no hay nada que pagar.
        estado="pendiente_pago" if valor > 0 else "activo",
        fecha_pago=None if valor > 0 else fecha,
        creado_por=actor.id,
    )
    db.add(inscripcion)
    db.flush()
    _auditar(
        db, "inscripcion.crear", inscripcion, actor.id, ip,
        despues={**_resumen(inscripcion), "alumno_id": str(alumno.id), "valor": inscripcion.valor, "plazo_dias": plazo},
    )
    return inscripcion


def registrar_pago(
    db: Session, i: Inscripcion, *, fecha_pago: date, monto: int, actor: Usuario, ip: str | None
) -> Inscripcion:
    """Registra un abono (total o parcial). Todos los abonos deben caer dentro del plazo vigente."""
    if i.estado == "rechazado":
        raise ErrorNegocio(
            "La inscripción está rechazada. Un Admin o SuperAdmin debe conceder una prórroga antes de registrar el pago."
        )
    if i.estado != "pendiente_pago":
        raise Conflicto(f"La inscripción ya no está pendiente de pago (estado: {ETIQUETAS[i.estado]}).")
    if fecha_pago > hoy():
        raise ErrorNegocio("La fecha de pago no puede ser futura.")
    if fecha_pago < i.fecha_inscripcion:
        raise ErrorNegocio("La fecha de pago no puede ser anterior a la fecha de inscripción.")
    if fecha_pago > i.fecha_limite_pago:
        plazo = (
            "el plazo ampliado por prórroga" if i.prorrogas
            else f"el plazo de {(i.fecha_limite_pago - i.fecha_inscripcion).days} días"
        )
        raise ErrorNegocio(
            f"La fecha de pago ({formato_fecha(fecha_pago)}) supera {plazo} para pagar la inscripción "
            f"(fecha límite: {formato_fecha(i.fecha_limite_pago)}). "
            "Solo un Admin o SuperAdmin puede conceder una prórroga."
        )
    if monto > i.saldo:
        raise ErrorNegocio(
            f"El abono ({formato_pesos(monto)}) supera el saldo pendiente ({formato_pesos(i.saldo)})."
        )
    antes = _resumen(i)
    i.pagos.append(PagoInscripcion(fecha=fecha_pago, monto=monto, registrado_por=actor.id))
    i.monto_pagado = (i.monto_pagado or 0) + monto
    if i.saldo == 0:  # con el último abono la inscripción queda activa
        i.estado, i.fecha_pago = "activo", fecha_pago
    db.flush()
    _auditar(
        db, "inscripcion.pago", i, actor.id, ip, antes=antes,
        despues={**_resumen(i), "abono": monto, "fecha_abono": fecha_pago.isoformat(), "saldo": i.saldo},
    )
    return i


def anular_pago(
    db: Session, i: Inscripcion, *, pago_id: uuid.UUID, motivo: str, actor: Usuario, ip: str | None
) -> Inscripcion:
    """Revierte un abono con un movimiento negativo. El abono original queda en el historial."""
    pago = next((p for p in i.pagos if p.id == pago_id), None)
    if pago is None:
        raise NoEncontrado("Abono no encontrado en esta inscripción.")
    if pago.anula_id is not None:
        raise ErrorNegocio("Ese movimiento ya es una anulación; no se puede anular.")
    if any(p.anula_id == pago.id for p in i.pagos):
        raise Conflicto("Ese abono ya fue anulado.")
    if i.estado not in ("pendiente_pago", "activo", "rechazado"):
        raise Conflicto(f"No se pueden anular abonos de una inscripción en estado {ETIQUETAS[i.estado]}.")

    antes = _resumen(i)
    i.pagos.append(PagoInscripcion(
        fecha=hoy(), monto=-pago.monto, anula_id=pago.id, motivo=motivo, registrado_por=actor.id,
    ))
    i.monto_pagado = (i.monto_pagado or 0) - pago.monto
    if i.estado == "activo" and i.saldo > 0:  # sin ese abono ya no está paga: vuelve a pendiente
        i.estado, i.fecha_pago = "pendiente_pago", None
    db.flush()
    _auditar(
        db, "inscripcion.anular_pago", i, actor.id, ip, antes=antes,
        despues={**_resumen(i), "abono_anulado": str(pago.id), "monto": pago.monto, "motivo": motivo},
    )
    return i


def conceder_prorroga(
    db: Session, i: Inscripcion, *, nuevo_limite: date, motivo: str, actor: Usuario, ip: str | None
) -> Inscripcion:
    if i.estado == "rechazado" and i.causa_rechazo != "vencimiento":
        raise ErrorNegocio("Solo se puede prorrogar una inscripción rechazada por vencimiento del plazo.")
    if i.estado not in ("pendiente_pago", "rechazado"):
        raise Conflicto(f"Solo se puede prorrogar una inscripción pendiente de pago (estado: {ETIQUETAS[i.estado]}).")
    if nuevo_limite <= i.fecha_limite_pago:
        raise ErrorNegocio(
            f"La nueva fecha límite debe ser posterior a la actual ({formato_fecha(i.fecha_limite_pago)})."
        )
    if nuevo_limite < hoy():
        raise ErrorNegocio("La nueva fecha límite no puede estar en el pasado.")

    antes = _resumen(i)
    if i.estado == "rechazado":  # la prórroga reactiva la inscripción vencida
        _verificar_sin_vigente(db, i.alumno_id, i.anio, excluir=i.id)
        i.estado, i.causa_rechazo, i.motivo = "pendiente_pago", None, None
    i.prorrogas.append(Prorroga(
        limite_anterior=i.fecha_limite_pago, limite_nuevo=nuevo_limite, motivo=motivo, concedida_por=actor.id,
    ))
    i.fecha_limite_pago = nuevo_limite
    db.flush()
    _auditar(db, "inscripcion.prorroga", i, actor.id, ip, antes=antes, despues={**_resumen(i), "motivo_prorroga": motivo})
    return i


def cambiar_estado(
    db: Session, i: Inscripcion, *, nuevo: str, motivo: str | None, actor: Usuario, ip: str | None
) -> Inscripcion:
    if nuevo == i.estado:
        raise Conflicto(f"La inscripción ya está en estado {ETIQUETAS[nuevo]}.")
    permiso = TRANSICIONES.get((i.estado, nuevo))
    if permiso is None:
        detalle = " El paso a activo ocurre al registrar el pago." if i.estado == "pendiente_pago" else ""
        raise ErrorNegocio(f"No se puede pasar de '{ETIQUETAS[i.estado]}' a '{ETIQUETAS[nuevo]}'.{detalle}")
    if permiso not in actor.permisos_codigos:
        raise Prohibido("Solo el SuperAdmin puede confirmar una expulsión.")
    if nuevo in ("rechazado", "a_expulsar", "expulsado") and not motivo:
        raise ErrorNegocio("Indica el motivo del cambio de estado.")

    antes = _resumen(i)
    i.estado, i.motivo = nuevo, motivo
    i.causa_rechazo = "manual" if nuevo == "rechazado" else None
    db.flush()
    _auditar(db, "inscripcion.estado", i, actor.id, ip, antes=antes, despues=_resumen(i))
    return i


def vencer(db: Session, *, en: date, actor_id: uuid.UUID | None = None, ip: str | None = None) -> int:
    """Rechaza las inscripciones pendientes cuyo plazo terminó antes de `en`. La llamará el worker diario."""
    vencidas = db.scalars(
        select(Inscripcion)
        .where(Inscripcion.estado == "pendiente_pago", Inscripcion.fecha_limite_pago < en)
        .with_for_update(of=Inscripcion)
    ).unique().all()
    for i in vencidas:
        antes = _resumen(i)
        i.estado, i.causa_rechazo = "rechazado", "vencimiento"
        i.motivo = f"Venció el plazo de pago ({formato_fecha(i.fecha_limite_pago)}) sin registrar el pago."
        _auditar(db, "inscripcion.vencer", i, actor_id, ip, antes=antes, despues=_resumen(i))
    db.flush()
    return len(vencidas)
