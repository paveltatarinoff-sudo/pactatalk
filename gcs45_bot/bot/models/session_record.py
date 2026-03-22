from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Text, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.user import Base


class SessionSnapshot(Base):
    __tablename__ = "session_snapshots"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_a_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_b_id: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    dialogue_state: Mapped[str] = mapped_column(String(32), default="SETUP")
    waiting_for: Mapped[str] = mapped_column(String(16), default="A")
    phase: Mapped[str] = mapped_column(String(32), default="opening")
    mode: Mapped[str] = mapped_column(String(32), default="structured")
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
