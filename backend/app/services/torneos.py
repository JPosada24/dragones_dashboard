"""Torneos: inscripción de clubes externos con cupo, lista de espera y pagos."""
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.fechas import formato_fecha, formato_pesos
from app.models.acceso import Usuario
from app.models.torneos import OCUPAN_CUPO, EquipoTorneo, PagoEquipo, Torneo
from app.services import auditoria, configuracion, programacion
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado


def _auditar(db: Session, accion: str, entidad: str, entidad_id, actor_id, ip, **extra) -> None:
    auditoria.registrar(
        db, accion=accion, entidad=entidad, entidad_id=str(entidad_id), usuario_id=actor_id, ip=ip, **extra,
    )


# ---------- Torneos ----------
def listar(db: Session, *, desde: date | None) -> list[Torneo]:
    q = select(Torneo).where(Torneo.estado != "eliminado")
    if desde:
        q = q.where(Torneo.fecha_fin >= desde)
    return list(db.scalars(q.order_by(Torneo.fecha_inicio)))


def obtener(db: Session, torneo_id: uuid.UUID) -> Torneo:
    torneo = db.get(Torneo, torneo_id)
    if torneo is None or torneo.estado == "eliminado":
        raise NoEncontrado("Torneo no encontrado.")
    return torneo


def resumen(db: Session, torneo: Torneo) -> dict[str, int]:
    equipos = list(db.scalars(select(EquipoTorneo).where(EquipoTorneo.torneo_id == torneo.id)))
    return {
        "ocupados": sum(e.estado in OCUPAN_CUPO for e in equipos),
        "confirmados": sum(e.estado == "confirmado" for e in equipos),
        "en_espera": sum(e.estado == "en_espera" for e in equipos),
        "recaudado": sum(e.monto_pagado for e in equipos),
    }


def _validar_fechas(inicio: date, fin: date, limite: date, *, nuevo: bool) -> None:
    hoy = fechas.hoy()
    if nuevo and inicio < hoy:
        raise ErrorNegocio("El torneo no puede empezar en una fecha pasada.")
    if fin < inicio:
        raise ErrorNegocio("La fecha de fin debe ser igual o posterior a la de inicio.")
    if limite > inicio or (nuevo and limite < hoy):
        raise ErrorNegocio("La fecha límite de inscripción debe estar entre hoy y el inicio del torneo.")


def crear(db: Session, *, datos: dict[str, Any], actor: Usuario, ip: str | None) -> Torneo:
    _validar_fechas(datos["fecha_inicio"], datos["fecha_fin"], datos["fecha_limite_inscripcion"], nuevo=True)
    if datos.get("cupo_equipos") is None:
        datos["cupo_equipos"] = configuracion.obtener(db, "cupo_equipos_sugerido")
    torneo = Torneo(**datos, estado="programado", creado_por=actor.id)
    db.add(torneo)
    db.flush()
    _auditar(
        db, "torneo.crear", "torneo", torneo.id, actor.id, ip,
        despues={
            "nombre": torneo.nombre, "rama": torneo.rama, "fecha_inicio": torneo.fecha_inicio.isoformat(),
            "cupo": torneo.cupo_equipos, "valor": torneo.valor_inscripcion,
        },
    )
    programacion.generar(db)  # los entrenamientos de esos días se cancelan
    return torneo


def cancelar(db: Session, torneo: Torneo, *, motivo: str | None, actor: Usuario, ip: str | None) -> Torneo:
    if torneo.estado == "cancelado":
        raise Conflicto("El torneo ya estaba cancelado.")
    torneo.estado, torneo.motivo_cancelacion = "cancelado", motivo
    db.flush()
    # Lo ya pagado queda registrado: la devolución a cada club se hace por fuera del sistema.
    _auditar(db, "torneo.cancelar", "torneo", torneo.id, actor.id, ip, despues={"motivo": motivo})
    programacion.generar(db)  # y vuelven los entrenamientos que había cancelado
    return torneo


def _foto(t: Torneo) -> dict[str, Any]:
    return {
        "nombre": t.nombre, "rama": t.rama, "fecha_inicio": t.fecha_inicio.isoformat(),
        "fecha_fin": t.fecha_fin.isoformat(), "lugar": t.lugar, "cupo": t.cupo_equipos, "valor": t.valor_inscripcion,
    }


