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

    async def save_session_insight(self, **kwargs) -> None:
        self.events.append({"insight": kwargs})

    async def save_pair_resume(self, session: SessionState, resume_ctx: str) -> None:
        self.events.append({"resume_ctx": resume_ctx})

    async def delete_history(self, session_id: str) -> None:
        self.events.append({"deleted_history": session_id})

    async def delete(self, session: SessionState) -> None:
        self.session = None
        self.events.append({"deleted_session": session.session_id})


class _BotStub:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str, object]] = []
        self.chat_actions: list[tuple[int, str]] = []
        self.edited_markups: list[tuple[int, int, object]] = []

    async def send_message(self, user_id: int, text: str, reply_markup=None) -> None:
        self.sent_messages.append((user_id, text, reply_markup))

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.chat_actions.append((chat_id, action))

    async def edit_message_reply_markup(self, chat_id: int, message_id: int, reply_markup=None) -> None:
        self.edited_markups.append((chat_id, message_id, reply_markup))

    async def get_file(self, file_id: str):
        return type("File", (), {"file_path": f"voice/{file_id}.ogg"})()

    async def download_file(self, file_path: str, buf) -> None:
        buf.write(b"voice")


class _MessageStub:
    def __init__(self, *, user_id: int, text: str, chat_id: int = 100) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.chat = type("Chat", (), {"id": chat_id})()
        self.text = text
        self.answers: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append((text, reply_markup))


class _VoiceMessageStub(_MessageStub):
    def __init__(self, *, user_id: int, chat_id: int = 100, file_id: str = "voice-file") -> None:
        super().__init__(user_id=user_id, text="", chat_id=chat_id)
        self.voice = type("Voice", (), {"file_id": file_id})()


class _CallbackMessageStub:
    def __init__(self) -> None:
        self.deleted = False
        self.reply_markup = object()
        self.answers: list[str] = []
        self.chat = type("Chat", (), {"id": 100})()
        self.message_id = 1

    async def delete(self) -> None:
        self.deleted = True

    async def edit_reply_markup(self, reply_markup=None) -> None:
        self.reply_markup = reply_markup

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append(text)


class _CallbackStub:
    def __init__(self, user_id: int) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.message = _CallbackMessageStub()
        self.answered = False
        self.answer_kwargs: list[dict] = []

    async def answer(self, *args, **kwargs) -> None:
        self.answered = True
        self.answer_kwargs.append(kwargs)


class _RedisStub:
    def __init__(self) -> None:
        self.kv: dict[str, object] = {}

    async def set(self, key: str, value, ex=None, nx=None) -> bool:
        self.kv[key] = value
        return True

    async def get(self, key: str):
        return self.kv.get(key)


class _StateStub:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def test_end_intent_shows_direct_finish_button_even_out_of_turn(monkeypatch) -> None:
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

    assert session.close_confirmation_pending is False
    assert session.close_choice_active is True
    assert len(bot.sent_messages) == 2
    assert all("хотите закончить разговор" in text for _, text, _ in bot.sent_messages)
    assert all(reply_markup is not None for _, _, reply_markup in bot.sent_messages)


def test_second_text_end_intent_does_not_duplicate_finish_buttons(monkeypatch) -> None:
    session = _session(waiting_for="A")
    session.close_choice_active = True
    repo = _RepoStub(session)
    bot = _BotStub()
    message = _MessageStub(user_id=2, text="закончить сессию")

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

    assert bot.sent_messages == []
    assert message.answers
    assert "Кнопка завершения уже открыта" in message.answers[0][0]


def test_text_pause_and_continue_later_opens_finish_button(monkeypatch) -> None:
    session = _session(waiting_for="A")
    repo = _RepoStub(session)
    bot = _BotStub()
    message = _MessageStub(user_id=2, text="Сейчас не могу, давай продолжим позже.")

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

    assert session.close_choice_active is True
    assert len(bot.sent_messages) == 2
    assert all("хотите закончить разговор" in text for _, text, _ in bot.sent_messages)


