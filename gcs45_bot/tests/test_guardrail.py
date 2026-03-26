from __future__ import annotations

import asyncio
import json

from bot.handlers import facilitator
from bot.models.session import SessionState
from bot.services.claude_service import ClaudeService


def _session(waiting_for: str = "A", state: str = "DEEPEN") -> SessionState:
    return SessionState(
        session_id="test-session",
        user_a_id=1,
        user_b_id=2,
        name_a="Pasha",
        name_b="Lyuda",
        waiting_for=waiting_for,
        dialogue_state=state,
    )


class _HistoryRepo:
    def __init__(self) -> None:
        self.history: list[dict[str, str]] = []

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        return list(self.history)

    async def save_history(self, session_id: str, history: list[dict[str, str]]) -> None:
        self.history = list(history)

    async def delete_history(self, session_id: str) -> None:
        self.history = []


class _RepoStub:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.saved_sessions: list[SessionState] = []

    async def append_event(self, **kwargs) -> None:
        self.events.append(kwargs)

    async def save(self, session: SessionState) -> None:
        self.saved_sessions.append(session)


class _BotStub:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []
        self.chat_actions: list[tuple[int, str]] = []

    async def send_chat_action(self, chat_id: int, action: str) -> None:
        self.chat_actions.append((chat_id, action))

    async def send_message(self, user_id: int, text: str, reply_markup=None) -> None:
        self.sent_messages.append((user_id, text))


class _MessageStub:
    def __init__(self, user_id: int = 1, chat_id: int = 100) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.chat = type("Chat", (), {"id": chat_id})()
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append(text)


class _RedisSetStub:
    def __init__(self) -> None:
        self._taken: set[str] = set()

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self._taken:
            return False
        self._taken.add(key)
        return True


def test_handoff_coherence_blocks_override_when_text_starts_with_original_addressee() -> None:
    session = _session()
    resolved, reason = ClaudeService._apply_handoff_coherence_check(
        session=session,
        message="Pasha, хочу остаться с твоим переживанием.",
        original_addressed_to="A",
        final_next_speaker="B",
    )

    assert resolved == "A"
    assert reason == "text_starts_with_original_addressee"


def test_handoff_coherence_allows_override_without_name_conflict() -> None:
    session = _session()
    resolved, reason = ClaudeService._apply_handoff_coherence_check(
        session=session,
        message="Спасибо. Хочу услышать вторую сторону.",
        original_addressed_to="A",
        final_next_speaker="B",
    )

    assert resolved == "B"
    assert reason is None


def test_feedback_override_restores_target_speaker_in_service() -> None:
    session = _session()
    repo = _HistoryRepo()
    service = ClaudeService()

    async def fake_with_retry(operation, callback, session_id=None):
        payload = {
            "message": "Коротко признаю это. Что для тебя сейчас важнее всего?",
            "next_speaker": "B",
            "addressed_to": "B",
            "risk_flag": False,
            "next_state": "DEEPEN",
        }
        msg = type("Msg", (), {"content": json.dumps(payload)})()
        choice = type("Choice", (), {"message": msg})()
        return type("Resp", (), {"choices": [choice]})()

    service._with_retry = fake_with_retry  # type: ignore[method-assign]

    message, risk_flag, next_speaker, response_meta = asyncio.run(
        service.get_facilitator_response(
            session=session,
            user_message="ты перепутал ход",
            sender_label="A",
            repo=repo,
            address_feedback=True,
            feedback_target="A",
        )
    )

    assert risk_flag is False
    assert message.startswith("Коротко признаю")
    assert next_speaker == "A"
    assert response_meta["addressed_to"] == "A"