def actualizar(db: Session, torneo: Torneo, *, cambios: dict[str, Any], actor: Usuario, ip: str | None) -> Torneo:
    """Corrige datos del torneo. Si sube el cupo entran los primeros de la lista de espera; no se puede bajar por
    debajo de los equipos que ya ocupan cupo. El valor nuevo aplica a quienes se inscriban después."""
    _bloquear(db, torneo)
    if torneo.estado != "programado":
        raise ErrorNegocio("Solo se edita un torneo programado.")
    nuevos = {k: v for k, v in cambios.items() if v is not None or k == "lugar"}
    inicio = nuevos.get("fecha_inicio", torneo.fecha_inicio)
    fin = nuevos.get("fecha_fin", torneo.fecha_fin)
    limite = nuevos.get("fecha_limite_inscripcion", torneo.fecha_limite_inscripcion)
    _validar_fechas(inicio, fin, limite, nuevo=False)
    ocupados = _ocupados(db, torneo)
    if nuevos.get("cupo_equipos") is not None and nuevos["cupo_equipos"] < ocupados:
        raise ErrorNegocio(f"Ya hay {ocupados} equipos con cupo: el cupo no puede ser menor.")
    antes = _foto(torneo)
    for campo, valor in nuevos.items():
        setattr(torneo, campo, valor)
    # Si hay más cupo, entran los que esperaban (en orden de llegada).
    libres = torneo.cupo_equipos - ocupados
    if libres > 0:
        for e in db.scalars(
            select(EquipoTorneo).where(EquipoTorneo.torneo_id == torneo.id, EquipoTorneo.estado == "en_espera")
            .order_by(EquipoTorneo.creado_en).limit(libres)
        ):
            e.estado = "confirmado" if e.valor == 0 else "pendiente_pago"
    db.flush()
    _auditar(db, "torneo.actualizar", "torneo", torneo.id, actor.id, ip, antes=antes, despues=_foto(torneo))
    programacion.generar(db)  # las fechas pueden haber cambiado
    return torneo


def eliminar(db: Session, torneo: Torneo, *, actor: Usuario, ip: str | None) -> None:
    """El torneo deja de verse en todas partes. Sus equipos y pagos se conservan como evidencia."""
    _bloquear(db, torneo)
    antes = {"nombre": torneo.nombre, "estado": torneo.estado, **resumen(db, torneo)}
    torneo.estado = "eliminado"
    db.flush()
    _auditar(db, "torneo.eliminar", "torneo", torneo.id, actor.id, ip, antes=antes)
    programacion.generar(db)  # vuelven los entrenamientos de esos días


# ---------- Equipos ----------
def listar_equipos(db: Session, torneo: Torneo) -> list[EquipoTorneo]:
    orden = {"confirmado": 0, "pendiente_pago": 1, "en_espera": 2, "retirado": 3}
    equipos = list(db.scalars(
        select(EquipoTorneo).where(EquipoTorneo.torneo_id == torneo.id).order_by(EquipoTorneo.creado_en)
    ))
    return sorted(equipos, key=lambda e: orden[e.estado])  # estable: dentro de cada estado, por orden de llegada


def obtener_equipo(db: Session, torneo: Torneo, equipo_id: uuid.UUID) -> EquipoTorneo:
    equipo = db.get(EquipoTorneo, equipo_id)
    if equipo is None or equipo.torneo_id != torneo.id:
        raise NoEncontrado("Equipo no encontrado en este torneo.")
    return equipo


def _bloquear(db: Session, torneo: Torneo) -> None:
    """Bloquea el torneo mientras se mueve el cupo: dos inscripciones simultáneas no pueden pasarse del límite."""
    db.refresh(torneo, with_for_update=True)


def _ocupados(db: Session, torneo: Torneo) -> int:
    return db.scalar(select(func.count()).select_from(EquipoTorneo).where(
        EquipoTorneo.torneo_id == torneo.id, EquipoTorneo.estado.in_(OCUPAN_CUPO)
    ))


def _estado_con_cupo(torneo: Torneo) -> str:
    return "confirmado" if torneo.valor_inscripcion == 0 else "pendiente_pago"


def inscribir(db: Session, torneo: Torneo, *, datos: dict[str, Any], actor: Usuario, ip: str | None) -> EquipoTorneo:
    _bloquear(db, torneo)
    if torneo.estado != "programado":
        raise ErrorNegocio("El torneo fue cancelado.")
    if fechas.hoy() > torneo.fecha_limite_inscripcion:
        raise ErrorNegocio(f"Las inscripciones cerraron el {formato_fecha(torneo.fecha_limite_inscripcion)}.")
    # Con el torneo bloqueado esta consulta es segura; el índice único de la base queda como respaldo.
    repetido = db.scalar(select(EquipoTorneo.id).where(
        EquipoTorneo.torneo_id == torneo.id, EquipoTorneo.estado != "retirado",
        func.lower(EquipoTorneo.nombre_club) == datos["nombre_club"].lower(),
    ))
    if repetido is not None:
        raise Conflicto(f"El club «{datos['nombre_club']}» ya está inscrito en este torneo.")
    hay_cupo = _ocupados(db, torneo) < torneo.cupo_equipos
    equipo = EquipoTorneo(
        torneo_id=torneo.id, **datos, estado=_estado_con_cupo(torneo) if hay_cupo else "en_espera",
        valor=torneo.valor_inscripcion, monto_pagado=0, inscrito_por=actor.id,
    )
    db.add(equipo)
    db.flush()
    _auditar(
        db, "torneo.inscribir_equipo", "equipo_torneo", equipo.id, actor.id, ip,
        despues={"torneo_id": str(torneo.id), "club": equipo.nombre_club, "estado": equipo.estado},
    )
    return equipo


