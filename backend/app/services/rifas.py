"""Rifas: un talonario por alumno, pagos por talonario, paz y salvo y sorteo (varias jugadas) con acta inmutable."""
import hashlib
import json
import secrets
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import fechas
from app.core.fechas import formato_pesos
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, Inscripcion
from app.models.dominio import ESTADOS_VIGENTES
from app.models.rifas import RIFA_FUERA, ActaSorteo, PagoTalonario, Rifa, Talonario, boleta
from app.services import alumnos, auditoria, configuracion
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado


def _auditar(db: Session, accion: str, entidad: str, entidad_id, actor_id, ip, **extra) -> None:
    auditoria.registrar(
        db, accion=accion, entidad=entidad, entidad_id=str(entidad_id), usuario_id=actor_id, ip=ip, **extra,
    )


def _verificar_abierta(rifa: Rifa) -> None:
    if rifa.estado == "cancelada":
        raise ErrorNegocio("La rifa fue cancelada.")


# ---------- Consultas ----------
def listar(db: Session, *, anio: int | None) -> list[Rifa]:
    q = select(Rifa).where(Rifa.estado != "eliminada")
    if anio:
        q = q.where(Rifa.anio == anio)
    return list(db.scalars(q.order_by(Rifa.anio.desc(), Rifa.numero)))


def obtener(db: Session, rifa_id: uuid.UUID) -> Rifa:
    rifa = db.get(Rifa, rifa_id)
    if rifa is None or rifa.estado == "eliminada":
        raise NoEncontrado("Rifa no encontrada.")
    return rifa


def resumen(db: Session, rifa: Rifa) -> dict[str, int]:
    talonarios = list(db.scalars(select(Talonario).where(Talonario.rifa_id == rifa.id)))
    return {
        "talonarios": len(talonarios),
        "talonarios_pagados": sum(t.pagado for t in talonarios),
        "recaudado": sum(t.recaudado for t in talonarios),
        "esperado": len(talonarios) * rifa.valor_talonario,
    }


def talonarios_visibles(db: Session, usuario: Usuario, rifa: Rifa) -> list[Talonario]:
    """Staff: todos (Entrenador, su rama). Miembro: solo los suyos o los de sus hijos."""
    return list(db.scalars(
        select(Talonario).join(Talonario.alumno)
        .where(Talonario.rifa_id == rifa.id, alumnos.filtro_visibles(usuario))
        .order_by(Talonario.indice)
    ).unique())


def _talonario(db: Session, rifa: Rifa, talonario_id: uuid.UUID, *, bloquear: bool = False) -> Talonario:
    if bloquear:
        # Bloqueado mientras se paga o se anula: dos registros a la vez no pasan del valor del talonario.
        db.execute(select(Talonario.id).where(Talonario.id == talonario_id).with_for_update())
    t = db.get(Talonario, talonario_id)
    if t is None or t.rifa_id != rifa.id:
        raise NoEncontrado("Talonario no encontrado en esta rifa.")
    return t


# ---------- Creación y talonarios ----------
def _alumnos_sin_talonario(db: Session, rifa: Rifa) -> list[Alumno]:
    ya = select(Talonario.alumno_id).where(Talonario.rifa_id == rifa.id)
    return list(db.scalars(
        select(Alumno).join(Inscripcion, Inscripcion.alumno_id == Alumno.id).where(
            Alumno.activo.is_(True), Inscripcion.anio == rifa.anio, Inscripcion.estado.in_(ESTADOS_VIGENTES),
            Alumno.id.not_in(ya),
        ).order_by(Alumno.rama, Alumno.apellidos, Alumno.nombres)
    ))


def asignar_pendientes(db: Session, rifa: Rifa, *, actor: Usuario, ip: str | None) -> int:
    """Da un talonario a cada alumno inscrito que aún no tenga en esta rifa."""
    if rifa.estado != "abierta":
        raise ErrorNegocio("Solo se asignan talonarios en una rifa abierta.")
    pendientes = _alumnos_sin_talonario(db, rifa)
    ultimo = db.scalar(select(func.max(Talonario.indice)).where(Talonario.rifa_id == rifa.id))
    indice = 0 if ultimo is None else ultimo + 1  # ojo: "ultimo or -1" fallaría cuando ultimo == 0
    for alumno in pendientes:
        db.add(Talonario(rifa_id=rifa.id, alumno_id=alumno.id, indice=indice, codigo=alumno.codigo))
        indice += 1
    db.flush()
    if pendientes:
        _auditar(db, "rifa.asignar_talonarios", "rifa", rifa.id, actor.id, ip, despues={"asignados": len(pendientes)})
    return len(pendientes)


