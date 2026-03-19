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
                "Pasha, я услышал тебя.",
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
