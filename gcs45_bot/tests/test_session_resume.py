"""Tests for P3.1: session resume / continuity between sessions."""
from __future__ import annotations

import asyncio

from bot.models.session import SessionState
from bot.models.pair_resume import PairResume, make_pair_key
from bot.handlers.session import _apply_resume_resolution
from bot.services.resume_choice import (
    RESUME_CHOICE_ALIGNMENT_PENDING,
    RESUME_CHOICE_CONTINUE,
    RESUME_CHOICE_NEW_TOPIC,
    classify_resume_resolution_text,
    decide_resume_resolution,
    get_resume_resolution,
    normalize_resume_choice,
    process_alignment_reply,
    record_resume_vote,
)
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
        assert "Активная техника" in prompt

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


# ── P3.3: Stopping point + active technique continuity ───────────────────────


SAMPLE_RESUME_WITH_TECHNIQUE = (
    "Тема: Нехватка внимания и близости.\n"
    "Позиция Pasha: ему важно чувствовать, что его ценят и замечают.\n"
    "Позиция Lyuda: ей нужно больше совместного времени.\n"
    "Где остановились: Pasha пересказывал слова Lyuda в рамках упражнения.\n"
    "Активная техника: активное слушание — Pasha начал пересказ, но не завершил.\n"
    "Что осталось недосказанным: Lyuda не дала обратную связь на пересказ.\n"
    "Состояние: DEEPEN"
)

SAMPLE_RESUME_NO_TECHNIQUE = (
    "Тема: Распределение домашних обязанностей.\n"
    "Позиция Pasha: хочет больше равенства.\n"
    "Позиция Lyuda: чувствует, что её вклад не замечают.\n"
    "Где остановились: обсуждали конкретную ситуацию — ужин в среду.\n"
    "Активная техника: нет\n"
    "Что осталось недосказанным: Pasha не успел рассказать про свои ожидания.\n"
    "Состояние: DEEPEN"
)


class TestResumeStoppingPoint:
    """P3.3: resume_block and guidelines reference technique and stopping point."""

    def test_resume_block_mentions_technique_field(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME_WITH_TECHNIQUE)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "Активная техника" in prompt
        assert "активное слушание" in prompt

    def test_resume_block_mentions_stopping_point(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME_WITH_TECHNIQUE)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "Где остановились" in prompt or "точку остановки" in prompt

    def test_resume_block_hint_references_technique(self) -> None:
        """The resume_block hint should tell the bot to look at technique field."""
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME_WITH_TECHNIQUE)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "предложи продолжить именно её" in prompt or "предложить продолжить" in prompt

    def test_no_technique_resume_still_works(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME_NO_TECHNIQUE)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "КОНТЕКСТ ПРЕДЫДУЩЕЙ СЕССИИ" in prompt
        assert "нет" in prompt  # "Активная техника: нет" is in the resume

    def test_resume_without_technique_field_still_injects(self) -> None:
        """Old-format resumes (without technique field) should still be injected."""
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME)
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "SETUP")
        assert "КОНТЕКСТ ПРЕДЫДУЩЕЙ СЕССИИ" in prompt
        assert "вечер вторника" in prompt


class TestResumeGuidelinesP33:
    """P3.3: STATE_GUIDELINES_RESUME mentions technique continuity."""

    def test_guidelines_mention_technique_priority(self) -> None:
        assert "АКТИВНАЯ ТЕХНИКА" in STATE_GUIDELINES_RESUME

    def test_guidelines_mention_stopping_point(self) -> None:
        assert "ТОЧКА ОСТАНОВКИ" in STATE_GUIDELINES_RESUME or "Где остановились" in STATE_GUIDELINES_RESUME

    def test_guidelines_technique_before_topic(self) -> None:
        """Technique should be offered before general topic question."""
        idx_technique = STATE_GUIDELINES_RESUME.find("АКТИВНАЯ ТЕХНИКА")
        idx_new_topic = STATE_GUIDELINES_RESUME.find("новую тему")
        assert idx_technique < idx_new_topic, "Technique offer should come before new topic option"


class TestResumeConfirmationChoice:
    def test_continue_keeps_resume(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME)
        message = _apply_resume_resolution(session, RESUME_CHOICE_CONTINUE)

        assert session.resume_context == SAMPLE_RESUME
        assert "Продолжим прошлую тему" in message

    def test_new_topic_clears_resume(self) -> None:
        session = _session(state="SETUP", resume_context=SAMPLE_RESUME)
        message = _apply_resume_resolution(session, RESUME_CHOICE_NEW_TOPIC)

        assert session.resume_context == ""
        assert "что ты хочешь получить от этого разговора" in message

    def test_stale_not_accurate_maps_to_new_topic(self) -> None:
        assert normalize_resume_choice("session:resume_not_accurate") == RESUME_CHOICE_NEW_TOPIC


