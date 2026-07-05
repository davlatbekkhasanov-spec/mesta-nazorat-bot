"""add work_sessions.work_type

Revision ID: 004
Revises: 003
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "work_sessions",
        sa.Column(
            "work_type",
            sa.String(32),
            nullable=False,
            server_default="inventarizatsiya",
        ),
    )


def downgrade() -> None:
    op.drop_column("work_sessions", "work_type")
