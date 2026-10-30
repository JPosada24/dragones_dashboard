"""Rifas sin compradores: pagos por talonario, varias jugadas de sorteo, rifas eliminables y motivos opcionales

- Los puestos (con comprador por número) desaparecen: el talonario es del alumno y se paga completo o por abonos
  (`pagos_talonario`). Sus boletas se nombran código-número (F012-07) y entran al sorteo si está pagado al 100 %.
- El sorteo se puede jugar varias veces: cada jugada es un acta (orden 1, 2…) y una boleta no gana dos veces.
- Una rifa se puede "eliminar": deja de verse y de contar, pero su dinero y sus actas se conservan.
- Anular abonos (inscripción, torneos) ya no exige motivo.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-30
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

SIN_MOTIVO = "(anula_id IS NULL AND monto > 0) OR (anula_id IS NOT NULL AND monto < 0)"


def upgrade() -> None:
    conn = op.get_bind()

    # ---------- Motivo opcional al anular abonos ----------
    for tabla in ("pagos_inscripcion", "pagos_equipo"):
        op.drop_constraint(f"ck_{tabla}_monto", tabla, type_="check")
        op.create_check_constraint(f"ck_{tabla}_monto", tabla, SIN_MOTIVO)

    # ---------- Rifas eliminables ----------
    op.drop_constraint("ck_rifas_estado", "rifas", type_="check")
    op.create_check_constraint("ck_rifas_estado", "rifas", "estado IN ('abierta', 'sorteada', 'cancelada', 'eliminada')")
    op.drop_constraint("uq_rifas_anio_numero", "rifas", type_="unique")
    op.create_index("uq_rifas_anio_numero", "rifas", ["anio", "numero"], unique=True,
                    postgresql_where=sa.text("estado <> 'eliminada'"))

    # ---------- Pagos por talonario (antes, por puesto) ----------
    op.create_table(
        "pagos_talonario",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("talonario_id", sa.Uuid(), sa.ForeignKey("talonarios.id"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("monto", sa.Integer(), nullable=False),
        sa.Column("anula_id", sa.Uuid(), sa.ForeignKey("pagos_talonario.id"), unique=True),
        sa.Column("motivo", sa.String(500)),
        sa.Column("registrado_por", sa.Uuid(), sa.ForeignKey("usuarios.id")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(SIN_MOTIVO, name="ck_pagos_talonario_monto"),
    )
    op.create_index("ix_pagos_talonario_talonario_id", "pagos_talonario", ["talonario_id"])
    # Cada pago de puesto pasa a su talonario con el mismo id (así las anulaciones siguen apuntando bien).
    op.execute("""
        INSERT INTO pagos_talonario (id, talonario_id, fecha, monto, anula_id, motivo, registrado_por, creado_en)
        SELECT p.id, u.talonario_id, p.fecha, p.monto, p.anula_id, p.motivo, p.registrado_por, p.creado_en
        FROM pagos_puesto p JOIN puestos u ON u.id = p.puesto_id
        ORDER BY (p.anula_id IS NOT NULL), p.creado_en
    """)
    op.execute("""
        CREATE TRIGGER pagos_talonario_inmutable BEFORE UPDATE OR DELETE ON pagos_talonario
        FOR EACH ROW EXECUTE FUNCTION solo_agregar();
    """)

    # ---------- Actas: varias jugadas por rifa, boleta con código ----------
    op.add_column("actas_sorteo", sa.Column("orden", sa.Integer()))
    op.add_column("actas_sorteo", sa.Column("talonario_id", sa.Uuid(), sa.ForeignKey("talonarios.id")))
    op.add_column("actas_sorteo", sa.Column("codigo", sa.String(8)))
    op.add_column("actas_sorteo", sa.Column("boleta", sa.Integer()))
    # Las actas son de solo agregar: para convertir las que ya existen se suspende el candado un momento.
    op.execute("ALTER TABLE actas_sorteo DISABLE TRIGGER actas_sorteo_inmutable")
    # talonario -> número de su primer puesto (para pasar de número a boleta 1…N)
    primer_puesto = dict(conn.execute(sa.text("SELECT talonario_id, min(numero) FROM puestos GROUP BY talonario_id")).all())
    codigo_de = {  # número de puesto -> (rifa, código-boleta)
        (r, n): f"{c}-{n - primer_puesto[t] + 1:02d}"
        for r, n, t, c in conn.execute(sa.text(
            "SELECT u.rifa_id, u.numero, u.talonario_id, t.codigo FROM puestos u JOIN talonarios t ON t.id = u.talonario_id"
        ))
    }
    actas = conn.execute(sa.text(
        "SELECT a.id, a.rifa_id, a.numero_ganador, a.participantes, u.talonario_id, t.codigo "
        "FROM actas_sorteo a JOIN puestos u ON u.id = a.puesto_id JOIN talonarios t ON t.id = u.talonario_id"
    )).all()
    for a in actas:
        participantes = sorted(codigo_de[(a.rifa_id, n)] for n in a.participantes)
        conn.execute(
            sa.text("UPDATE actas_sorteo SET orden = 1, talonario_id = :t, codigo = :c, boleta = :b, "
                    "participantes = CAST(:p AS jsonb) WHERE id = :id"),
            {"t": a.talonario_id, "c": a.codigo, "b": a.numero_ganador - primer_puesto[a.talonario_id] + 1,
             "p": json.dumps(participantes), "id": a.id},
        )
    # La huella de las actas antiguas se conserva tal cual: certifica la lista con la que se jugó entonces.
    op.execute("ALTER TABLE actas_sorteo ENABLE TRIGGER actas_sorteo_inmutable")
    for col in ("orden", "talonario_id", "codigo", "boleta"):
        op.alter_column("actas_sorteo", col, nullable=False)
    op.drop_constraint("actas_sorteo_rifa_id_key", "actas_sorteo", type_="unique")
    op.create_index("ix_actas_sorteo_rifa_id", "actas_sorteo", ["rifa_id"])
    op.create_unique_constraint("uq_actas_rifa_orden", "actas_sorteo", ["rifa_id", "orden"])
    op.create_unique_constraint("uq_actas_rifa_boleta", "actas_sorteo", ["rifa_id", "codigo", "boleta"])
    op.drop_column("actas_sorteo", "numero_ganador")
    op.drop_column("actas_sorteo", "comprador_nombre")
    op.drop_column("actas_sorteo", "puesto_id")

    # ---------- Fuera los puestos y sus pagos ----------
    op.execute("DROP TRIGGER IF EXISTS pagos_puesto_inmutable ON pagos_puesto")
    op.drop_table("pagos_puesto")
    op.drop_table("puestos")


def downgrade() -> None:
    # Los compradores por puesto y la repartición de pagos por número no se pueden reconstruir.
    raise NotImplementedError("La 0012 no se puede revertir: restaura un respaldo anterior si lo necesitas.")
