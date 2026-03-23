from __future__ import annotations

import asyncio

from bot.handlers import facilitator
from bot.handlers import session as session_handler
from bot.models.session import SessionState


def _session(waiting_for: str = "A") -> SessionState:
    return SessionState(
        session_id="end-flow-test",
        user_a_id=1,
        user_b_id=2,
        name_a="Pasha",
        name_b="Lyuda",
        waiting_for=waiting_for,
        dialogue_state="DEEPEN",
    )


class _RepoStub:
    def __init__(self, session: SessionState | None = None) -> None:
        self.session = session
        self.saved_sessions: list[SessionState] = []
        self.events: list[dict] = []

    async def get_by_user(self, user_id: int) -> SessionState | None:
        return self.session

    async def get(self, session_id: str) -> SessionState | None:
        return self.session

    async def save(self, session: SessionState) -> None:
        self.session = session
        self.saved_sessions.append(session)

    async def append_event(self, **kwargs) -> None:
        self.events.append(kwargs)


class _BotStub:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str, object]] = []
        self.chat_actions: list[tuple[int, str]] = []

    async def send_message(self, user_id: int, text: str, reply_markup=None) -> None:
        self.sent_messages.append((user_id, text, reply_markup))

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.chat_actions.append((chat_id, action))


class _MessageStub:
    def __init__(self, *, user_id: int, text: str, chat_id: int = 100) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.chat = type("Chat", (), {"id": chat_id})()
        self.text = text
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _CallbackMessageStub:
    def __init__(self) -> None:
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class _CallbackStub:
    def __init__(self, user_id: int) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.message = _CallbackMessageStub()
        self.answered = False

    async def answer(self, *args, **kwargs) -> None:
        self.answered = True


def test_end_intent_prompts_both_and_sets_pending_even_out_of_turn(monkeypatch) -> None:
    session = _session(waiting_for="A")
    repo = _RepoStub(session)
    bot = _BotStub()
    message = _MessageStub(user_id=2, text="давай закончим")

    monkeypatch.setattr(facilitator, "SessionRepository", lambda redis, session_factory: repo)

    asyncio.run(
        facilitator.handle_session_message(
            message=message,
            bot=bot,
            redis=None,
            session_factory=None,
            state=None,
        )
    )

    assert session.close_confirmation_pending is True
    assert len(bot.sent_messages) == 2
    assert all("Готовы закончить разговор" in text for _, text, _ in bot.sent_messages)
    assert all(reply_markup is None for _, _, reply_markup in bot.sent_messages)


def test_reply_extras_no_longer_adds_finish_button_in_regular_flow() -> None:
    session = _session()

    signature, keyboard = facilitator._reply_extras(session)

    assert "теперь твой ход" in signature
    assert keyboard is None


def test_yes_after_pending_shows_finish_buttons(monkeypatch) -> None:
    session = _session(waiting_for="A")
    session.close_confirmation_pending = True
    repo = _RepoStub(session)
    bot = _BotStub()
    message = _MessageStub(user_id=1, text="да")

    monkeypatch.setattr(facilitator, "SessionRepository", lambda redis, session_factory: repo)

    asyncio.run(
        facilitator.handle_session_message(
            message=message,
            bot=bot,
            redis=None,
            session_factory=None,
            state=None,
        )
    )

    assert session.close_confirmation_pending is False
    assert len(bot.sent_messages) == 2
    assert all("нажмите кнопку ниже" in text for _, text, _ in bot.sent_messages)
    assert all(reply_markup is not None for _, _, reply_markup in bot.sent_messages)


def test_no_after_pending_cancels_finish_flow(monkeypatch) -> None:
    session = _session(waiting_for="A")
    session.close_confirmation_pending = True
    repo = _RepoStub(session)
    bot = _BotStub()
    message = _MessageStub(user_id=2, text="нет")

    monkeypatch.setattr(facilitator, "SessionRepository", lambda redis, session_factory: repo)

    asyncio.run(
        facilitator.handle_session_message(
            message=message,
            bot=bot,
            redis=None,
            session_factory=None,
            state=None,
        )
    )

    assert session.close_confirmation_pending is False
    assert len(bot.sent_messages) == 2
    assert all("Сессию не завершаю" in text for _, text, _ in bot.sent_messages)
    assert all(reply_markup is None for _, _, reply_markup in bot.sent_messages)


def test_end_session_command_enters_confirmation_flow(monkeypatch) -> None:
    session = _session()
    repo = _RepoStub(session)
    bot = _BotStub()
    message = _MessageStub(user_id=1, text="/end_session")

    monkeypatch.setattr(session_handler, "SessionRepository", lambda redis, session_factory: repo)

    asyncio.run(
        session_handler.cmd_end_session(
            message=message,
            bot=bot,
            redis=None,
            session_factory=None,
            state=None,
        )
    )

    assert session.close_confirmation_pending is True
    assert len(bot.sent_messages) == 2
    assert all("Готовы закончить разговор" in text for _, text, _ in bot.sent_messages)


def test_continue_callback_clears_pending_close_confirmation(monkeypatch) -> None:
    session = _session()
    session.close_confirmation_pending = True
    repo = _RepoStub(session)
    bot = _BotStub()
    callback = _CallbackStub(user_id=1)

    monkeypatch.setattr(session_handler, "SessionRepository", lambda redis, session_factory: repo)

    asyncio.run(
        session_handler.cb_continue_session(
            callback=callback,
            bot=bot,
            redis=None,
            session_factory=None,
        )
    )

    assert session.close_confirmation_pending is False
    assert callback.message.deleted is True
    assert callback.answered is True
    assert len(bot.sent_messages) == 2
    assert all("не завершаю" in text for _, text, _ in bot.sent_messages)
