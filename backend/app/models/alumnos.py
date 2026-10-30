import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.dominio import ESTADOS_INSCRIPCION, ESTADOS_VIGENTES, RAMAS, TIPOS_ARCHIVO, TIPOS_DOCUMENTO, en
from app.models.mixins import TiempoMixin, UUIDMixin


class Alumno(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "alumnos"
    __table_args__ = (
        CheckConstraint(en("rama", RAMAS), name="ck_alumnos_rama"),
        CheckConstraint(en("tipo_documento", TIPOS_DOCUMENTO), name="ck_alumnos_tipo_documento"),
        CheckConstraint("codigo ~ '^[FM][0-9]{3,5}$'", name="ck_alumnos_codigo"),
    )

    # F001, F002… (femenina) o M001… (masculina). Lo asigna el sistema; identifica el talonario en el sorteo.
    codigo: Mapped[str] = mapped_column(String(8), unique=True)
    nombres: Mapped[str] = mapped_column(String(80))
    apellidos: Mapped[str] = mapped_column(String(80))
    tipo_documento: Mapped[str] = mapped_column(String(5))
    # El número de documento solo se guarda cifrado; el índice ciego sirve para buscar y evitar duplicados.
    documento_cifrado: Mapped[bytes] = mapped_column(LargeBinary)
    documento_indice: Mapped[str] = mapped_column(String(64), unique=True)
    documento_ultimos: Mapped[str] = mapped_column(String(4))
    fecha_nacimiento: Mapped[date] = mapped_column(Date)
    rama: Mapped[str] = mapped_column(String(10), index=True)
    telefono: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    direccion: Mapped[str | None] = mapped_column(String(200))
    eps: Mapped[str | None] = mapped_column(String(80))
    # Cuenta propia del alumno mayor de edad (rol Miembro).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    vinculos: Mapped[list["AlumnoAcudiente"]] = relationship(
        back_populates="alumno", lazy="selectin", cascade="all, delete-orphan"
    )


class Acudiente(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "acudientes"
    __table_args__ = (CheckConstraint(en("tipo_documento", TIPOS_DOCUMENTO), name="ck_acudientes_tipo_documento"),)

    nombres: Mapped[str] = mapped_column(String(80))
    apellidos: Mapped[str] = mapped_column(String(80))
    tipo_documento: Mapped[str] = mapped_column(String(5))
    documento_cifrado: Mapped[bytes] = mapped_column(LargeBinary)
    documento_indice: Mapped[str] = mapped_column(String(64), unique=True)
    documento_ultimos: Mapped[str] = mapped_column(String(4))
    telefono: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    # Cuenta del acudiente (rol Miembro): con ella ve e inscribe a sus hijos.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"), unique=True)


class AlumnoAcudiente(Base):
    __tablename__ = "alumno_acudiente"

    alumno_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("alumnos.id", ondelete="CASCADE"), primary_key=True
    )
    acudiente_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("acudientes.id"), primary_key=True)
    parentesco: Mapped[str] = mapped_column(String(30))
    principal: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    alumno: Mapped[Alumno] = relationship(back_populates="vinculos")
    acudiente: Mapped[Acudiente] = relationship(lazy="joined")


class DocumentoAlumno(UUIDMixin, Base):
    """Archivo adjunto del alumno. El contenido vive cifrado en el almacén, nunca en una carpeta pública."""

    __tablename__ = "documentos_alumno"
    __table_args__ = (CheckConstraint(en("tipo", TIPOS_ARCHIVO), name="ck_documentos_alumno_tipo"),)

    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    nombre_original: Mapped[str] = mapped_column(String(255))
    clave_almacen: Mapped[str] = mapped_column(String(64), unique=True)
    mime: Mapped[str] = mapped_column(String(50))
    tamano: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    subido_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Inscripcion(UUIDMixin, TiempoMixin, Base):
    __tablename__ = "inscripciones"
    __table_args__ = (
        CheckConstraint(en("estado", ESTADOS_INSCRIPCION), name="ck_inscripciones_estado"),
        CheckConstraint(en("rama", RAMAS), name="ck_inscripciones_rama"),
        CheckConstraint(
            "causa_rechazo IS NULL OR causa_rechazo IN ('vencimiento', 'manual')", name="ck_inscripciones_causa"
        ),
        CheckConstraint("fecha_limite_pago >= fecha_inscripcion", name="ck_inscripciones_limite"),
        CheckConstraint(
            "causa_expulsion IS NULL OR causa_expulsion IN ('mora', 'manual')", name="ck_inscripciones_causa_expulsion"
        ),
        # Un alumno solo puede tener una inscripción vigente por año.
        Index(
            "ux_inscripciones_vigente", "alumno_id", "anio", unique=True,
            postgresql_where=text(en("estado", ESTADOS_VIGENTES)),
        ),
    )

    alumno_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alumnos.id"), index=True)
    anio: Mapped[int] = mapped_column(Integer)
    rama: Mapped[str] = mapped_column(String(10))
    fecha_inscripcion: Mapped[date] = mapped_column(Date)
    # Se fija al inscribir con el plazo vigente en "configuracion"; solo una prórroga la cambia.
    fecha_limite_pago: Mapped[date] = mapped_column(Date)
    valor: Mapped[int] = mapped_column(Integer)
    fecha_pago: Mapped[date | None] = mapped_column(Date)  # fecha en que se completó el valor
    monto_pagado: Mapped[int | None] = mapped_column(Integer)  # suma de los abonos
    estado: Mapped[str] = mapped_column(String(20), index=True, default="pendiente_pago")
    causa_rechazo: Mapped[str | None] = mapped_column(String(20))
    # Por qué está "a expulsar"/"expulsado": "mora" (lo marcó el sistema; sale solo al pagar) o "manual".
    causa_expulsion: Mapped[str | None] = mapped_column(String(10))
    motivo: Mapped[str | None] = mapped_column(String(255))
    creado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))

    alumno: Mapped[Alumno] = relationship(lazy="joined")
    prorrogas: Mapped[list["Prorroga"]] = relationship(lazy="selectin", order_by="Prorroga.creado_en")
    pagos: Mapped[list["PagoInscripcion"]] = relationship(lazy="selectin", order_by="PagoInscripcion.creado_en")

    @property
    def saldo(self) -> int:
        return self.valor - (self.monto_pagado or 0)


class PagoInscripcion(UUIDMixin, Base):
    """Abono a una inscripción (se aceptan pagos parciales). Es de solo agregar (trigger en PostgreSQL).

    Un abono mal registrado no se borra: se anula con otra fila de monto negativo que apunta a él (`anula_id`).
    """

    __tablename__ = "pagos_inscripcion"
    __table_args__ = (
        CheckConstraint(
            "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0 AND motivo IS NOT NULL)",
            name="ck_pagos_inscripcion_monto",
        ),
    )

    inscripcion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("inscripciones.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[int] = mapped_column(Integer)
    anula_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("pagos_inscripcion.id"), unique=True)
    motivo: Mapped[str | None] = mapped_column(String(500))
    registrado_por: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Prorroga(UUIDMixin, Base):
    """Ampliación del plazo de pago. Es de solo agregar (trigger en PostgreSQL)."""

    __tablename__ = "prorrogas"
    __table_args__ = (CheckConstraint("limite_nuevo > limite_anterior", name="ck_prorrogas_limite"),)

    inscripcion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("inscripciones.id"), index=True)
    limite_anterior: Mapped[date] = mapped_column(Date)
    limite_nuevo: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String(500))
    concedida_por: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
