"""Create persistent tickets and approvals.

Revision ID: 0001_ticket_persistence
Revises:
Create Date: 2026-11-16
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from alembic import context

revision: str = "0001_ticket_persistence"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL NOT NULL PRIMARY KEY,
                ticket_id VARCHAR(32) NOT NULL UNIQUE,
                title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                category VARCHAR(100) NOT NULL,
                subcategory VARCHAR(100) NOT NULL,
                priority VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'Open',
                assigned_group VARCHAR(150) NOT NULL,
                created_by VARCHAR(150) NOT NULL DEFAULT 'user',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                resolution TEXT
            )"""
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_tickets_ticket_id ON tickets (ticket_id)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_tickets_priority_status "
            "ON tickets (priority, status)"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_tickets_category_priority "
            "ON tickets (category, priority)"
        )
        op.execute(
            """CREATE TABLE IF NOT EXISTS ticket_approvals (
                approval_id VARCHAR(100) NOT NULL PRIMARY KEY,
                message TEXT NOT NULL,
                ticket_data JSON NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL
            )"""
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_ticket_approvals_expires_at "
            "ON ticket_approvals (expires_at)"
        )
        return

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "tickets" not in tables:
        op.create_table(
            "tickets",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("ticket_id", sa.String(length=32), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("subcategory", sa.String(length=100), nullable=False),
            sa.Column("priority", sa.String(length=20), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default="Open",
                nullable=False,
            ),
            sa.Column("assigned_group", sa.String(length=150), nullable=False),
            sa.Column(
                "created_by",
                sa.String(length=150),
                server_default="user",
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("resolution", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("ticket_id"),
        )

    ticket_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("tickets")
    }
    if "ix_tickets_ticket_id" not in ticket_indexes:
        op.create_index("ix_tickets_ticket_id", "tickets", ["ticket_id"])
    if "ix_tickets_priority_status" not in ticket_indexes:
        op.create_index(
            "ix_tickets_priority_status",
            "tickets",
            ["priority", "status"],
        )
    if "ix_tickets_category_priority" not in ticket_indexes:
        op.create_index(
            "ix_tickets_category_priority",
            "tickets",
            ["category", "priority"],
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "ticket_approvals" not in tables:
        op.create_table(
            "ticket_approvals",
            sa.Column("approval_id", sa.String(length=100), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("ticket_data", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("approval_id"),
        )

    approval_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("ticket_approvals")
    }
    if "ix_ticket_approvals_expires_at" not in approval_indexes:
        op.create_index(
            "ix_ticket_approvals_expires_at",
            "ticket_approvals",
            ["expires_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_ticket_approvals_expires_at", table_name="ticket_approvals")
    op.drop_table("ticket_approvals")
    op.drop_index("ix_tickets_category_priority", table_name="tickets")
    op.drop_index("ix_tickets_priority_status", table_name="tickets")
    op.drop_index("ix_tickets_ticket_id", table_name="tickets")
    op.drop_table("tickets")