def retirar(
    db: Session, torneo: Torneo, equipo: EquipoTorneo, *, motivo: str | None, actor: Usuario, ip: str | None
):
    """Retira un equipo. Si ocupaba cupo, entra el primero de la lista de espera. Devuelve el promovido (o None)."""
    _bloquear(db, torneo)
    if equipo.estado == "retirado":
        raise Conflicto("El equipo ya estaba retirado.")
    liberaba_cupo = equipo.estado in OCUPAN_CUPO
    antes = equipo.estado
    equipo.estado, equipo.motivo_retiro = "retirado", motivo
    db.flush()
    _auditar(db, "torneo.retirar_equipo", "equipo_torneo", equipo.id, actor.id, ip,
             antes={"estado": antes}, despues={"motivo": motivo, "pagado": equipo.monto_pagado})

    promovido = None
    if liberaba_cupo and torneo.estado == "programado" and _ocupados(db, torneo) < torneo.cupo_equipos:
        promovido = db.scalar(
            select(EquipoTorneo)
            .where(EquipoTorneo.torneo_id == torneo.id, EquipoTorneo.estado == "en_espera")
            .order_by(EquipoTorneo.creado_en).limit(1)
        )
        if promovido is not None:
            promovido.estado = _estado_con_cupo(torneo)
            db.flush()
            _auditar(db, "torneo.promover_equipo", "equipo_torneo", promovido.id, actor.id, ip,
                     antes={"estado": "en_espera"}, despues={"estado": promovido.estado})
    return promovido


# ---------- Pagos ----------
def pagar(
    db: Session, equipo: EquipoTorneo, *, monto: int, fecha: date, actor: Usuario, ip: str | None
) -> EquipoTorneo:
    if equipo.torneo.estado != "programado":
        raise ErrorNegocio("El torneo fue cancelado.")
    if equipo.estado == "en_espera":
        raise Conflicto("El equipo está en lista de espera: solo paga cuando tenga cupo.")
    if equipo.estado == "retirado":
        raise Conflicto("El equipo se retiró del torneo.")
    if fecha > fechas.hoy():
        raise ErrorNegocio("La fecha de pago no puede ser futura.")
    if monto > equipo.saldo:
        raise ErrorNegocio(
            f"El pago ({formato_pesos(monto)}) supera el saldo pendiente ({formato_pesos(equipo.saldo)})."
        )
    equipo.pagos.append(PagoEquipo(fecha=fecha, monto=monto, registrado_por=actor.id))
    equipo.monto_pagado += monto
    if equipo.saldo == 0:
        equipo.estado = "confirmado"
    db.flush()
    _auditar(db, "torneo.pago_equipo", "equipo_torneo", equipo.id, actor.id, ip,
             despues={"monto": monto, "fecha": fecha.isoformat(), "saldo": equipo.saldo, "estado": equipo.estado})
    return equipo


def anular_pago(
    db: Session, equipo: EquipoTorneo, pago_id: uuid.UUID, *, motivo: str | None, actor: Usuario, ip: str | None
) -> EquipoTorneo:
    pago = next((p for p in equipo.pagos if p.id == pago_id), None)
    if pago is None:
        raise NoEncontrado("Pago no encontrado en este equipo.")
    if pago.anula_id is not None:
        raise ErrorNegocio("Ese movimiento ya es una anulación; no se puede anular.")
    if any(p.anula_id == pago.id for p in equipo.pagos):
        raise Conflicto("Ese pago ya fue anulado.")
    equipo.pagos.append(PagoEquipo(
        fecha=fechas.hoy(), monto=-pago.monto, anula_id=pago.id, motivo=motivo, registrado_por=actor.id,
    ))
    equipo.monto_pagado -= pago.monto
    if equipo.estado == "confirmado" and equipo.saldo > 0:
        equipo.estado = "pendiente_pago"
    db.flush()
    _auditar(db, "torneo.anular_pago", "equipo_torneo", equipo.id, actor.id, ip,
             despues={"pago_anulado": str(pago.id), "monto": pago.monto, "motivo": motivo})
    return equipo
