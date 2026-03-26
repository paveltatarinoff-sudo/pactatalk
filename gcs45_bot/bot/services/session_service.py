from __future__ import annotations

import html
import random
import string
from datetime import datetime
from typing import Optional

from aiogram import Bot
import structlog

from bot.models.session import SessionState
from bot.repositories.session_repo import SessionRepository

log = structlog.get_logger()
BOT_DIALOG_LABEL = "🤖 Pacta"
PARTICIPANT_DIALOG_ICON = "👤"


def format_bot_dialog_message(text: str) -> str:
    stripped = text.lstrip()
    prefix = f"<b>{BOT_DIALOG_LABEL}</b>"
    if stripped.startswith(prefix):
        return text
    return f"{prefix}\n\n{text}"


def format_participant_dialog_label(name: str) -> str:
    return f"{PARTICIPANT_DIALOG_ICON} {html.escape(name)}"


def format_participant_dialog_block(name: str, text: str) -> str:
    return f"<b>{format_participant_dialog_label(name)}:</b>\n{text}"


def generate_invite_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


class SessionService:
    def __init__(self, repo: SessionRepository, bot: Bot) -> None:
        self._repo = repo
        self._bot = bot

    async def create_session(self, user_a_id: int) -> SessionState:
        """Партнёр A создаёт сессию и получает инвайт-код."""
        code = generate_invite_code()
        # На случай коллизии — перегенерируем
        while await self._repo.get_by_invite(code) is not None:
            code = generate_invite_code()

        session = SessionState(
            user_a_id=user_a_id,
            invite_code=code,
        )
        await self._repo.save(session)
        await self._repo.save_invite(code, session.session_id)
        return session

    async def join_session(self, user_b_id: int, code: str) -> Optional[SessionState]:
        """Партнёр B присоединяется по инвайт-коду."""
        session = await self._repo.get_by_invite(code.upper())
        if session is None:
            return None
        if session.user_b_id != 0:
            return None  # Уже занято
        if session.user_a_id == user_b_id:
            return None  # Нельзя присоединиться к своей же сессии

        session.user_b_id = user_b_id
        await self._repo.save(session)
        await self._repo.delete_invite(code.upper())
        return session

    async def start_session(self, session: SessionState) -> SessionState:
        """Официально стартует сессию (оба партнёра подтвердили)."""
        session.phase = "opening"
        session.mode = "structured"
        session.speaker_turn = "facilitator"
        session.waiting_for = "BOTH"
        session.waiting_since = datetime.utcnow()
        session.timeout_reminders_sent = 0
        session.consecutive_turns = 0
        session.started_at = datetime.utcnow()
        session.elapsed_seconds = 0
        session.dialogue_state = "SETUP"
        session.last_turn_summary = ""
        await self._repo.save(session)
        return session

    async def pass_turn(self, session: SessionState) -> SessionState:
        """Передать слово другому партнёру."""
        new_turn = "B" if session.speaker_turn == "A" else "A"
        session.speaker_turn = new_turn
        session.waiting_for = new_turn  # BUG-PASS-TURN fix: waiting_for controls is_active_speaker
        session.waiting_since = datetime.utcnow()
        session.timeout_reminders_sent = 0
        session.consecutive_turns = 0
        await self._repo.save(session)
        return session

    async def end_session(self, session: SessionState) -> SessionState:
        session.phase = "closing"
        session.mode = "closing"
        await self._repo.save(session)
        return session

    async def notify_both(self, session: SessionState, text: str, **kwargs) -> None:
        """Отправить сообщение обоим партнёрам."""
        payload = format_bot_dialog_message(text)
        for uid in (session.user_a_id, session.user_b_id):
            if uid:
                try:
                    await self._bot.send_message(uid, payload, **kwargs)
                except Exception:
                    log.warning(
                        "notify_both_delivery_failed",
                        session_id=session.session_id,
                        target_user_id=uid,
                    )

    async def get_user_session(self, user_id: int) -> Optional[SessionState]:
        return await self._repo.get_by_user(user_id)
