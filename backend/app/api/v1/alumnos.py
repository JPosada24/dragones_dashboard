import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, requiere_alguno
from app.core.almacen import Almacen, get_almacen
from app.core.fechas import edad, hoy
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.alumnos import Alumno
from app.schemas.alumnos import (
    AcudienteVinculadoOut,
    AlumnoActualizar,
    AlumnoCrear,
    AlumnoOut,
    DocumentoIdentidadOut,
    DocumentoOut,
    TipoArchivo,
    VinculoIn,
)
from app.schemas.asistencia import HistorialOut
from app.schemas.comunes import Rama
from app.schemas.rifas import DeudaRifaOut, EstadoCuentaOut
from app.services import alumnos as servicio
from app.services import asistencia, configuracion, documentos, estado_cuenta
from app.services.errores import Prohibido

router = APIRouter(prefix="/alumnos", tags=["alumnos"])

VER_ALUMNOS = requiere_alguno("alumnos.ver_todos", "alumnos.ver_rama", "alumnos.ver_propios")
VER_DOCUMENTOS = requiere_alguno("alumnos.editar", "alumnos.ver_propios")


def alumno_a_out(alumno: Alumno, edad_mayoria: int, inscripcion_estado: str | None) -> AlumnoOut:
    anios = edad(alumno.fecha_nacimiento, hoy())
    return AlumnoOut(
        id=alumno.id,
        codigo=alumno.codigo,
        nombres=alumno.nombres,
        apellidos=alumno.apellidos,
        tipo_documento=alumno.tipo_documento,
        documento=servicio.enmascarar(alumno.documento_ultimos),
        fecha_nacimiento=alumno.fecha_nacimiento,
        edad=anios,
        es_menor=anios < edad_mayoria,
        rama=alumno.rama,
        telefono=alumno.telefono,
        email=alumno.email,
        direccion=alumno.direccion,
        eps=alumno.eps,
        usuario_id=alumno.usuario_id,
        activo=alumno.activo,
        inscripcion_estado=inscripcion_estado,
        acudientes=[
            AcudienteVinculadoOut(
                acudiente_id=v.acudiente.id, nombres=v.acudiente.nombres, apellidos=v.acudiente.apellidos,
                telefono=v.acudiente.telefono, parentesco=v.parentesco, principal=v.principal,
            )
            for v in alumno.vinculos
        ],
    )


def _out(db: Session, alumno: Alumno) -> AlumnoOut:
    estado = servicio.estados_inscripcion(db, [alumno.id], hoy().year).get(alumno.id)
    return alumno_a_out(alumno, configuracion.obtener(db, "edad_mayoria"), estado)


@router.get("", response_model=list[AlumnoOut])
def listar(
    rama: Rama | None = None,
    buscar: str | None = Query(None, min_length=2, max_length=80),
    activo: bool | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    usuario: Usuario = Depends(VER_ALUMNOS),
    db: Session = Depends(get_db),
) -> list[AlumnoOut]:
    """Busca por nombre o apellido (parcial), por código (F012) o por número de documento (completo, exacto)."""
    edad_mayoria = configuracion.obtener(db, "edad_mayoria")
    filas = servicio.listar(db, usuario, rama=rama, buscar=buscar, activo=activo, skip=skip, limit=limit)
    estados = servicio.estados_inscripcion(db, [a.id for a in filas], hoy().year)
    return [alumno_a_out(a, edad_mayoria, estados.get(a.id)) for a in filas]


