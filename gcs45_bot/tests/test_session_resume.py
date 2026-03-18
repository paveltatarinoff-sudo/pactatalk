"""Tests for P3.1: session resume / continuity between sessions."""
from __future__ import annotations

from bot.models.session import SessionState
from bot.models.pair_resume import PairResume, make_pair_key
from bot.services.claude_service import ClaudeService, STATE_GUIDELINES, STATE_GUIDELINES_RESUME


def _session(
    state: str = "SETUP",
    waiting_for: str = "BOTH",
    resume_context: str = "",
) -> SessionState:
    return SessionState(
        session_id="test",
        user_a_id=100,
        user_b_id=200,
        name_a="Pasha",
        name_b="Lyuda",
        waiting_for=waiting_for,
        dialogue_state=state,
        resume_context=resume_context,
    )


SAMPLE_RESUME = (
    "Тема: Нехватка внимания и близости.\n"
    "Позиция Pasha: ему важно чувствовать, что его ценят и замечают.\n"
    "Позиция Lyuda: ей нужно больше совместного времени.\n"
    "Где остановились: обсуждали конкретную ситуацию — вечер вторника.\n"
    "Что осталось недосказанным: Pasha не успел рассказать, что чувствует когда Lyuda уходит.\n"
    "Состояние: DEEPEN"
)


# ── PairResume model ────────────────────────────────────────────────────────


class TestMakePairKey:
    def test_deterministic_order(self) -> None:
        assert make_pair_key(100, 200) == "100:200"
        assert make_pair_key(200, 100) == "100:200"

    def test_same_result_regardless_of_input_order(self) -> None:
        assert make_pair_key(555, 111) == make_pair_key(111, 555)

    def test_different_pairs_different_keys(self) -> None:
        assert make_pair_key(100, 200) != make_pair_key(100, 300)


class TestPairResumeModel:
    def test_model_fields(self) -> None:
        pr = PairResume(
            pair_key="100:200",
            session_id="test-session",
            name_a="Pasha",
            name_b="Lyuda",
            resume_context="test resume",
            dialogue_state="DEEPEN",
        )
        assert pr.pair_key == "100:200"
        assert pr.resume_context == "test resume"
        assert pr.dialogue_state == "DEEPEN"


# ── SessionState resume_context field ────────────────────────────────────────


class TestSessionStateResumeField:
    def test_default_empty(self) -> None:
        s = SessionState()
        assert s.resume_context == ""

    def test_can_set_resume(self) -> None:
        s = _session(resume_context=SAMPLE_RESUME)
        assert "Нехватка внимания" in s.resume_context


# ── Developer prompt with resume context ─────────────────────────────────────


class TestResumeInDeveloperPrompt:
    def test_resume_injected_in_setup(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "КОНТЕКСТ ПРЕДЫДУЩЕЙ СЕССИИ" in prompt
        assert "Нехватка внимания" in prompt
        assert "Хотите продолжить" in prompt

    def test_resume_not_injected_in_deepen(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A", resume_context=SAMPLE_RESUME)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN")
        assert "КОНТЕКСТ ПРЕДЫДУЩЕЙ СЕССИИ" not in prompt

    def test_no_resume_no_injection(self) -> None:
        session = _session(state="SETUP")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "КОНТЕКСТ ПРЕДЫДУЩЕЙ СЕССИИ" not in prompt

    def test_resume_uses_resume_guidelines(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        # Should use STATE_GUIDELINES_RESUME, not regular SETUP
        assert "НЕ начинай с «Что тебя сюда привело?»" in prompt
        assert "ПРОДОЛЖЕНИЕ" in prompt

    def test_no_resume_uses_regular_setup(self) -> None:
        session = _session(state="SETUP")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        # Should use regular SETUP guidelines
        assert "Что тебя сюда привело" in prompt


# ── STATE_GUIDELINES_RESUME content ──────────────────────────────────────────


class TestResumeGuidelines:
    def test_resume_guidelines_exist(self) -> None:
        assert STATE_GUIDELINES_RESUME is not None
        assert len(STATE_GUIDELINES_RESUME) > 50

    def test_resume_guidelines_mention_both(self) -> None:
        assert "BOTH" in STATE_GUIDELINES_RESUME

    def test_resume_guidelines_mention_continue_or_new(self) -> None:
        assert "продолжить" in STATE_GUIDELINES_RESUME
        assert "новую" in STATE_GUIDELINES_RESUME

    def test_resume_guidelines_forbid_fresh_start(self) -> None:
        assert "НЕ начинай с «Что тебя сюда привело?»" in STATE_GUIDELINES_RESUME

    def test_resume_guidelines_not_copy_paste(self) -> None:
        assert "НЕ пересказывай resume дословно" in STATE_GUIDELINES_RESUME
