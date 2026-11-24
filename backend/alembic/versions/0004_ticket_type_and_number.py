"""Add separate ticket type and display number fields.

Revision ID: 0004_ticket_type_number
Revises: 0003_ticket_cols_fix
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_ticket_type_number"
down_revision: str | None = "0003_ticket_cols_fix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("tickets")}
    if "ticket_type" not in columns:
        op.add_column(
            "tickets",
            sa.Column("ticket_type", sa.String(length=20), nullable=True),
        )
        op.create_index("ix_tickets_ticket_type", "tickets", ["ticket_type"])
    if "ticket_number" not in columns:
        op.add_column(
            "tickets",
            sa.Column("ticket_number", sa.String(length=32), nullable=True),
        )
        op.create_index(
            "ix_tickets_ticket_number",
            "tickets",
            ["ticket_number"],
            unique=True,
        )

    op.execute(
        sa.text(
            """
            UPDATE tickets
            SET ticket_number = ticket_id
            WHERE ticket_number IS NULL
              AND (
                  ticket_id LIKE 'INC-%'
                  OR ticket_id LIKE 'SR-%'
                  OR ticket_id LIKE 'HUM-%'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE tickets
            SET ticket_type = CASE
                WHEN LOWER(COALESCE(category, '')) = 'access management'
                  OR LOWER(COALESCE(title, '') || ' ' || COALESCE(description, '') || ' ' ||
                    COALESCE(subcategory, '') || ' ' || COALESCE(ai_recommendation, ''))
                    LIKE '%password reset%' OR
                    LOWER(COALESCE(title, '') || ' ' || COALESCE(description, '') || ' ' ||
                    COALESCE(category, '') || ' ' || COALESCE(subcategory, '') || ' ' ||
                    COALESCE(ai_recommendation, ''))
                    LIKE '%install%' OR
                    LOWER(COALESCE(title, '') || ' ' || COALESCE(description, '') || ' ' ||
                    COALESCE(category, '') || ' ' || COALESCE(subcategory, '') || ' ' ||
                    COALESCE(ai_recommendation, ''))
                    LIKE '%request%' OR
                    LOWER(COALESCE(title, '') || ' ' || COALESCE(description, '') || ' ' ||
                    COALESCE(category, '') || ' ' || COALESCE(subcategory, '') || ' ' ||
                    COALESCE(ai_recommendation, ''))
                    LIKE '%access%' OR
                    LOWER(COALESCE(title, '') || ' ' || COALESCE(description, '') || ' ' ||
                    COALESCE(category, '') || ' ' || COALESCE(subcategory, '') || ' ' ||
                    COALESCE(ai_recommendation, ''))
                    LIKE '%permission%'
                THEN 'service_request'
                ELSE 'incident'
            END
            WHERE ticket_type IS NULL
              AND ticket_id NOT LIKE 'HUM-%'
            """
        )
    )

    if not sa.inspect(bind).has_table("ticket_sequences"):
        op.create_table(
            "ticket_sequences",
            sa.Column("ticket_type", sa.String(length=20), nullable=False),
            sa.Column(
                "last_number",
                sa.Integer(),
                server_default="0",
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("ticket_type"),
        )
        op.execute(
            "INSERT INTO ticket_sequences (ticket_type, last_number) "
            "VALUES ('incident', 0), ('service_request', 0)"
        )

def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("ticket_sequences"):
        op.drop_table("ticket_sequences")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("tickets")}
    if "ticket_number" in columns:
        op.drop_index("ix_tickets_ticket_number", table_name="tickets")
        op.drop_column("tickets", "ticket_number")
    if "ticket_type" in columns:
        op.drop_index("ix_tickets_ticket_type", table_name="tickets")
        op.drop_column("tickets", "ticket_type")
