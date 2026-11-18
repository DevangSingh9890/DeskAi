"""Add admin ticket metadata, comments, and audit history.

Revision ID: 0002_admin_ticket_operations
Revises: e4f8a145a16e
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_admin_ticket_operations"
down_revision: str | None = "e4f8a145a16e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("impact", sa.String(length=20), nullable=True))
    op.add_column("tickets", sa.Column("ai_recommendation", sa.Text(), nullable=True))
    op.add_column(
        "tickets", sa.Column("knowledge_sources", sa.JSON(), nullable=True)
    )
    op.add_column(
        "tickets", sa.Column("similar_incidents", sa.JSON(), nullable=True)
    )

    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=32), nullable=False),
        sa.Column("author", sa.String(length=150), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_comments_ticket_created",
        "ticket_comments",
        ["ticket_id", "created_at"],
    )

    op.create_table(
        "ticket_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=150), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ticket_history_ticket_created",
        "ticket_history",
        ["ticket_id", "created_at"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO ticket_history (ticket_id, event_type, new_value, actor)
            SELECT ticket_id, 'ticket_created', title, created_by
            FROM tickets
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_history_ticket_created", table_name="ticket_history")
    op.drop_table("ticket_history")
    op.drop_index("ix_ticket_comments_ticket_created", table_name="ticket_comments")
    op.drop_table("ticket_comments")
    op.drop_column("tickets", "similar_incidents")
    op.drop_column("tickets", "knowledge_sources")
    op.drop_column("tickets", "ai_recommendation")
    op.drop_column("tickets", "impact")