def test_voice_end_intent_shows_direct_finish_button(monkeypatch) -> None:
    async def scenario() -> None:
        session = _session(waiting_for="A")
        repo = _RepoStub(session)
        bot = _BotStub()
        message = _VoiceMessageStub(user_id=2)
        redis = _RedisStub()
        process_called = False

        async def fake_transcribe_voice(_: bytes) -> str:
            return "Мне неудобно сейчас, я хотел бы завершить сессию."

        async def fake_process_turn(**kwargs) -> None:
            nonlocal process_called
            process_called = True

        monkeypatch.setattr(facilitator, "SessionRepository", lambda redis, session_factory: repo)
        monkeypatch.setattr(facilitator._claude, "transcribe_voice", fake_transcribe_voice)
        monkeypatch.setattr(facilitator, "_process_turn", fake_process_turn)

        await facilitator.handle_voice_message(
            message=message,
            bot=bot,
            redis=redis,
            session_factory=None,
            state=None,
        )

        assert session.close_choice_active is True
        assert process_called is False
        assert message.answers
        assert "🎤 <i>Мне неудобно сейчас, я хотел бы завершить сессию.</i>" == message.answers[0][0]
        assert len(bot.sent_messages) == 2
        assert all("хотите закончить разговор" in text for _, text, _ in bot.sent_messages)
        assert all(reply_markup is not None for _, _, reply_markup in bot.sent_messages)

    asyncio.run(scenario())


def test_voice_continue_later_intent_shows_direct_finish_button(monkeypatch) -> None:
    async def scenario() -> None:
        session = _session(waiting_for="A")
        repo = _RepoStub(session)
        bot = _BotStub()
        message = _VoiceMessageStub(user_id=2)
        redis = _RedisStub()
        process_called = False

        async def fake_transcribe_voice(_: bytes) -> str:
            return "Мне неудобно сейчас, давай продолжим позже."

        async def fake_process_turn(**kwargs) -> None:
            nonlocal process_called
            process_called = True

        monkeypatch.setattr(facilitator, "SessionRepository", lambda redis, session_factory: repo)
        monkeypatch.setattr(facilitator._claude, "transcribe_voice", fake_transcribe_voice)
        monkeypatch.setattr(facilitator, "_process_turn", fake_process_turn)

        await facilitator.handle_voice_message(
            message=message,
            bot=bot,
            redis=redis,
            session_factory=None,
            state=None,
        )

        assert session.close_choice_active is True
        assert process_called is False
        assert len(bot.sent_messages) == 2
        assert all("хотите закончить разговор" in text for _, text, _ in bot.sent_messages)

    asyncio.run(scenario())


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
    assert session.close_choice_active is True
    assert len(bot.sent_messages) == 2
    assert all("открыл завершение сессии" in text for _, text, _ in bot.sent_messages)
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

    assert session.close_confirmation_pending is False
    assert session.close_choice_active is True
    assert len(bot.sent_messages) == 2
    assert all("открыл завершение сессии" in text for _, text, _ in bot.sent_messages)


def test_first_continue_callback_waits_for_second_partner(monkeypatch) -> None:
    session = _session()
    session.close_choice_active = True
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

    assert session.close_choice_active is True
    assert session.close_continue_votes == "A"
    assert callback.message.reply_markup is None
    assert callback.answered is True
    assert callback.message.answers
    assert "Если второй партнёр тоже выберет" in callback.message.answers[0]


def test_second_continue_callback_resumes_session(monkeypatch) -> None:
    session = _session()
    session.close_choice_active = True
    session.close_continue_votes = "A"
    session.close_choice_msg_id_a = 11
    session.close_choice_msg_id_b = 22
    repo = _RepoStub(session)
    bot = _BotStub()
    callback = _CallbackStub(user_id=2)

    monkeypatch.setattr(session_handler, "SessionRepository", lambda redis, session_factory: repo)

    asyncio.run(
        session_handler.cb_continue_session(
            callback=callback,
            bot=bot,
            redis=None,
            session_factory=None,
        )
    )

    assert session.close_choice_active is False
    assert session.close_continue_votes == ""
    assert callback.answered is True
    assert len(bot.sent_messages) == 2
    assert all("Оба выбрали продолжить разговор" in text for _, text, _ in bot.sent_messages)


