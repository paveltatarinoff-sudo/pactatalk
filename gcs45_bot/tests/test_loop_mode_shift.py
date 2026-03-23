from __future__ import annotations

import asyncio

from bot.handlers import facilitator
from bot.models.session import SessionState
from bot.services.loop_guard import append_history_entry, maybe_build_loop_mode_shift


def _session(state: str = "DEEPEN", waiting_for: str = "A") -> SessionState:
    return SessionState(
        session_id="loop-test",
        user_a_id=1,
        user_b_id=2,
        name_a="Pasha",
        name_b="Lyuda",
        waiting_for=waiting_for,
        dialogue_state=state,
    )


def _history_with_pairs(pairs: list[tuple[str, str, str]]) -> list[dict]:
    history: list[dict] = []
    for speaker, user_text, bot_text in pairs:
        history = append_history_entry(history, role="user", content=f"[{speaker}]: {user_text}")
        history = append_history_entry(history, role="assistant", content=bot_text)
    return history


class _RepoStub:
    def __init__(self, history: list[dict] | None = None) -> None:
        self.history = list(history or [])
        self.events: list[dict] = []
        self.saved_sessions: list[SessionState] = []

    async def get_history(self, session_id: str) -> list[dict]:
        return list(self.history)

    async def save_history(self, session_id: str, history: list[dict]) -> None:
        self.history = list(history)

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


class _ClaudePassThroughStub:
    def __init__(self, reply: str, next_speaker: str = "A") -> None:
        self.called = False
        self.reply = reply
        self.next_speaker = next_speaker

    async def get_facilitator_response(self, session, user_message, sender_label, repo, **kwargs):
        self.called = True
        return (
            self.reply,
            False,
            self.next_speaker,
            {
                "dialogue_state_before": session.dialogue_state,
                "waiting_for_before": session.waiting_for,
                "addressed_to": self.next_speaker,
                "next_speaker": self.next_speaker,
                "next_state": session.dialogue_state,
                "risk_flag": False,
            },
        )


def test_explicit_loop_feedback_triggers_mode_shift() -> None:
    session = _session()
    history = _history_with_pairs([
        ("A", "я уже устал от этого", "Pasha, что сейчас в этом самое болезненное?"),
    ])
    history = append_history_entry(history, role="user", content="[A]: ты повторяешься, мы ходим по кругу")

    result = maybe_build_loop_mode_shift(session, history)

    assert result is not None
    assert result.reason == "explicit_loop_feedback"
    assert result.addressed_to == "A"
    assert "правда начал ходить по кругу" in result.reply


def test_low_energy_pattern_triggers_mode_shift() -> None:
    session = _session()
    history = _history_with_pairs([
        ("A", "не знаю", "Pasha, что здесь для тебя самое трудное?"),
        ("A", "не помогает", "Pasha, а что ты чувствуешь в этот момент?"),
    ])
    history = append_history_entry(history, role="user", content="[A]: сложно")

    result = maybe_build_loop_mode_shift(session, history)

    assert result is not None
    assert result.reason == "low_energy_repetition"
    assert "этот формат сейчас буксует" in result.reply


def test_productive_conversation_does_not_trigger_mode_shift() -> None:
    session = _session()
    history = _history_with_pairs([
        ("A", "мне обидно, когда ты закрываешься", "Pasha, в какой момент это было особенно остро?"),
        ("A", "вчера вечером, когда я заговорил, а в ответ была тишина", "Pasha, что в тот момент было самым болезненным?"),
    ])
    history = append_history_entry(
        history,
        role="user",
        content="[A]: я почувствовал, что опять остался в этом один",
    )

    assert maybe_build_loop_mode_shift(session, history) is None


def test_risk_signal_does_not_trigger_mode_shift() -> None:
    session = _session()
    history = _history_with_pairs([
        ("A", "не знаю", "Pasha, что здесь для тебя самое трудное?"),
    ])
    history = append_history_entry(
        history,
        role="user",
        content="[A]: ты повторяешься, и я боюсь идти домой",
    )

    assert maybe_build_loop_mode_shift(session, history) is None


def test_process_turn_short_circuits_model_when_loop_detected(monkeypatch) -> None:
    class _ClaudeStub:
        def __init__(self) -> None:
            self.called = False

        async def get_facilitator_response(self, *args, **kwargs):
            self.called = True
            raise AssertionError("model should not be called when loop mode shift is triggered")

    claude_stub = _ClaudeStub()
    monkeypatch.setattr(facilitator, "_claude", claude_stub)
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub(
        _history_with_pairs([
            ("A", "не знаю", "Pasha, что здесь для тебя самое трудное?"),
            ("A", "не помогает", "Pasha, а что ты чувствуешь в этот момент?"),
        ])
    )
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="сложно",
            relay_text="сложно",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert claude_stub.called is False
    assert session.waiting_for == "A"
    assert any("Что сейчас полезнее:" in text for _, text in bot.sent_messages)
    assert "короткую структуру ответа" in repo.history[-1]["content"]


def test_process_turn_keeps_normal_productive_flow(monkeypatch) -> None:
    claude_stub = _ClaudePassThroughStub(
        "Pasha, когда это произошло вчера, что задело тебя сильнее всего?"
    )
    monkeypatch.setattr(facilitator, "_claude", claude_stub)
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub(
        _history_with_pairs([
            ("A", "мне обидно, когда ты закрываешься", "Pasha, в какой момент это было особенно остро?"),
            ("A", "вчера вечером, когда я заговорил, а в ответ была тишина", "Pasha, что в тот момент было самым болезненным?"),
        ])
    )
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="я почувствовал, что опять остался в этом один",
            relay_text="я почувствовал, что опять остался в этом один",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert claude_stub.called is True
    assert session.waiting_for == "A"
    assert any("что задело тебя сильнее всего" in text for _, text in bot.sent_messages)
    assert all("Что сейчас полезнее:" not in text for _, text in bot.sent_messages)


def test_process_turn_keeps_sensitive_deepening_flow(monkeypatch) -> None:
    claude_stub = _ClaudePassThroughStub(
        "Pasha, когда это случается, что в тебе обрывается первым?"
    )
    monkeypatch.setattr(facilitator, "_claude", claude_stub)
    monkeypatch.setattr(facilitator, "_reply_extras", lambda session: ("", None))

    session = _session(waiting_for="A")
    repo = _RepoStub(
        _history_with_pairs([
            ("A", "мне больно, когда ты исчезаешь", "Pasha, в какой момент это чувствуется острее всего?"),
        ])
    )
    bot = _BotStub()
    message = _MessageStub(user_id=1)

    asyncio.run(
        facilitator._process_turn(
            text="я правда чувствую себя в этот момент совсем один",
            relay_text="я правда чувствую себя в этот момент совсем один",
            message=message,
            session=session,
            sender_label="A",
            bot=bot,
            repo=repo,
            state=None,
        )
    )

    assert claude_stub.called is True
    assert session.waiting_for == "A"
    assert any("что в тебе обрывается первым" in text for _, text in bot.sent_messages)
    assert all("Что сейчас полезнее:" not in text for _, text in bot.sent_messages)
