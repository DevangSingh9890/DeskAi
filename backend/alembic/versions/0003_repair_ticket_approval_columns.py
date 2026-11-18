"""Repair ticket metadata columns required by ticket creation.

Revision ID: 0003_ticket_cols_fix
Revises: 0002_admin_ticket_operations
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_ticket_cols_fix"
down_revision: str | None = "0002_admin_ticket_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("tickets")
    }
    columns = (
        ("impact", sa.String(length=20)),
        ("ai_recommendation", sa.Text()),
        ("knowledge_sources", sa.JSON()),
        ("similar_incidents", sa.JSON()),
    )
    for column_name, column_type in columns:
        if column_name not in existing_columns:
            op.add_column(
                "tickets",
                sa.Column(column_name, column_type, nullable=True),
            )


def downgrade() -> None:
    pass
