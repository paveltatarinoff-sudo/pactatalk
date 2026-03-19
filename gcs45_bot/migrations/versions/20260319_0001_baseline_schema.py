"""baseline schema for current project tables

Revision ID: 20260319_0001
Revises:
Create Date: 2026-03-19 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pair_resumes",
        sa.Column("pair_key", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("name_a", sa.String(length=128), nullable=False),
        sa.Column("name_b", sa.String(length=128), nullable=False),
        sa.Column("resume_context", sa.Text(), nullable=False),
        sa.Column("dialogue_state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("pair_key"),
    )
    op.create_index(op.f("ix_pair_resumes_session_id"), "pair_resumes", ["session_id"], unique=False)

    op.create_table(
        "session_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("speaker_label", sa.String(length=16), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("dialogue_state_before", sa.String(length=32), nullable=True),
        sa.Column("dialogue_state_after", sa.String(length=32), nullable=True),
        sa.Column("waiting_for_before", sa.String(length=16), nullable=True),
        sa.Column("waiting_for_after", sa.String(length=16), nullable=True),
        sa.Column("next_speaker", sa.String(length=16), nullable=True),
        sa.Column("addressed_to", sa.String(length=16), nullable=True),
        sa.Column("risk_flag", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_session_events_created_at"), "session_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_session_events_session_id"), "session_events", ["session_id"], unique=False)

    op.create_table(
        "session_snapshots",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_a_id", sa.BigInteger(), nullable=False),
        sa.Column("user_b_id", sa.BigInteger(), nullable=False),
        sa.Column("dialogue_state", sa.String(length=32), nullable=False),
        sa.Column("waiting_for", sa.String(length=16), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_session_snapshots_user_a_id"), "session_snapshots", ["user_a_id"], unique=False)
    op.create_index(op.f("ix_session_snapshots_user_b_id"), "session_snapshots", ["user_b_id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.String(length=256), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("credits_granted", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payload"),
    )
    op.create_index(op.f("ix_transactions_telegram_id"), "transactions", ["telegram_id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_transactions_telegram_id"), table_name="transactions")
    op.drop_table("transactions")

    op.drop_index(op.f("ix_session_snapshots_user_b_id"), table_name="session_snapshots")
    op.drop_index(op.f("ix_session_snapshots_user_a_id"), table_name="session_snapshots")
    op.drop_table("session_snapshots")

    op.drop_index(op.f("ix_session_events_session_id"), table_name="session_events")
    op.drop_index(op.f("ix_session_events_created_at"), table_name="session_events")
    op.drop_table("session_events")

    op.drop_index(op.f("ix_pair_resumes_session_id"), table_name="pair_resumes")
    op.drop_table("pair_resumes")
