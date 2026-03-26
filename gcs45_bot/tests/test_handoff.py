"""Tests for P1/P1.1 fix: handoff / BOTH / turn transfer guards."""
from __future__ import annotations

from bot.models.session import SessionState
from bot.services.claude_service import ClaudeService


def _make_messages(turns: list[tuple[str, str]]) -> list[dict]:
    """Build message history from (speaker, text) tuples, interleaved with bot responses."""
    messages: list[dict] = []
    for i, (speaker, text) in enumerate(turns):
        messages.append({"role": "user", "content": f"[{speaker}]: {text}"})
        messages.append({"role": "assistant", "content": f"Ответ бота #{i + 1}"})
    return messages


def _session(state: str = "DEEPEN", waiting_for: str = "A") -> SessionState:
    return SessionState(
        session_id="test",
        user_a_id=1,
        user_b_id=2,
        name_a="Pasha",
        name_b="Lyuda",
        waiting_for=waiting_for,
        dialogue_state=state,
    )


class TestConsecutiveSameSpeaker:
    def test_three_a_in_row(self) -> None:
        messages = _make_messages([("A", "раз"), ("A", "два"), ("A", "три")])
        count, speaker = ClaudeService._consecutive_same_speaker(messages)
        assert count == 3
        assert speaker == "A"

    def test_alternating(self) -> None:
        messages = _make_messages([("A", "раз"), ("B", "два"), ("A", "три")])
        count, speaker = ClaudeService._consecutive_same_speaker(messages)
        assert count == 1
        assert speaker == "A"

    def test_two_b_then_a(self) -> None:
        messages = _make_messages([("A", "раз"), ("B", "два"), ("B", "три")])
        count, speaker = ClaudeService._consecutive_same_speaker(messages)
        assert count == 2
        assert speaker == "B"

    def test_both_breaks_streak(self) -> None:
        messages = _make_messages([("A", "раз"), ("BOTH", "оба"), ("A", "три")])
        count, speaker = ClaudeService._consecutive_same_speaker(messages)
        assert count == 1
        assert speaker == "A"

    def test_empty(self) -> None:
        count, speaker = ClaudeService._consecutive_same_speaker([])
        assert count == 0
        assert speaker == ""


class TestLastUserSpeaker:
    def test_last_is_a(self) -> None:
        messages = _make_messages([("B", "раз"), ("A", "два")])
        assert ClaudeService._last_user_speaker(messages) == "A"

    def test_last_is_b(self) -> None:
        messages = _make_messages([("A", "раз"), ("B", "два")])
        assert ClaudeService._last_user_speaker(messages) == "B"

    def test_empty(self) -> None:
        assert ClaudeService._last_user_speaker([]) == ""


class TestLastUserMessageVulnerable:
    def test_vulnerable_message(self) -> None:
        messages = [{"role": "user", "content": "[A]: мне больно и страшно"}]
        assert ClaudeService._last_user_message_is_vulnerable(messages) is True

    def test_normal_message(self) -> None:
        messages = [{"role": "user", "content": "[A]: Да, я согласен"}]
        assert ClaudeService._last_user_message_is_vulnerable(messages) is False

    def test_lonely(self) -> None:
        messages = [{"role": "user", "content": "[B]: я чувствую себя одинокой"}]
        assert ClaudeService._last_user_message_is_vulnerable(messages) is True

    def test_abandoned(self) -> None:
        messages = [{"role": "user", "content": "[A]: чувствую себя брошенным"}]
        assert ClaudeService._last_user_message_is_vulnerable(messages) is True

    def test_blurry_feeling_is_vulnerable(self) -> None:
        messages = [{"role": "user", "content": "[A]: Мне тяжело и неприятно"}]
        assert ClaudeService._last_user_message_is_vulnerable(messages) is True

    def test_accusation_is_vulnerable(self) -> None:
        messages = [{"role": "user", "content": "[A]: Ты никогда меня не слушаешь"}]
        assert ClaudeService._last_user_message_is_vulnerable(messages) is True


