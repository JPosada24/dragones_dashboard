"""Alumnos, acudientes, documentos, inscripciones y prórrogas (+ rama del usuario)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Valores fijados aquí a propósito: una migración no debe cambiar si mañana cambia el código.
RAMAS = "('masculina', 'femenina')"
TIPOS_DOCUMENTO = "('RC', 'TI', 'CC', 'CE', 'PA', 'PPT')"


def _tiempos() -> list[sa.Column]:
    return [
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _persona() -> list[sa.Column]:
    return [
        sa.Column("nombres", sa.String(80), nullable=False),
        sa.Column("apellidos", sa.String(80), nullable=False),
        sa.Column("tipo_documento", sa.String(5), nullable=False),
        sa.Column("documento_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("documento_indice", sa.String(64), nullable=False, unique=True),
        sa.Column("documento_ultimos", sa.String(4), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("rama", sa.String(10)))
    op.create_check_constraint("ck_usuarios_rama", "usuarios", f"rama IS NULL OR rama IN {RAMAS}")

    op.create_table(
        "alumnos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_persona(),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=False),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("telefono", sa.String(20)),
        sa.Column("email", sa.String(254)),
        sa.Column("direccion", sa.String(200)),
        sa.Column("eps", sa.String(80)),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id"), unique=True),
        sa.Column("activo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_tiempos(),
        sa.CheckConstraint(f"rama IN {RAMAS}", name="ck_alumnos_rama"),
        sa.CheckConstraint(f"tipo_documento IN {TIPOS_DOCUMENTO}", name="ck_alumnos_tipo_documento"),
    )
    op.create_index("ix_alumnos_rama", "alumnos", ["rama"])

    op.create_table(
        "acudientes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_persona(),
        sa.Column("telefono", sa.String(20), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("usuario_id", sa.Uuid(), sa.ForeignKey("usuarios.id"), unique=True),
        *_tiempos(),
        sa.CheckConstraint(f"tipo_documento IN {TIPOS_DOCUMENTO}", name="ck_acudientes_tipo_documento"),
    )

    op.create_table(
        "alumno_acudiente",
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("acudiente_id", sa.Uuid(), sa.ForeignKey("acudientes.id"), primary_key=True),
        sa.Column("parentesco", sa.String(30), nullable=False),
        sa.Column("principal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "documentos_alumno",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("nombre_original", sa.String(255), nullable=False),
        sa.Column("clave_almacen", sa.String(64), nullable=False, unique=True),
        sa.Column("mime", sa.String(50), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("subido_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('identidad', 'eps', 'consentimiento', 'certificado_medico', 'foto', 'otro')",
            name="ck_documentos_alumno_tipo",
        ),
    )
    op.create_index("ix_documentos_alumno_alumno_id", "documentos_alumno", ["alumno_id"])

    op.create_table(
        "inscripciones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("alumno_id", sa.Uuid(), sa.ForeignKey("alumnos.id"), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("rama", sa.String(10), nullable=False),
        sa.Column("fecha_inscripcion", sa.Date(), nullable=False),
        sa.Column("fecha_limite_pago", sa.Date(), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("fecha_pago", sa.Date()),
        sa.Column("monto_pagado", sa.Integer()),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("causa_rechazo", sa.String(20)),
        sa.Column("motivo", sa.String(255)),
        sa.Column("creado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        *_tiempos(),
        sa.CheckConstraint(
            "estado IN ('pendiente_pago', 'activo', 'a_expulsar', 'expulsado', 'rechazado')",
            name="ck_inscripciones_estado",
        ),
        sa.CheckConstraint(f"rama IN {RAMAS}", name="ck_inscripciones_rama"),
        sa.CheckConstraint(
            "causa_rechazo IS NULL OR causa_rechazo IN ('vencimiento', 'manual')", name="ck_inscripciones_causa"
        ),
        sa.CheckConstraint("fecha_limite_pago >= fecha_inscripcion", name="ck_inscripciones_limite"),
    )
    op.create_index("ix_inscripciones_alumno_id", "inscripciones", ["alumno_id"])
    op.create_index("ix_inscripciones_estado", "inscripciones", ["estado"])
    op.create_index(
        "ux_inscripciones_vigente", "inscripciones", ["alumno_id", "anio"], unique=True,
        postgresql_where=sa.text("estado IN ('pendiente_pago', 'activo', 'a_expulsar')"),
    )

    op.create_table(
        "prorrogas",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("inscripcion_id", sa.Uuid(), sa.ForeignKey("inscripciones.id"), nullable=False),
        sa.Column("limite_anterior", sa.Date(), nullable=False),
        sa.Column("limite_nuevo", sa.Date(), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("concedida_por", sa.Uuid(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("limite_nuevo > limite_anterior", name="ck_prorrogas_limite"),
    )
    op.create_index("ix_prorrogas_inscripcion_id", "prorrogas", ["inscripcion_id"])

    # Las prórrogas son evidencia: igual que la auditoría, no se editan ni se borran.
    op.execute(
        """
        CREATE FUNCTION solo_agregar() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla % es de solo agregar', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER prorrogas_inmutable
        BEFORE UPDATE OR DELETE ON prorrogas
        FOR EACH ROW EXECUTE FUNCTION solo_agregar();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prorrogas_inmutable ON prorrogas")
    op.execute("DROP FUNCTION IF EXISTS solo_agregar()")
    op.drop_table("prorrogas")
    op.drop_table("inscripciones")
    op.drop_table("documentos_alumno")
    op.drop_table("alumno_acudiente")
    op.drop_table("acudientes")
    op.drop_table("alumnos")
    op.drop_constraint("ck_usuarios_rama", "usuarios", type_="check")
    op.drop_column("usuarios", "rama")
