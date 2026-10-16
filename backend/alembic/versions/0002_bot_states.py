"""bot conversation state stored in the database (serverless-safe)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_states",
        sa.Column("key", sa.LargeBinary(length=32), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("bot_states")