def crear(
    db: Session, *, nombre: str, anio: int, premio: str, fecha_sorteo: date, actor: Usuario, ip: str | None
) -> Rifa:
    if fecha_sorteo < fechas.hoy():
        raise ErrorNegocio("La fecha del sorteo no puede estar en el pasado.")
    if fecha_sorteo.year != anio:
        raise ErrorNegocio("La fecha del sorteo debe caer en el año de la rifa.")
    maximo = configuracion.obtener(db, "rifas_por_anio")
    vigentes = db.scalar(
        select(func.count()).select_from(Rifa).where(Rifa.anio == anio, Rifa.estado.not_in(RIFA_FUERA))
    )
    if vigentes >= maximo:
        raise ErrorNegocio(f"Ya hay {vigentes} rifas en {anio}; el máximo configurado es {maximo}.")
    numero = (db.scalar(
        select(func.max(Rifa.numero)).where(Rifa.anio == anio, Rifa.estado != "eliminada")
    ) or 0) + 1
    rifa = Rifa(
        nombre=nombre, anio=anio, numero=numero, premio=premio, fecha_sorteo=fecha_sorteo, estado="abierta",
        puestos_por_talonario=configuracion.obtener(db, "puestos_por_talonario"),
        precio_puesto=configuracion.obtener(db, "precio_puesto"), creado_por=actor.id,
    )
    db.add(rifa)
    db.flush()
    _auditar(
        db, "rifa.crear", "rifa", rifa.id, actor.id, ip,
        despues={"nombre": nombre, "anio": anio, "numero": numero, "premio": premio,
                 "puestos": rifa.puestos_por_talonario, "precio": rifa.precio_puesto},
    )
    asignar_pendientes(db, rifa, actor=actor, ip=ip)
    return rifa


def cancelar(db: Session, rifa: Rifa, *, motivo: str | None, actor: Usuario, ip: str | None) -> Rifa:
    if rifa.estado != "abierta":
        raise Conflicto("Solo se puede cancelar una rifa abierta.")
    rifa.estado, rifa.motivo_cancelacion = "cancelada", motivo
    db.flush()
    _auditar(db, "rifa.cancelar", "rifa", rifa.id, actor.id, ip, despues={"motivo": motivo})
    return rifa


def eliminar(db: Session, rifa: Rifa, *, actor: Usuario, ip: str | None) -> None:
    """La rifa deja de verse y de contar (deudas, paz y salvo, máximo por año). Su dinero y sus actas no se
    borran: quedan como evidencia, y la auditoría registra quién la eliminó y cómo estaba."""
    db.refresh(rifa, with_for_update=True)
    antes = {"nombre": rifa.nombre, "anio": rifa.anio, "numero": rifa.numero, "estado": rifa.estado,
             **resumen(db, rifa)}
    rifa.estado = "eliminada"
    db.flush()
    _auditar(db, "rifa.eliminar", "rifa", rifa.id, actor.id, ip, antes=antes)


# ---------- Pagos ----------
def pagar_talonario(
    db: Session, rifa: Rifa, talonario_id: uuid.UUID, *, monto: int, fecha: date, actor: Usuario, ip: str | None
) -> Talonario:
    """Pago completo o abono del talonario (el alumno entrega lo que ha recogido)."""
    _verificar_abierta(rifa)
    if fecha > fechas.hoy():
        raise ErrorNegocio("La fecha de pago no puede ser futura.")
    talonario = _talonario(db, rifa, talonario_id, bloquear=True)
    if monto > talonario.saldo:
        raise ErrorNegocio(
            f"El pago ({formato_pesos(monto)}) supera el saldo del talonario ({formato_pesos(talonario.saldo)})."
        )
    talonario.pagos.append(PagoTalonario(fecha=fecha, monto=monto, registrado_por=actor.id))
    db.flush()
    _auditar(db, "rifa.pago_talonario", "talonario", talonario.id, actor.id, ip,
             despues={"monto": monto, "fecha": fecha.isoformat(), "saldo": talonario.saldo})
    return talonario