class TestLastUserMessageSafetyAdjacent:
    def test_soft_control_is_safety_adjacent(self) -> None:
        messages = [{"role": "user", "content": "[B]: Мне спокойнее, если ты никуда не пойдешь сегодня"}]
        assert ClaudeService._last_user_message_is_safety_adjacent(messages) is True

    def test_normal_message_is_not_safety_adjacent(self) -> None:
        messages = [{"role": "user", "content": "[A]: Я устал и хочу просто отдохнуть"}]
        assert ClaudeService._last_user_message_is_safety_adjacent(messages) is False


class TestLastUserMessageNeedsGrounding:
    def test_broad_message_needs_grounding(self) -> None:
        messages = [{"role": "user", "content": "[A]: Ты всегда закрываешься, и мне от этого тяжело"}]
        assert ClaudeService._last_user_message_needs_grounding(messages) is True

    def test_specific_message_does_not_need_grounding(self) -> None:
        messages = [{"role": "user", "content": "[A]: Вчера вечером, когда ты молчал после моего вопроса, меня накрыло"}]
        assert ClaudeService._last_user_message_needs_grounding(messages) is False


class TestPreGenerationHoldReason:
    def test_vulnerable_message_forces_hold(self) -> None:
        messages = [{"role": "user", "content": "[A]: Мне очень больно и страшно"}]
        reason = ClaudeService._pre_generation_hold_reason(messages, "DEEPEN")
        assert reason == "vulnerable"

    def test_safety_adjacent_message_forces_hold(self) -> None:
        messages = [{"role": "user", "content": "[B]: Мне спокойнее, если ты сразу пишешь, где ты и с кем"}]
        reason = ClaudeService._pre_generation_hold_reason(messages, "DEEPEN")
        assert reason == "safety_adjacent"

    def test_non_vulnerable_message_does_not_force_hold(self) -> None:
        messages = [{"role": "user", "content": "[A]: Да, согласен"}]
        reason = ClaudeService._pre_generation_hold_reason(messages, "DEEPEN")
        assert reason is None

    def test_joint_state_does_not_force_hold(self) -> None:
        messages = [{"role": "user", "content": "[A]: Мне очень больно и страшно"}]
        reason = ClaudeService._pre_generation_hold_reason(messages, "OPTIONS")
        assert reason is None

    def test_second_hold_turn_releases_hold(self) -> None:
        messages = _make_messages([("A", "Мне страшно"), ("A", "И я не знаю, как это вынести")])
        reason = ClaudeService._pre_generation_hold_reason(messages, "DEEPEN")
        assert reason is None


class TestRecentHandoffContext:
    def test_builds_context(self) -> None:
        messages = _make_messages([("A", "привет"), ("B", "привет")])
        ctx = ClaudeService._recent_handoff_context(messages)
        assert "Последние ходы" in ctx
        assert "[A]:" in ctx
        assert "[B]:" in ctx
        assert "[BOT]:" in ctx

    def test_empty(self) -> None:
        ctx = ClaudeService._recent_handoff_context([])
        assert ctx == ""


class TestJointTurnHelpers:
    def test_recent_consecutive_joint_turns_counts_both_cycles(self) -> None:
        messages = _make_messages([
            ("BOTH", "[A]: хочу обсудить переезд\n[B]: хочу ясности по будущему"),
            ("BOTH", "[A]: мне важно найти работу\n[B]: мне одиноко от неопределенности"),
        ])
        assert ClaudeService._recent_consecutive_joint_turns(messages) == 2

    def test_count_user_turns_counts_joint_subturns(self) -> None:
        messages = _make_messages([
            ("BOTH", "[A]: первое\n[B]: второе"),
            ("A", "третье"),
        ])
        assert ClaudeService._count_user_turns(messages) == 3

    def test_should_force_clarify_reads_joint_subturns(self) -> None:
        messages = _make_messages([
            ("BOTH", "[A]: мне нужно больше пространства\n[B]: мне нужна близость и больше вместе"),
        ])
        assert ClaudeService._should_force_clarify(messages) is True

    def test_preferred_focus_speaker_after_joint_prefers_more_vulnerable_side(self) -> None:
        session = _session(state="SETUP", waiting_for="BOTH")
        messages = _make_messages([
            ("BOTH", "[A]: мне важно понять сроки\n[B]: мне одиноко и страшно от этой неопределенности"),
        ])
        assert ClaudeService._preferred_focus_speaker_after_joint(session, messages) == "B"