def test_process_turn_passes_feedback_flag_to_service(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            captured["address_feedback"] = kwargs.get("address_feedback")
            captured["feedback_target"] = kwargs.get("feedback_target")
            return (
                "Pasha, давай уточним это.",
                False,
                "A",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "A",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="ты перепутал ход",
            relay_text="ты перепутал ход",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert captured["address_feedback"] is True
    assert captured["feedback_target"] == "A"
    assert session.waiting_for == "A"


def test_process_turn_uses_service_handoff_as_pass_through(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Спасибо. Хочу услышать вторую сторону.",
                False,
                "B",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "B",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "B"
    assert repo.events[-1]["next_speaker"] == "B"


def test_process_turn_keeps_service_handoff_when_reply_addresses_a(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Pasha, давай останемся с твоим переживанием ещё немного.",
                False,
                "B",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "B",
                    "next_speaker": "B",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "B"
    assert repo.events[-1]["next_speaker"] == "B"
    assert repo.events[-1]["addressed_to"] == "B"


def test_process_turn_keeps_service_handoff_when_reply_addresses_b(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Lyuda, как это для тебя сейчас звучит?",
                False,
                "A",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "A",
                    "next_speaker": "A",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "A"
    assert repo.events[-1]["next_speaker"] == "A"
    assert repo.events[-1]["addressed_to"] == "A"


def test_detect_explicit_reply_addressee_handles_sentence_level_handoff() -> None:
    session = _session()

    addressee = facilitator._detect_explicit_reply_addressee(
        session,
        "Кажется, это про опору в ваших отношениях. Pasha, как ты это слышишь?",
    )

    assert addressee == "A"


def test_detect_explicit_reply_addressee_ignores_mid_sentence_name_mentions() -> None:
    session = _session()

    addressee = facilitator._detect_explicit_reply_addressee(
        session,
        "Когда Pasha, наконец, открывается, напряжение между вами становится ниже.",
    )

    assert addressee is None


def test_detect_explicit_reply_addressee_handles_suffix_vocative_handoff() -> None:
    session = _session()

    addressee = facilitator._detect_explicit_reply_addressee(
        session,
        "Мне интересно, как это звучит для тебя, Pasha? Есть ли чувство, что это что-то меняет?",
    )

    assert addressee == "A"


def test_detect_explicit_reply_addressee_handles_cyrillic_variant_of_latin_name() -> None:
    session = _session()

    addressee = facilitator._detect_explicit_reply_addressee(
        session,
        "Звучит так, что тебе важно чувствовать отклик. Люда, как это для тебя?",
    )

    assert addressee == "B"


def test_process_turn_keeps_service_handoff_on_sentence_level_addressee_signal(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Кажется, ты хочешь чувствовать в паре больше опоры. "
                "Pasha, как ты воспринимаешь эти слова?",
                False,
                "BOTH",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "BOTH",
                    "next_speaker": "BOTH",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "BOTH"
    assert repo.events[-1]["next_speaker"] == "BOTH"
    assert repo.events[-1]["addressed_to"] == "BOTH"


def test_process_turn_keeps_service_handoff_on_suffix_vocative_signal(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Спасибо, что поделилась. Мне интересно, как это звучит для тебя, Pasha? "
                "Есть ли чувство, что это что-то меняет?",
                False,
                "B",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "B",
                    "next_speaker": "B",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="B")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=2)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="B",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "B"
    assert repo.events[-1]["next_speaker"] == "B"
    assert repo.events[-1]["addressed_to"] == "B"


def test_process_turn_keeps_service_handoff_on_cyrillic_name_signal(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Звучит так, что тебе важно чувствовать отклик. Люда, как это для тебя? "
                "Есть ли что-то, что ты могла бы предложить?",
                False,
                "BOTH",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "BOTH",
                    "next_speaker": "BOTH",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "BOTH"
    assert repo.events[-1]["next_speaker"] == "BOTH"
    assert repo.events[-1]["addressed_to"] == "BOTH"


def test_process_turn_keeps_service_handoff_on_joint_reply_signal(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            return (
                "Вы оба сейчас говорите о том, как быстро накапливается усталость. С чего начнём?",
                False,
                "A",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "A",
                    "next_speaker": "A",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A", state="OPTIONS")
    repo = _RepoStub()
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="обычный ответ",
            relay_text="обычный ответ",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert session.waiting_for == "A"
    assert repo.events[-1]["next_speaker"] == "A"
    assert repo.events[-1]["addressed_to"] == "A"


def test_add_message_truncates_history_content_to_max_length() -> None:
    repo = _HistoryRepo()
    service = ClaudeService()

    asyncio.run(
        service._add_message(
            session_id="test-session",
            role="user",
            content="x" * 2500,
            repo=repo,
        )
    )

    assert len(repo.history) == 1
    assert len(repo.history[0]["content"]) == 2000


def test_acquire_message_throttle_blocks_second_attempt() -> None:
    redis = _RedisSetStub()

    first = asyncio.run(facilitator._acquire_message_throttle(redis, 1))
    second = asyncio.run(facilitator._acquire_message_throttle(redis, 1))

    assert first is True
    assert second is False


def test_setup_topic_split_detects_different_short_topics() -> None:
    assert facilitator._looks_like_setup_topic_split(
        "Хотела бы обсудить тему детей.",
        "Хочу поговорить о том, что мы почти не видимся.",
    ) is True


def test_setup_topic_split_ignores_same_topic_with_overlap() -> None:
    assert facilitator._looks_like_setup_topic_split(
        "Хочу обсудить тему детей.",
        "Для меня тема детей сейчас самая важная.",
    ) is False


def test_setup_topic_split_ignores_topic_and_meta_participation() -> None:
    assert facilitator._looks_like_setup_topic_split(
        "Хочу обсудить вопрос нашего сексуального взаимодействия.",
        "Я просто готова участвовать в сессии.",
    ) is False


def test_collect_for_both_triggers_setup_topic_split_guard(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, *args, **kwargs):
            raise AssertionError("Claude should not be called when setup topic split guard triggers")

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())

    session = _session(waiting_for="BOTH", state="SETUP")
    repo = _RepoStub()
    bot = _BotStub()
    first_message = _MessageStub(user_id=1)
    second_message = _MessageStub(user_id=2)

    asyncio.run(
        facilitator._collect_for_both(
            text="Хочу обсудить тему детей.",
            relay_text="Хочу обсудить тему детей.",
            message=first_message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )
    asyncio.run(
        facilitator._collect_for_both(
            text="Хочу поговорить о том, что мы почти не видимся.",
            relay_text="Хочу поговорить о том, что мы почти не видимся.",
            message=second_message,
            session=session,
            sender_label="B",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert first_message.answers == ["Принято. Жду ответа от второго партнёра."]
    assert any("Похоже, сейчас звучат две разные темы." in text for _, text in bot.sent_messages)
    assert session.waiting_for == "BOTH"
    assert session.last_turn_summary == facilitator.SETUP_TOPIC_SPLIT_SUMMARY
    assert repo.events[-1]["next_speaker"] == "BOTH"
    assert repo.events[-1]["addressed_to"] == "BOTH"


def test_collect_for_both_prompts_seed_topic_when_other_partner_is_neutral(monkeypatch) -> None:
    class _ClaudeStub:
        async def get_facilitator_response(self, *args, **kwargs):
            raise AssertionError("Claude should not be called when setup topic seed prompt triggers")

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())

    session = _session(waiting_for="BOTH", state="SETUP")
    repo = _RepoStub()
    bot = _BotStub()
    first_message = _MessageStub(user_id=1)
    second_message = _MessageStub(user_id=2)

    asyncio.run(
        facilitator._collect_for_both(
            text="Хочу обсудить вопрос нашего сексуального взаимодействия.",
            relay_text="Хочу обсудить вопрос нашего сексуального взаимодействия.",
            message=first_message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )
    asyncio.run(
        facilitator._collect_for_both(
            text="Я просто готова участвовать в сессии.",
            relay_text="Я просто готова участвовать в сессии.",
            message=second_message,
            session=session,
            sender_label="B",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert first_message.answers == ["Принято. Жду ответа от второго партнёра."]
    assert any("тему на старт сейчас предлагает Pasha" in text for _, text in bot.sent_messages)
    assert any("Если вам ок начать с этой темы" in text for _, text in bot.sent_messages)
    assert session.waiting_for == "BOTH"
    assert session.last_turn_summary.startswith(facilitator.SETUP_TOPIC_SEED_SUMMARY_PREFIX)
    assert repo.events[-1]["next_speaker"] == "BOTH"
    assert repo.events[-1]["addressed_to"] == "BOTH"


def test_collect_for_both_passes_canonical_both_turn_to_service(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class _ClaudeStub:
        async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
            captured["user_message"] = user_message
            captured["sender_label"] = sender_label
            return (
                "Pasha, давай остановимся на твоей стороне.",
                False,
                "A",
                {
                    "dialogue_state_before": session.dialogue_state,
                    "waiting_for_before": session.waiting_for,
                    "addressed_to": "A",
                    "next_speaker": "A",
                    "risk_flag": False,
                },
            )

    monkeypatch.setattr(facilitator, "_claude", _ClaudeStub())
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="BOTH", state="SETUP")
    repo = _RepoStub()
    bot = _BotStub()
    first_message = _MessageStub(user_id=1)
    second_message = _MessageStub(user_id=2)

    asyncio.run(
        facilitator._collect_for_both(
            text="Хочу обсудить переезд в Испанию.",
            relay_text="Хочу обсудить переезд в Испанию.",
            message=first_message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )
    asyncio.run(
        facilitator._collect_for_both(
            text="Хочу понять наши планы по переезду в Испанию.",
            relay_text="Хочу понять наши планы по переезду в Испанию.",
            message=second_message,
            session=session,
            sender_label="B",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert captured["sender_label"] == "BOTH"
    assert captured["user_message"] == (
        "[A]: Хочу обсудить переезд в Испанию.\n"
        "[B]: Хочу понять наши планы по переезду в Испанию."
    )
