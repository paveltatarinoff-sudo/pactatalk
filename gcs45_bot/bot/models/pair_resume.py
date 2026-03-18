from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.user import Base


class PairResume(Base):
    __tablename__ = "pair_resumes"

    pair_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    name_a: Mapped[str] = mapped_column(String(128), default="")
    name_b: Mapped[str] = mapped_column(String(128), default="")
    resume_context: Mapped[str] = mapped_column(Text)
    dialogue_state: Mapped[str] = mapped_column(String(32), default="SETUP")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def make_pair_key(user_a_id: int, user_b_id: int) -> str:
    """Deterministic pair key from two user IDs (sorted)."""
    lo, hi = sorted([user_a_id, user_b_id])
    return f"{lo}:{hi}"
