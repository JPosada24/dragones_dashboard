"""Reportes de dinero para la tesorería del club."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.core.fechas import hoy
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.reportes import IngresoMesOut, IngresosOut
from app.services import auditoria
from app.services import reportes as servicio
from app.services.errores import ErrorNegocio

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/ingresos", response_model=IngresosOut)
def ingresos(
    anio: int | None = Query(None, ge=2000, le=2100),
    _: Usuario = Depends(requiere("reportes.ver")),
    db: Session = Depends(get_db),
) -> IngresosOut:
    """Neto por mes y concepto (las anulaciones restan en el mes en que se hicieron)."""
    anio = anio or hoy().year
    meses = [IngresoMesOut(**m) for m in servicio.ingresos(db, anio)]
    return IngresosOut(anio=anio, meses=meses, total=sum(m.total for m in meses))


@router.get("/movimientos.csv")
def movimientos_csv(
    desde: date,
    hasta: date,
    request: Request,
    actor: Usuario = Depends(requiere("reportes.exportar")),
    db: Session = Depends(get_db),
) -> Response:
    """Todos los movimientos de dinero del rango, para la contabilidad (CSV separado por «;»). Queda auditado."""
    if hasta < desde or (hasta - desde).days > 366:
        raise ErrorNegocio("El rango debe ir de una fecha a otra posterior, de máximo un año.")
    contenido = servicio.movimientos_csv(db, desde, hasta)
    auditoria.registrar(db, accion="reportes.exportar", entidad="reportes", entidad_id="movimientos",
                        usuario_id=actor.id, despues={"desde": desde.isoformat(), "hasta": hasta.isoformat()},
                        ip=ip_cliente(request))
    db.commit()
    return Response(
        contenido, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="movimientos-{desde}-a-{hasta}.csv"',
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
