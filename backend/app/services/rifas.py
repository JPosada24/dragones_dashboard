"""Rifas: talonarios por alumno, pagos de puestos, paz y salvo y sorteo con acta inmutable."""
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
from app.models.rifas import ActaSorteo, PagoPuesto, Puesto, Rifa, Talonario
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
    q = select(Rifa)
    if anio:
        q = q.where(Rifa.anio == anio)
    return list(db.scalars(q.order_by(Rifa.anio.desc(), Rifa.numero)))


def obtener(db: Session, rifa_id: uuid.UUID) -> Rifa:
    rifa = db.get(Rifa, rifa_id)
    if rifa is None:
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


def _puesto(db: Session, rifa: Rifa, numero: int) -> Puesto:
    puesto = db.scalar(select(Puesto).where(Puesto.rifa_id == rifa.id, Puesto.numero == numero))
    if puesto is None:
        raise NoEncontrado(f"El puesto {numero} no existe en esta rifa.")
    return puesto


def _talonario(db: Session, rifa: Rifa, talonario_id: uuid.UUID) -> Talonario:
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
    """Da un talonario (con sus puestos numerados) a cada alumno inscrito que aún no tenga en esta rifa."""
    if rifa.estado != "abierta":
        raise ErrorNegocio("Solo se asignan talonarios en una rifa abierta.")
    pendientes = _alumnos_sin_talonario(db, rifa)
    ultimo = db.scalar(select(func.max(Talonario.indice)).where(Talonario.rifa_id == rifa.id))
    indice = 0 if ultimo is None else ultimo + 1  # ojo: "ultimo or -1" fallaría cuando ultimo == 0
    n = rifa.puestos_por_talonario
    for alumno in pendientes:
        talonario = Talonario(rifa_id=rifa.id, alumno_id=alumno.id, indice=indice, codigo=alumno.codigo)
        db.add(talonario)
        db.flush()
        db.add_all(
            Puesto(rifa_id=rifa.id, talonario_id=talonario.id, numero=indice * n + k, monto_pagado=0) for k in range(n)
        )
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
    vigentes = db.scalar(select(func.count()).select_from(Rifa).where(Rifa.anio == anio, Rifa.estado != "cancelada"))
    if vigentes >= maximo:
        raise ErrorNegocio(f"Ya hay {vigentes} rifas en {anio}; el máximo configurado es {maximo}.")
    numero = (db.scalar(select(func.max(Rifa.numero)).where(Rifa.anio == anio)) or 0) + 1
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


def cancelar(db: Session, rifa: Rifa, *, motivo: str, actor: Usuario, ip: str | None) -> Rifa:
    if rifa.estado != "abierta":
        raise Conflicto("Solo se puede cancelar una rifa abierta.")
    rifa.estado, rifa.motivo_cancelacion = "cancelada", motivo
    db.flush()
    _auditar(db, "rifa.cancelar", "rifa", rifa.id, actor.id, ip, despues={"motivo": motivo})
    return rifa


# ---------- Puestos y pagos ----------
def actualizar_comprador(
    db: Session, rifa: Rifa, numero: int, *, nombre: str | None, telefono: str | None, actor: Usuario, ip: str | None
) -> Puesto:
    _verificar_abierta(rifa)
    puesto = _puesto(db, rifa, numero)
    antes = {"comprador": puesto.comprador_nombre}
    puesto.comprador_nombre, puesto.comprador_telefono = nombre, telefono
    db.flush()
    _auditar(db, "rifa.puesto_comprador", "puesto", puesto.id, actor.id, ip, antes=antes, despues={"comprador": nombre})
    return puesto


def _pagar_puesto(db: Session, puesto: Puesto, monto: int, fecha: date, actor_id: uuid.UUID) -> None:
    puesto.pagos.append(PagoPuesto(fecha=fecha, monto=monto, registrado_por=actor_id))
    puesto.monto_pagado += monto


def _validar_fecha_pago(fecha: date) -> None:
    if fecha > fechas.hoy():
        raise ErrorNegocio("La fecha de pago no puede ser futura.")


def pagar_puesto(
    db: Session, rifa: Rifa, numero: int, *, monto: int, fecha: date, actor: Usuario, ip: str | None
) -> Puesto:
    _verificar_abierta(rifa)
    _validar_fecha_pago(fecha)
    puesto = _puesto(db, rifa, numero)
    saldo = rifa.precio_puesto - puesto.monto_pagado
    if monto > saldo:
        raise ErrorNegocio(f"El pago ({formato_pesos(monto)}) supera el saldo del puesto ({formato_pesos(saldo)}).")
    _pagar_puesto(db, puesto, monto, fecha, actor.id)
    db.flush()
    _auditar(db, "rifa.pago_puesto", "puesto", puesto.id, actor.id, ip,
             despues={"numero": numero, "monto": monto, "fecha": fecha.isoformat()})
    return puesto


