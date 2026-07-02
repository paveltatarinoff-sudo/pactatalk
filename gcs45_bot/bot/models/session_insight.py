from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.user import Base


class SessionInsight(Base):
    __tablename__ = "session_insights"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_a_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_b_id: Mapped[int] = mapped_column(BigInteger, index=True)
    topic: Mapped[str] = mapped_column(String(160), default="")
    clarified_text: Mapped[str] = mapped_column(Text, default="")
    agreement_text: Mapped[str] = mapped_column(Text, default="")
    summary_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