class _RedisChoiceStub:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        if nx and key in self._values:
            return False
        self._values[key] = value
        return True

    async def get(self, key: str):
        return self._values.get(key)

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self._values:
                del self._values[key]
                deleted += 1
        return deleted


class TestResumePairVoting:
    def test_first_vote_waits_for_partner(self) -> None:
        redis = _RedisChoiceStub()
        status, resolution = asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_CONTINUE,
            )
        )

        assert status == "waiting"
        assert resolution == RESUME_CHOICE_CONTINUE
        assert asyncio.run(get_resume_resolution(redis, "session-1")) is None

    def test_matching_votes_resolve_continue(self) -> None:
        redis = _RedisChoiceStub()
        asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_CONTINUE,
            )
        )
        status, resolution = asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=200,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_CONTINUE,
            )
        )

        assert status == "matched"
        assert resolution == RESUME_CHOICE_CONTINUE
        assert asyncio.run(get_resume_resolution(redis, "session-1")) == RESUME_CHOICE_CONTINUE

    def test_conflicting_votes_enter_alignment_pending(self) -> None:
        redis = _RedisChoiceStub()
        asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_NEW_TOPIC,
            )
        )
        status, resolution = asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=200,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_CONTINUE,
            )
        )

        assert status == "mismatch"
        assert resolution is None
        assert asyncio.run(get_resume_resolution(redis, "session-1")) == RESUME_CHOICE_ALIGNMENT_PENDING

    def test_duplicate_vote_from_same_user_is_ignored(self) -> None:
        redis = _RedisChoiceStub()
        asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_NEW_TOPIC,
            )
        )
        status, resolution = asyncio.run(
            record_resume_vote(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                choice=RESUME_CHOICE_CONTINUE,
            )
        )

        assert status == "duplicate"
        assert resolution == RESUME_CHOICE_NEW_TOPIC


class TestResumeAlignmentResolution:
    def test_alignment_text_resolves_continue(self) -> None:
        redis = _RedisChoiceStub()
        asyncio.run(redis.set("resume_resolution:session-1", RESUME_CHOICE_ALIGNMENT_PENDING))

        first = asyncio.run(
            process_alignment_reply(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                text="Хочу продолжить прошлую тему.",
            )
        )
        second = asyncio.run(
            process_alignment_reply(
                redis,
                session_id="session-1",
                user_id=200,
                user_a_id=100,
                user_b_id=200,
                text="Давайте продолжим с этого места.",
            )
        )

        assert first == ("waiting", None)
        assert second == ("resolved", RESUME_CHOICE_CONTINUE)
        assert asyncio.run(get_resume_resolution(redis, "session-1")) == RESUME_CHOICE_CONTINUE

    def test_alignment_text_resolves_new_topic(self) -> None:
        redis = _RedisChoiceStub()
        asyncio.run(redis.set("resume_resolution:session-1", RESUME_CHOICE_ALIGNMENT_PENDING))

        asyncio.run(
            process_alignment_reply(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                text="Лучше начать новую тему.",
            )
        )
        result = asyncio.run(
            process_alignment_reply(
                redis,
                session_id="session-1",
                user_id=200,
                user_a_id=100,
                user_b_id=200,
                text="Мне важнее начать заново.",
            )
        )

        assert result == ("resolved", RESUME_CHOICE_NEW_TOPIC)
        assert asyncio.run(get_resume_resolution(redis, "session-1")) == RESUME_CHOICE_NEW_TOPIC

    def test_alignment_text_retry_when_answers_do_not_converge(self) -> None:
        redis = _RedisChoiceStub()
        asyncio.run(redis.set("resume_resolution:session-1", RESUME_CHOICE_ALIGNMENT_PENDING))

        asyncio.run(
            process_alignment_reply(
                redis,
                session_id="session-1",
                user_id=100,
                user_a_id=100,
                user_b_id=200,
                text="Не знаю, может продолжить.",
            )
        )
        result = asyncio.run(
            process_alignment_reply(
                redis,
                session_id="session-1",
                user_id=200,
                user_a_id=100,
                user_b_id=200,
                text="Не уверен, как лучше.",
            )
        )

        assert result == ("retry", None)
        assert asyncio.run(get_resume_resolution(redis, "session-1")) == RESUME_CHOICE_ALIGNMENT_PENDING


class TestResumeTextClassification:
    def test_continue_markers_detected(self) -> None:
        assert classify_resume_resolution_text("Хочу продолжить прошлую тему") == RESUME_CHOICE_CONTINUE

    def test_new_topic_markers_detected(self) -> None:
        assert classify_resume_resolution_text("Давай начнем новую тему") == RESUME_CHOICE_NEW_TOPIC

    def test_pair_decision_requires_same_direction(self) -> None:
        assert decide_resume_resolution("Продолжим с этого места", "Начнем новую тему") is None