def pagar_talonario(
    db: Session, rifa: Rifa, talonario_id: uuid.UUID, *, monto: int, fecha: date, actor: Usuario, ip: str | None
) -> Talonario:
    """Reparte un pago entre los puestos con saldo, en orden de número (el alumno entrega la plata junta)."""
    _verificar_abierta(rifa)
    _validar_fecha_pago(fecha)
    talonario = _talonario(db, rifa, talonario_id)
    if monto > talonario.saldo:
        raise ErrorNegocio(
            f"El pago ({formato_pesos(monto)}) supera el saldo del talonario ({formato_pesos(talonario.saldo)})."
        )
    restante = monto
    for puesto in talonario.puestos:
        if restante == 0:
            break
        parte = min(restante, rifa.precio_puesto - puesto.monto_pagado)
        if parte > 0:
            _pagar_puesto(db, puesto, parte, fecha, actor.id)
            restante -= parte
    db.flush()
    _auditar(db, "rifa.pago_talonario", "talonario", talonario.id, actor.id, ip,
             despues={"monto": monto, "fecha": fecha.isoformat(), "saldo": talonario.saldo})
    return talonario


def anular_pago(
    db: Session, rifa: Rifa, numero: int, pago_id: uuid.UUID, *, motivo: str, actor: Usuario, ip: str | None
) -> Puesto:
    puesto = _puesto(db, rifa, numero)
    pago = next((p for p in puesto.pagos if p.id == pago_id), None)
    if pago is None:
        raise NoEncontrado("Pago no encontrado en este puesto.")
    if pago.anula_id is not None:
        raise ErrorNegocio("Ese movimiento ya es una anulación; no se puede anular.")
    if any(p.anula_id == pago.id for p in puesto.pagos):
        raise Conflicto("Ese pago ya fue anulado.")
    puesto.pagos.append(PagoPuesto(
        fecha=fechas.hoy(), monto=-pago.monto, anula_id=pago.id, motivo=motivo, registrado_por=actor.id,
    ))
    puesto.monto_pagado -= pago.monto
    db.flush()
    # Si la rifa ya se sorteó, el acta no cambia: queda como constancia de lo que había en ese momento.
    _auditar(db, "rifa.anular_pago", "puesto", puesto.id, actor.id, ip,
             despues={"pago_anulado": str(pago.id), "monto": pago.monto, "motivo": motivo})
    return puesto


# ---------- Sorteo ----------
def huella(participantes: list[int]) -> str:
    return hashlib.sha256(json.dumps(participantes, separators=(",", ":")).encode()).hexdigest()


def sortear(db: Session, rifa: Rifa, *, actor: Usuario, ip: str | None) -> ActaSorteo:
    """Elige un puesto al azar (CSPRNG del sistema) entre los talonarios pagados al 100 %."""
    # Primero se bloquea la fila y se relee el estado: dos clics simultáneos no pueden producir dos ganadores.
    db.refresh(rifa, with_for_update=True)
    if rifa.estado != "abierta":
        raise Conflicto("Esta rifa ya se sorteó o fue cancelada.")
    if fechas.hoy() < rifa.fecha_sorteo:
        raise ErrorNegocio(f"El sorteo es el {fechas.formato_fecha(rifa.fecha_sorteo)}; aún no se puede jugar.")
    pagados = [t for t in db.scalars(select(Talonario).where(Talonario.rifa_id == rifa.id)) if t.pagado]
    puestos = {p.numero: (p, t) for t in pagados for p in t.puestos}
    if not puestos:
        raise ErrorNegocio("No hay talonarios pagados al 100 %: nadie participa todavía en el sorteo.")
    participantes = sorted(puestos)
    numero = secrets.choice(participantes)
    puesto, talonario = puestos[numero]
    acta = ActaSorteo(
        rifa_id=rifa.id, numero_ganador=numero, puesto_id=puesto.id, alumno_id=talonario.alumno_id,
        comprador_nombre=puesto.comprador_nombre, participantes=participantes,
        total_participantes=len(participantes), huella=huella(participantes), jugado_por=actor.id,
    )
    db.add(acta)
    rifa.estado = "sorteada"
    db.flush()
    _auditar(db, "rifa.sortear", "rifa", rifa.id, actor.id, ip,
             despues={"numero_ganador": numero, "participantes": len(participantes), "huella": acta.huella})
    return acta


def acta(db: Session, rifa: Rifa) -> ActaSorteo:
    a = db.scalar(select(ActaSorteo).where(ActaSorteo.rifa_id == rifa.id))
    if a is None:
        raise NoEncontrado("Esta rifa aún no se ha sorteado.")
    return a


def talonario_de(db: Session, rifa_id: uuid.UUID, alumno_id: uuid.UUID) -> Talonario:
    """El talonario de un alumno en una rifa (para mostrar el acta con su código y boleta)."""
    t = db.scalar(select(Talonario).where(Talonario.rifa_id == rifa_id, Talonario.alumno_id == alumno_id))
    if t is None:
        raise NoEncontrado("Talonario no encontrado en esta rifa.")
    return t
