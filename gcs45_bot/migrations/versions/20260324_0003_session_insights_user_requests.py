"""session_insights and user_requests tables

Revision ID: 20260324_0003
Revises: 20260319_0001
Create Date: 2026-03-24 00:00:00

Reconstructed 2026-10-16: the original revision files (0002/0003) were never
committed to git and were lost from disk; production is stamped 20260324_0003.
This single revision recreates the full delta between the committed baseline
and the stamped head, with DDL verified column-by-column against the live
production schema. On production `upgrade head` is a no-op; a fresh database
gets the complete schema.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260324_0003"
down_revision = "20260319_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_insights",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_a_id", sa.BigInteger(), nullable=False),
        sa.Column("user_b_id", sa.BigInteger(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("clarified_text", sa.Text(), nullable=False),
        sa.Column("agreement_text", sa.Text(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_session_insights_user_a_id"), "session_insights", ["user_a_id"], unique=False)
    op.create_index(op.f("ix_session_insights_user_b_id"), "session_insights", ["user_b_id"], unique=False)

    op.create_table(
        "user_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("admin_reply_text", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_requests_created_at"), "user_requests", ["created_at"], unique=False)
    op.create_index(op.f("ix_user_requests_kind"), "user_requests", ["kind"], unique=False)
    op.create_index(op.f("ix_user_requests_session_id"), "user_requests", ["session_id"], unique=False)
    op.create_index(op.f("ix_user_requests_telegram_id"), "user_requests", ["telegram_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_requests_telegram_id"), table_name="user_requests")
    op.drop_index(op.f("ix_user_requests_session_id"), table_name="user_requests")
    op.drop_index(op.f("ix_user_requests_kind"), table_name="user_requests")
    op.drop_index(op.f("ix_user_requests_created_at"), table_name="user_requests")
    op.drop_table("user_requests")

    op.drop_index(op.f("ix_session_insights_user_b_id"), table_name="session_insights")
    op.drop_index(op.f("ix_session_insights_user_a_id"), table_name="session_insights")
    op.drop_table("session_insights")