@router.post("", response_model=AlumnoOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: AlumnoCrear,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> AlumnoOut:
    alumno = servicio.crear_alumno(
        db, datos=datos.model_dump(exclude={"acudientes"}), vinculos=[v.model_dump() for v in datos.acudientes],
        actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return _out(db, alumno)


@router.get("/{alumno_id}", response_model=AlumnoOut)
def detalle(alumno_id: uuid.UUID, usuario: Usuario = Depends(VER_ALUMNOS), db: Session = Depends(get_db)) -> AlumnoOut:
    return _out(db, servicio.obtener_visible(db, usuario, alumno_id))


@router.patch("/{alumno_id}", response_model=AlumnoOut)
def actualizar(
    alumno_id: uuid.UUID,
    datos: AlumnoActualizar,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> AlumnoOut:
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    servicio.actualizar_alumno(
        db, alumno, cambios=datos.model_dump(exclude_unset=True), actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return _out(db, alumno)


@router.delete("/{alumno_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    alumno_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.eliminar")),  # solo el SuperAdmin
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    """Elimina al alumno con TODA su información (pagos, asistencia, rifas, documentos). No se puede deshacer."""
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    claves = servicio.eliminar(db, alumno, actor=actor, ip=ip_cliente(request))
    db.commit()
    for clave in claves:  # después del commit: si la transacción falla, los archivos siguen ahí
        almacen.borrar(clave)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{alumno_id}/estado-cuenta", response_model=EstadoCuentaOut)
def ver_estado_cuenta(
    alumno_id: uuid.UUID, usuario: Usuario = Depends(VER_ALUMNOS), db: Session = Depends(get_db)
) -> EstadoCuentaOut:
    """Lo que el alumno debe al club (inscripción, multas, rifas). Paz y salvo = "al_dia"."""
    e = estado_cuenta.calcular(db, servicio.obtener_visible(db, usuario, alumno_id))
    return EstadoCuentaOut(
        alumno_id=alumno_id, anio=e.anio, inscripcion_estado=e.inscripcion_estado,
        inscripcion_saldo=e.inscripcion_saldo, multas_pendientes=e.multas_pendientes, multas_saldo=e.multas_saldo,
        rifas=[DeudaRifaOut(rifa=r.rifa, saldo=r.saldo) for r in e.rifas], total=e.total, al_dia=e.al_dia,
        en_mora=e.en_mora, entra_en_mora=e.entra_en_mora,
    )


@router.get("/{alumno_id}/asistencia", response_model=list[HistorialOut])
def historial_asistencia(
    alumno_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=200),
    usuario: Usuario = Depends(VER_ALUMNOS),
    db: Session = Depends(get_db),
) -> list[HistorialOut]:
    """Últimas asistencias del alumno y la multa de cada una (si la hubo)."""
    alumno = servicio.obtener_visible(db, usuario, alumno_id)
    return [HistorialOut(**vars(r)) for r in asistencia.historial_alumno(db, alumno, limit=limit)]


@router.get("/{alumno_id}/documento-identidad", response_model=DocumentoIdentidadOut)
def documento_identidad(
    alumno_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.ver_todos")),
    db: Session = Depends(get_db),
) -> DocumentoIdentidadOut:
    """Documento completo, descifrado. Solo Admin/SuperAdmin y cada consulta queda auditada."""
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    numero = servicio.ver_documento(db, alumno, actor=actor, ip=ip_cliente(request))
    db.commit()
    return DocumentoIdentidadOut(tipo_documento=alumno.tipo_documento, documento=numero)


@router.post("/{alumno_id}/acudientes", response_model=AlumnoOut)
def vincular_acudiente(
    alumno_id: uuid.UUID,
    datos: VinculoIn,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> AlumnoOut:
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    servicio.vincular_acudiente(db, alumno, **datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return _out(db, alumno)


@router.delete("/{alumno_id}/acudientes/{acudiente_id}", response_model=AlumnoOut)
def desvincular_acudiente(
    alumno_id: uuid.UUID,
    acudiente_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> AlumnoOut:
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    servicio.desvincular_acudiente(db, alumno, acudiente_id=acudiente_id, actor=actor, ip=ip_cliente(request))
    db.commit()
    return _out(db, alumno)


# ---------- Documentos ----------
def _alumno_para_documentos(db: Session, usuario: Usuario, alumno_id: uuid.UUID) -> Alumno:
    alumno = servicio.obtener_visible(db, usuario, alumno_id)
    if not documentos.puede_ver(db, usuario, alumno):
        raise Prohibido("No tienes permiso sobre los documentos de este alumno.")
    return alumno


@router.get("/{alumno_id}/documentos", response_model=list[DocumentoOut])
def listar_documentos(
    alumno_id: uuid.UUID, usuario: Usuario = Depends(VER_DOCUMENTOS), db: Session = Depends(get_db)
) -> list[DocumentoOut]:
    alumno = _alumno_para_documentos(db, usuario, alumno_id)
    return [DocumentoOut.model_validate(d) for d in documentos.listar(db, alumno)]


@router.post("/{alumno_id}/documentos", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
def subir_documento(
    alumno_id: uuid.UUID,
    request: Request,
    tipo: TipoArchivo = Form(),
    archivo: UploadFile = File(),
    actor: Usuario = Depends(requiere("alumnos.editar")),  # el Entrenador, solo en su rama
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> DocumentoOut:
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    doc = documentos.subir(
        db, alumno, tipo=tipo, nombre_original=archivo.filename or "documento", contenido=archivo.file,
        actor=actor, ip=ip_cliente(request), almacen=almacen,
    )
    db.commit()
    return DocumentoOut.model_validate(doc)


@router.get("/{alumno_id}/documentos/{documento_id}/archivo")
def descargar_documento(
    alumno_id: uuid.UUID,
    documento_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(VER_DOCUMENTOS),
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    alumno = _alumno_para_documentos(db, actor, alumno_id)
    doc = documentos.obtener(db, alumno, documento_id)
    datos = documentos.descargar(db, doc, actor=actor, ip=ip_cliente(request), almacen=almacen)
    db.commit()
    return Response(
        datos,
        media_type=doc.mime,
        headers={
            "Content-Disposition": documentos.content_disposition(doc.nombre_original),
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{alumno_id}/documentos/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_documento(
    alumno_id: uuid.UUID,
    documento_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    alumno = servicio.obtener_visible(db, actor, alumno_id)
    clave = documentos.eliminar(db, documentos.obtener(db, alumno, documento_id), actor=actor, ip=ip_cliente(request))
    db.commit()
    almacen.borrar(clave)  # después del commit: si la transacción falla, el archivo sigue ahí
    return Response(status_code=status.HTTP_204_NO_CONTENT)
