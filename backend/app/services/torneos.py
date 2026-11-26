"""Torneos: jornadas (rama, día y sedes), inscripción de clubes por rama con cupo, lista de espera, sedes y pagos."""
import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.fechas import formato_fecha, formato_pesos
from app.models.acceso import Usuario
from app.models.torneos import OCUPAN_CUPO, EquipoTorneo, JornadaTorneo, PagoEquipo, Torneo
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


def _aplicar_jornadas(torneo: Torneo, jornadas: list[dict[str, Any]]) -> None:
    """Deja el torneo con esas jornadas (reutiliza las del mismo día y rama) y su rama, si es una sola."""
    for j in jornadas:
        if not torneo.fecha_inicio <= j["fecha"] <= torneo.fecha_fin:
            raise ErrorNegocio("Cada jornada debe quedar entre la fecha de inicio y la de fin del torneo.")
    actuales = {(j.rama, j.fecha): j for j in torneo.jornadas}
    nuevas = []
    for j in jornadas:
        jornada = actuales.pop((j["rama"], j["fecha"]), None) or JornadaTorneo(rama=j["rama"], fecha=j["fecha"])
        jornada.sedes = list(j.get("sedes") or [])
        nuevas.append(jornada)
    torneo.jornadas = nuevas  # las que sobran se borran
    ramas = {j["rama"] for j in jornadas}
    torneo.rama = ramas.pop() if len(ramas) == 1 else None


def crear(db: Session, *, datos: dict[str, Any], actor: Usuario, ip: str | None) -> Torneo:
    _validar_fechas(datos["fecha_inicio"], datos["fecha_fin"], datos["fecha_limite_inscripcion"], nuevo=True)
    if datos.get("cupo_equipos") is None:
        datos["cupo_equipos"] = configuracion.obtener(db, "cupo_equipos_sugerido")
    rama, jornadas = datos.pop("rama", None), datos.pop("jornadas", None)
    # En corto (solo la rama): una jornada el día de inicio, sin sedes.
    jornadas = jornadas or [{"rama": rama, "fecha": datos["fecha_inicio"], "sedes": []}]
    torneo = Torneo(**datos, estado="programado", creado_por=actor.id)
    _aplicar_jornadas(torneo, jornadas)
    db.add(torneo)
    db.flush()
    _auditar(
        db, "torneo.crear", "torneo", torneo.id, actor.id, ip,
        despues={
            "nombre": torneo.nombre, "ramas": torneo.ramas, "fecha_inicio": torneo.fecha_inicio.isoformat(),
            "cupo": torneo.cupo_equipos, "valor": torneo.valor_inscripcion, "jornadas": _jornadas_foto(torneo),
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


def _jornadas_foto(t: Torneo) -> list[dict[str, Any]]:
    return [{"rama": j.rama, "fecha": j.fecha.isoformat(), "sedes": list(j.sedes)} for j in t.jornadas]


def _foto(t: Torneo) -> dict[str, Any]:
    return {
        "nombre": t.nombre, "ramas": t.ramas, "fecha_inicio": t.fecha_inicio.isoformat(),
        "fecha_fin": t.fecha_fin.isoformat(), "lugar": t.lugar, "cupo": t.cupo_equipos, "valor": t.valor_inscripcion,
        "jornadas": _jornadas_foto(t),
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
    rama, jornadas = nuevos.pop("rama", None), nuevos.pop("jornadas", None)
    inicio_anterior = torneo.fecha_inicio
    for campo, valor in nuevos.items():
        setattr(torneo, campo, valor)
    if jornadas is None:
        # Se conservan las jornadas (con la rama nueva, si se cambió); una sola que caía el día de inicio se mueve
        # con él.
        jornadas = [{"rama": rama or j.rama, "fecha": j.fecha, "sedes": list(j.sedes)} for j in torneo.jornadas]
        if len(jornadas) == 1 and jornadas[0]["fecha"] == inicio_anterior:
            jornadas[0]["fecha"] = torneo.fecha_inicio
    _aplicar_jornadas(torneo, jornadas)
    for e in db.scalars(select(EquipoTorneo).where(
        EquipoTorneo.torneo_id == torneo.id, EquipoTorneo.estado != "retirado",
    )):
        if e.rama not in torneo.ramas:
            raise ErrorNegocio(f"Hay equipos inscritos en la rama {e.rama}: retíralos antes de quitarla del torneo.")
        if e.sede and e.sede not in torneo.sedes_de(e.rama):
            e.sede = None  # su sede ya no está en la jornada: queda por asignar
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


def inscribir(
    db: Session, torneo: Torneo, *, datos: dict[str, Any], actor: Usuario | None, ip: str | None
) -> EquipoTorneo:
    """Inscribe el equipo de un club en una rama. `actor` es None cuando el club se inscribe solo desde el sitio.
    El cupo y el valor son uno para todo el torneo (las dos ramas)."""
    _bloquear(db, torneo)
    if torneo.estado != "programado":
        raise ErrorNegocio("El torneo fue cancelado.")
    if fechas.hoy() > torneo.fecha_limite_inscripcion:
        raise ErrorNegocio(f"Las inscripciones cerraron el {formato_fecha(torneo.fecha_limite_inscripcion)}.")
    datos = dict(datos)
    rama = datos.pop("rama", None)
    if rama is None:
        if len(torneo.ramas) != 1:
            raise ErrorNegocio("Elige la rama en la que se inscribe el equipo (femenina o masculina).")
        rama = torneo.ramas[0]
    elif rama not in torneo.ramas:
        raise ErrorNegocio(f"Este torneo no tiene rama {rama}.")
    # Con el torneo bloqueado esta consulta es segura; el índice único de la base queda como respaldo.
    repetido = db.scalar(select(EquipoTorneo.id).where(
        EquipoTorneo.torneo_id == torneo.id, EquipoTorneo.estado != "retirado", EquipoTorneo.rama == rama,
        func.lower(EquipoTorneo.nombre_club) == datos["nombre_club"].lower(),
    ))
    if repetido is not None:
        raise Conflicto(f"El club «{datos['nombre_club']}» ya tiene equipo en la rama {rama} de este torneo.")
    hay_cupo = _ocupados(db, torneo) < torneo.cupo_equipos
    equipo = EquipoTorneo(
        torneo_id=torneo.id, rama=rama, **datos, estado=_estado_con_cupo(torneo) if hay_cupo else "en_espera",
        valor=torneo.valor_inscripcion, monto_pagado=0, inscrito_por=actor.id if actor else None,
    )
    db.add(equipo)
    db.flush()
    _auditar(
        db, "torneo.inscribir_equipo", "equipo_torneo", equipo.id, actor.id if actor else None, ip,
        despues={"torneo_id": str(torneo.id), "club": equipo.nombre_club, "rama": rama, "estado": equipo.estado},
    )
    return equipo


def asignar_sede(
    db: Session, torneo: Torneo, equipo: EquipoTorneo, *, sede: str | None, actor: Usuario, ip: str | None
) -> EquipoTorneo:
    """El organizador decide en qué sede juega cada equipo: una de las sedes de la jornada de su rama."""
    if equipo.estado == "retirado":
        raise Conflicto("El equipo se retiró del torneo.")
    if sede is not None and sede not in torneo.sedes_de(equipo.rama):
        raise ErrorNegocio(f"«{sede}» no es una sede de la rama {equipo.rama} en este torneo.")
    antes = equipo.sede
    equipo.sede = sede
    db.flush()
    _auditar(db, "torneo.asignar_sede", "equipo_torneo", equipo.id, actor.id, ip,
             antes={"sede": antes}, despues={"sede": sede})
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
