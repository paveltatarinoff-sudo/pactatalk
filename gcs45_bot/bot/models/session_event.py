from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.user import Base


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    role: Mapped[str] = mapped_column(String(16))
    speaker_label: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    dialogue_state_before: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    dialogue_state_after: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    waiting_for_before: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    waiting_for_after: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    next_speaker: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    addressed_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    risk_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