class TestResolveHandoffInvariants:
    def test_keeps_single_speaker_handoff_when_valid(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = _make_messages([("A", "Мне важно это обсудить")])
        svc = ClaudeService()

        resolved = svc.resolve_handoff_invariants("B", "DEEPEN", messages, session)

        assert resolved == "B"

    def test_joint_states_force_both(self) -> None:
        session = _session(state="OPTIONS", waiting_for="A")
        messages = _make_messages([("A", "У меня есть вариант")])
        svc = ClaudeService()

        for effective_state in ("OPTIONS", "AGREE", "CHECK_IN"):
            resolved = svc.resolve_handoff_invariants("A", effective_state, messages, session)
            assert resolved == "BOTH"

    def test_depth_states_block_both_to_last_speaker(self) -> None:
        session = _session(state="DEEPEN", waiting_for="B")
        messages = _make_messages([("B", "Хочу это уточнить")])
        svc = ClaudeService()

        for effective_state in ("DEEPEN", "DEESCALATE", "CLARIFY"):
            resolved = svc.resolve_handoff_invariants("BOTH", effective_state, messages, session)
            assert resolved == "B"

    def test_vulnerability_hold_keeps_focus_on_last_speaker(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = [{"role": "user", "content": "[A]: Мне очень больно и страшно"}]
        svc = ClaudeService()

        resolved = svc.resolve_handoff_invariants("BOTH", "DEEPEN", messages, session)

        assert resolved == "A"

    def test_three_consecutive_turns_force_switch(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = _make_messages([("A", "раз"), ("A", "два"), ("A", "три")])
        svc = ClaudeService()

        resolved = svc.resolve_handoff_invariants("A", "DEEPEN", messages, session)

        assert resolved == "B"


# ── P1.1 tests ──────────────────────────────────────────────────────────────


class TestDeveloperPromptForcedSwitch:
    """When consecutive >= 3, addressing_rule should be overridden to the OTHER speaker."""

    def test_forced_switch_overrides_addressing_rule(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = _make_messages([("A", "раз"), ("A", "два"), ("A", "три")])
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages)
        # Should contain forced switch instruction to Lyuda
        assert "ПРИНУДИТЕЛЬНАЯ ПЕРЕДАЧА СЛОВА" in prompt
        assert "Lyuda" in prompt
        # Should NOT contain contradictory "Следующий отвечает: Pasha"
        assert "Следующий отвечает: Pasha" not in prompt

    def test_two_consecutive_gives_soft_hint(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = _make_messages([("B", "раз"), ("A", "два"), ("A", "три-нет-тут-2")])
        # Only 2 consecutive from A (last two)
        messages_2 = _make_messages([("A", "раз"), ("A", "два")])
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages_2)
        assert "HANDOFF:" in prompt
        assert "ПРИНУДИТЕЛЬНАЯ ПЕРЕДАЧА" not in prompt

    def test_no_warning_on_alternating(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = _make_messages([("A", "раз"), ("B", "два")])
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages)
        # "⚠ HANDOFF:" is the consecutive warning prefix — should not appear
        assert "⚠ HANDOFF:" not in prompt
        assert "ПРИНУДИТЕЛЬНАЯ ПЕРЕДАЧА" not in prompt

    def test_repeated_both_in_setup_forces_exit_to_single_partner(self) -> None:
        session = _session(state="SETUP", waiting_for="BOTH")
        messages = _make_messages([
            ("BOTH", "[A]: хочу обсудить переезд\n[B]: хочу понять, где будем жить"),
            ("BOTH", "[A]: мне важно найти работу\n[B]: мне одиноко и страшно от неопределенности"),
        ])
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages)
        assert "ОБЯЗАТЕЛЬНЫЙ ВЫХОД ИЗ BOTH" in prompt
        assert 'addressed_to="B"' in prompt
        assert "Lyuda" in prompt


class TestDeveloperPromptHoldOverride:
    def test_vulnerable_last_turn_forces_same_speaker_hold(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(
            session,
            "DEEPEN",
            [{"role": "user", "content": "[A]: Мне очень больно и страшно"}],
        )
        assert "ЖЁСТКОЕ УДЕРЖАНИЕ ФОКУСА" in prompt
        assert 'addressed_to="A", next_speaker="A"' in prompt
        assert "НЕЛЬЗЯ сейчас мостить к Lyuda" in prompt

    def test_safety_adjacent_last_turn_forces_same_speaker_hold(self) -> None:
        session = _session(state="DEEPEN", waiting_for="B")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(
            session,
            "DEEPEN",
            [{"role": "user", "content": "[B]: Мне спокойнее, если ты сразу отвечаешь и не споришь"}],
        )
        assert "ЖЁСТКОЕ УДЕРЖАНИЕ ФОКУСА" in prompt
        assert 'addressed_to="B", next_speaker="B"' in prompt
        assert "НЕЛЬЗЯ сейчас мостить к Pasha" in prompt

    def test_joint_state_does_not_force_hold(self) -> None:
        session = _session(state="OPTIONS", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(
            session,
            "OPTIONS",
            [{"role": "user", "content": "[A]: Мне очень больно и страшно"}],
        )
        assert "ЖЁСТКОЕ УДЕРЖАНИЕ ФОКУСА" not in prompt

    def test_broad_last_turn_injects_anti_generic_hint(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(
            session,
            "DEEPEN",
            [{"role": "user", "content": "[A]: Ты всегда закрываешься, и мне от этого тяжело"}],
        )
        assert "АНТИОБЩНОСТЬ" in prompt
        assert "НЕ задавай мета-вопросы" in prompt

    def test_forced_switch_still_wins_over_hold(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = _make_messages([
            ("A", "Мне страшно"),
            ("A", "И очень тяжело"),
            ("A", "Я чувствую себя совсем одиноко"),
        ])
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages)
        assert "ПРИНУДИТЕЛЬНАЯ ПЕРЕДАЧА СЛОВА" in prompt


# ── P1.2 tests ──────────────────────────────────────────────────────────────


class TestAddressingRuleInOptions:
    """In OPTIONS/AGREE/CHECK_IN addressing_rule should encourage BOTH."""

    def test_options_allows_both(self) -> None:
        session = _session(state="OPTIONS", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "OPTIONS")
        assert "addressed_to=\"BOTH\"" in prompt
        assert "ОБЯЗАТЕЛЬНО" in prompt

    def test_agree_allows_both(self) -> None:
        session = _session(state="AGREE", waiting_for="B")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "AGREE")
        assert "addressed_to=\"BOTH\"" in prompt
        assert "ОБЯЗАТЕЛЬНО" in prompt

    def test_check_in_allows_both(self) -> None:
        session = _session(state="CHECK_IN", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "CHECK_IN")
        assert "ОБЯЗАТЕЛЬНО" in prompt

    def test_deepen_does_not_encourage_both(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN")
        assert "предпочтительнее BOTH" not in prompt


class TestAddressingRuleAllowsSwitch:
    """In non-BOTH states, addressing_rule should mention switch possibility."""

    def test_deepen_mentions_switch(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN")
        assert "ПЕРЕКЛЮЧИ" in prompt
        assert "мост-фразой" in prompt

    def test_clarify_mentions_switch(self) -> None:
        session = _session(state="CLARIFY", waiting_for="B")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "CLARIFY")
        assert "ПЕРЕКЛЮЧИ" in prompt


class TestLastAnswerHint:
    """Developer prompt should characterize the last user answer."""

    def test_vulnerable_answer_suggests_stay(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = [{"role": "user", "content": "[A]: Мне так больно и страшно"}]
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages)
        assert "ЖЁСТКОЕ УДЕРЖАНИЕ ФОКУСА" in prompt
        assert 'addressed_to="A", next_speaker="A"' in prompt

    def test_long_answer_neutral(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        messages = [{"role": "user", "content": "[A]: Я думаю что нам нужно обсудить как мы проводим время вместе и раздельно потому что это важная тема"}]
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN", messages)
        assert "содержательный" in prompt


class TestOptionsStateGuidelinesHasBoth:
    """OPTIONS/AGREE STATE_GUIDELINES should explicitly require BOTH."""

    def test_options_requires_both(self) -> None:
        from bot.services.claude_service import STATE_GUIDELINES
        assert 'addressed_to="BOTH"' in STATE_GUIDELINES["OPTIONS"]
        assert 'next_speaker="BOTH"' in STATE_GUIDELINES["OPTIONS"]
        assert "ЗАПРЕЩЕНО" in STATE_GUIDELINES["OPTIONS"]

    def test_agree_requires_both(self) -> None:
        from bot.services.claude_service import STATE_GUIDELINES
        assert 'addressed_to="BOTH"' in STATE_GUIDELINES["AGREE"]
        assert 'next_speaker="BOTH"' in STATE_GUIDELINES["AGREE"]
        assert "ЗАПРЕЩЕНО" in STATE_GUIDELINES["AGREE"]


class TestBothMandatoryInOptionsAgree:
    """In OPTIONS/AGREE, addressing_rule should require BOTH, not just prefer it."""

    def test_options_says_mandatory(self) -> None:
        session = _session(state="OPTIONS", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "OPTIONS")
        assert "ОБЯЗАТЕЛЬНО" in prompt
        assert 'addressed_to="BOTH"' in prompt
        # Should NOT offer single-speaker alternative
        assert "ИЛИ к" not in prompt

    def test_agree_says_mandatory(self) -> None:
        session = _session(state="AGREE", waiting_for="B")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "AGREE")
        assert "ОБЯЗАТЕЛЬНО" in prompt
        assert 'addressed_to="BOTH"' in prompt
        assert "ИЛИ к" not in prompt

    def test_deepen_does_not_say_mandatory_both(self) -> None:
        session = _session(state="DEEPEN", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "DEEPEN")
        # DEEPEN should not have mandatory BOTH
        assert "В DEEPEN ОБЯЗАТЕЛЬНО: addressed_to" not in prompt


class TestNoBothNamePrefix:
    """BOTH addressing_rule should instruct not to start with partner name."""

    def test_both_mode_no_name_start(self) -> None:
        session = _session(state="OPTIONS", waiting_for="BOTH")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "OPTIONS")
        assert "НЕ начинай" in prompt

    def test_options_no_name_start(self) -> None:
        session = _session(state="OPTIONS", waiting_for="A")
        svc = ClaudeService()
        prompt = svc._developer_prompt_for_state(session, "OPTIONS")
        assert "НЕ начинай" in prompt


class TestResolveEffectiveStateForStickyBoth:
    def test_setup_exits_to_deepen_after_second_joint_cycle(self) -> None:
        session = _session(state="SETUP", waiting_for="BOTH")
        messages = _make_messages([
            ("BOTH", "[A]: хочу обсудить планы\n[B]: хочу ясности по будущему"),
            ("BOTH", "[A]: для меня важны сроки и работа\n[B]: для меня важно перестать жить в неопределенности"),
        ])
        svc = ClaudeService()
        assert svc._resolve_effective_state(session, messages) == "DEEPEN"


class TestOptionsGuidelinesHasForbid:
    """OPTIONS/AGREE STATE_GUIDELINES should forbid single-speaker addressing."""

    def test_options_forbids_single(self) -> None:
        from bot.services.claude_service import STATE_GUIDELINES
        assert "ЗАПРЕЩЕНО" in STATE_GUIDELINES["OPTIONS"]

    def test_agree_forbids_single(self) -> None:
        from bot.services.claude_service import STATE_GUIDELINES
        assert "ЗАПРЕЩЕНО" in STATE_GUIDELINES["AGREE"]
