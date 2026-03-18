from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional
import uuid


@dataclass
class SessionState:
    # Идентификация
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_a_id: int = 0
    user_b_id: int = 0
    chat_id: int = 0

    # Имена участников
    name_a: str = ""
    name_b: str = ""

    # Цели сессии
    goal_a: str = ""
    goal_b: str = ""
    goal_joint: str = ""

    # Текущий контекст
    topic_current: str = ""
    speaker_turn: Literal["A", "B", "facilitator"] = "facilitator"
    resume_context: str = ""  # Resume brief from previous session (if any)

    # State machine (signal-based, не time-based)
    # SETUP | CLARIFY | DEESCALATE | DEEPEN | OPTIONS | AGREE | CHECK_IN
    dialogue_state: str = "SETUP"
    last_turn_summary: str = ""  # краткое резюме последнего хода для async context

    # Заметки фасилитатора (метаданные, не цитаты)
    notes_a: list[str] = field(default_factory=list)
    notes_b: list[str] = field(default_factory=list)

    # Режим и фаза
    mode: Literal["structured", "free", "pause", "closing"] = "structured"
    phase: Literal["opening", "exploration", "deepening", "agreement", "closing"] = "opening"

    # Безопасность
    risk_flag: bool = False
    risk_details: str = ""

    # Временные метки
    started_at: datetime = field(default_factory=datetime.utcnow)
    paused_at: Optional[datetime] = None
    elapsed_seconds: int = 0

    # Приватность
    ephemeral_mode: bool = True
    summary_opt_in: bool = False

    # Invite code (для relay mode)
    invite_code: str = ""

    # ID первого сообщения сессии (для диапазонного удаления)
    first_msg_id_a: int = 0
    first_msg_id_b: int = 0

    # Управление очерёдностью (расширенная логика)
    # "A", "B" — слово у конкретного партнёра; "BOTH" — ждём ответа от обоих
    waiting_for: str = "A"
    # Счётчик: сколько раз подряд бот обратился к одному партнёру (макс. 3)
    consecutive_turns: int = 0
    # Буферы ответов в режиме BOTH
    pending_a_message: str = ""
    pending_b_message: str = ""
    # Время начала ожидания текущего ответа
    waiting_since: datetime = field(default_factory=datetime.utcnow)
    # Сколько напоминаний уже было отправлено на текущем ходе
    timeout_reminders_sent: int = 0

    def elapsed_minutes(self) -> int:
        if self.mode == "pause" and self.paused_at:
            return self.elapsed_seconds // 60
        delta = datetime.utcnow() - self.started_at
        return (self.elapsed_seconds + int(delta.total_seconds())) // 60

    def response_deadline_exceeded(self, timeout_seconds: int) -> bool:
        return (datetime.utcnow() - self.waiting_since).total_seconds() >= timeout_seconds

    def partner_name(self, user_id: int) -> Literal["A", "B"] | None:
        if user_id == self.user_a_id:
            return "A"
        if user_id == self.user_b_id:
            return "B"
        return None

    def is_active_speaker(self, user_id: int) -> bool:
        partner = self.partner_name(user_id)
        if partner is None:
            return False
        if self.waiting_for == "BOTH":
            return True  # оба партнёра могут писать одновременно
        return self.waiting_for == partner