def test_end_session_sends_single_summary_message(monkeypatch) -> None:
    async def scenario() -> None:
        session = _session()
        repo = _RepoStub(session)
        bot = _BotStub()
        callback = _CallbackStub(user_id=1)
        redis = _RedisStub()
        state = _StateStub()

        async def fake_generate_session_insight(session_obj, repo_obj):
            return {
                "topic": "Переезд",
                "clarified_text": "Прояснили ограничения по документам и срокам.",
                "agreement_text": "Договорились вернуться к теме позже.",
                "summary_text": "Прояснили ограничения по документам и срокам.",
            }

        async def fake_generate_resume_context(session_obj, repo_obj):
            return ""

        monkeypatch.setattr(session_handler, "SessionRepository", lambda redis, session_factory: repo)
        monkeypatch.setattr(session_handler, "CallbackQuery", _CallbackStub)
        monkeypatch.setattr(session_handler._claude, "generate_session_insight", fake_generate_session_insight)
        monkeypatch.setattr(session_handler._claude, "generate_resume_context", fake_generate_resume_context)
        monkeypatch.setattr(session_handler.settings, "post_session_survey_url", "")

        await session_handler.cb_end_session(
            event=callback,
            bot=bot,
            redis=redis,
            session_factory=None,
            state=state,
        )

        assert callback.answered is True
        assert state.cleared is True
        assert callback.message.deleted is True
        assert len(bot.sent_messages) == 2
        assert all("Краткий итог разговора" in text for _, text, _ in bot.sent_messages)
        assert all("Мои итоги" in text for _, text, _ in bot.sent_messages)
        assert all("6 коротких вопросов" not in text for _, text, _ in bot.sent_messages)
        assert all(reply_markup is None for _, _, reply_markup in bot.sent_messages)

    asyncio.run(scenario())


def test_end_session_adds_personalized_survey_links_when_configured(monkeypatch) -> None:
    async def scenario() -> None:
        session = _session()
        repo = _RepoStub(session)
        bot = _BotStub()
        callback = _CallbackStub(user_id=1)
        redis = _RedisStub()
        state = _StateStub()

        async def fake_generate_session_insight(session_obj, repo_obj):
            return {
                "topic": "Переезд",
                "clarified_text": "Прояснили ограничения по документам и срокам.",
                "agreement_text": "Договорились вернуться к теме позже.",
                "summary_text": "Прояснили ограничения по документам и срокам.",
            }

        async def fake_generate_resume_context(session_obj, repo_obj):
            return ""

        monkeypatch.setattr(session_handler, "SessionRepository", lambda redis, session_factory: repo)
        monkeypatch.setattr(session_handler, "CallbackQuery", _CallbackStub)
        monkeypatch.setattr(session_handler._claude, "generate_session_insight", fake_generate_session_insight)
        monkeypatch.setattr(session_handler._claude, "generate_resume_context", fake_generate_resume_context)
        monkeypatch.setattr(
            session_handler.settings,
            "post_session_survey_url",
            "https://tally.so/r/test-form?utm_source=bot",
        )

        await session_handler.cb_end_session(
            event=callback,
            bot=bot,
            redis=redis,
            session_factory=None,
            state=state,
        )

        first_markup = bot.sent_messages[0][2]
        second_markup = bot.sent_messages[1][2]
        first_button = first_markup.inline_keyboard[0][0]
        second_button = second_markup.inline_keyboard[0][0]

        assert all("6 коротких вопросов" in text for _, text, _ in bot.sent_messages)
        assert first_button.text == "Ответить на короткий опрос"
        assert second_button.text == "Ответить на короткий опрос"
        assert first_button.callback_data == "session:survey"
        assert second_button.callback_data == "session:survey"

    asyncio.run(scenario())


def test_post_session_survey_callback_clears_markup_and_opens_link(monkeypatch) -> None:
    async def scenario() -> None:
        callback = _CallbackStub(user_id=1)
        redis = _RedisStub()
        await redis.set(
            "summary_meta:1",
            session_handler.encode_summary_meta(session_id="end-flow-test", user_a_id=1, user_b_id=2),
        )
        monkeypatch.setattr(
            session_handler.settings,
            "post_session_survey_url",
            "https://tally.so/r/test-form?utm_source=bot",
        )

        await session_handler.cb_post_session_survey(callback=callback, redis=redis)

        assert callback.answered is True
        assert callback.message.reply_markup is None
        assert callback.answer_kwargs[-1]["url"].startswith("https://tally.so/r/test-form")
        assert "session_id=end-flow-test" in callback.answer_kwargs[-1]["url"]
        assert "role=A" in callback.answer_kwargs[-1]["url"]

    asyncio.run(scenario())