def anular_pago(
    db: Session, rifa: Rifa, talonario_id: uuid.UUID, pago_id: uuid.UUID, *, motivo: str | None, actor: Usuario,
    ip: str | None,
) -> Talonario:
    """Un pago errado no se borra: se registra otro en negativo que lo revierte."""
    talonario = _talonario(db, rifa, talonario_id, bloquear=True)
    pago = next((p for p in talonario.pagos if p.id == pago_id), None)
    if pago is None:
        raise NoEncontrado("Pago no encontrado en este talonario.")
    if pago.anula_id is not None:
        raise ErrorNegocio("Ese movimiento ya es una anulación; no se puede anular.")
    if any(p.anula_id == pago.id for p in talonario.pagos):
        raise Conflicto("Ese pago ya fue anulado.")
    talonario.pagos.append(PagoTalonario(
        fecha=fechas.hoy(), monto=-pago.monto, anula_id=pago.id, motivo=motivo, registrado_por=actor.id,
    ))
    db.flush()
    # Si la rifa ya se sorteó, las actas no cambian: son constancia de lo que había en ese momento.
    _auditar(db, "rifa.anular_pago", "talonario", talonario.id, actor.id, ip,
             despues={"pago_anulado": str(pago.id), "monto": pago.monto, "motivo": motivo})
    return talonario


# ---------- Sorteo ----------
def huella(participantes: list[str]) -> str:
    return hashlib.sha256(json.dumps(participantes, separators=(",", ":")).encode()).hexdigest()


def sortear(db: Session, rifa: Rifa, *, actor: Usuario, ip: str | None) -> ActaSorteo:
    """Una jugada: elige al azar (CSPRNG del sistema) una boleta de los talonarios pagados al 100 %.
    Se puede jugar varias veces; una boleta que ya ganó en esta rifa no vuelve a la urna."""
    # Se bloquea la fila antes de leer: dos clics a la vez no producen dos actas con el mismo orden.
    db.refresh(rifa, with_for_update=True)
    if rifa.estado not in ("abierta", "sorteada"):
        raise Conflicto("Esta rifa fue cancelada.")
    if fechas.hoy() < rifa.fecha_sorteo:
        raise ErrorNegocio(f"El sorteo es el {fechas.formato_fecha(rifa.fecha_sorteo)}; aún no se puede jugar.")
    anteriores = list(db.scalars(select(ActaSorteo).where(ActaSorteo.rifa_id == rifa.id)))
    ganadas = {boleta(a.codigo, a.boleta) for a in anteriores}
    urna = {
        b: t
        for t in db.scalars(select(Talonario).where(Talonario.rifa_id == rifa.id)) if t.pagado
        for b in t.boletas() if b not in ganadas
    }
    if not urna:
        raise ErrorNegocio(
            "No hay talonarios pagados al 100 %: nadie participa todavía en el sorteo." if not anteriores
            else "No quedan boletas en la urna: todas las de los talonarios pagados ya ganaron."
        )
    participantes = sorted(urna)
    ganadora = secrets.choice(participantes)
    t = urna[ganadora]
    acta = ActaSorteo(
        rifa_id=rifa.id, orden=len(anteriores) + 1, talonario_id=t.id, alumno_id=t.alumno_id, codigo=t.codigo,
        boleta=int(ganadora.rsplit("-", 1)[1]), participantes=participantes, total_participantes=len(participantes),
        huella=huella(participantes), jugado_por=actor.id,
    )
    db.add(acta)
    rifa.estado = "sorteada"
    db.flush()
    _auditar(db, "rifa.sortear", "rifa", rifa.id, actor.id, ip,
             despues={"orden": acta.orden, "boleta": ganadora, "participantes": len(participantes),
                      "huella": acta.huella})
    return acta


def actas(db: Session, rifa: Rifa) -> list[ActaSorteo]:
    return list(db.scalars(select(ActaSorteo).where(ActaSorteo.rifa_id == rifa.id).order_by(ActaSorteo.orden)))
