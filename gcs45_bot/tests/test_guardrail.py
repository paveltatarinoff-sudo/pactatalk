from bot.handlers.facilitator import _resolve_next_speaker_with_guardrail
from bot.models.session import SessionState


def _session() -> SessionState:
    return SessionState(
        session_id="test-session",
        user_a_id=1,
        user_b_id=2,
        name_a="Pasha",
        name_b="Lyuda",
        waiting_for="A",
    )


def test_feedback_override_for_partner_a() -> None:
    session = _session()

    result = _resolve_next_speaker_with_guardrail(
        session=session,
        proposed_next_speaker="B",
        ai_message="Lyuda, как ты это видишь?",
        last_user_message="задай вопрос мне",
        last_user_label="A",
    )

    assert result == "A"


def test_feedback_override_for_partner_b() -> None:
    session = _session()

    result = _resolve_next_speaker_with_guardrail(
        session=session,
        proposed_next_speaker="A",
        ai_message="Pasha, что ты чувствуешь?",
        last_user_message="ты перепутал",
        last_user_label="B",
    )

    assert result == "B"


def test_text_address_override_to_partner_a() -> None:
    session = _session()

    result = _resolve_next_speaker_with_guardrail(
        session=session,
        proposed_next_speaker="B",
        ai_message="Pasha, что для тебя сейчас важнее всего?",
        last_user_message="обычный ответ",
        last_user_label="B",
    )

    assert result == "A"


def test_text_address_override_to_partner_b() -> None:
    session = _session()

    result = _resolve_next_speaker_with_guardrail(
        session=session,
        proposed_next_speaker="A",
        ai_message="Lyuda, как ты это услышала?",
        last_user_message="обычный ответ",
        last_user_label="A",
    )

    assert result == "B"


def test_invalid_next_speaker_falls_back_to_both() -> None:
    session = _session()

    result = _resolve_next_speaker_with_guardrail(
        session=session,
        proposed_next_speaker="INVALID",
        ai_message="Как бы вы оба хотели продолжить?",
        last_user_message="обычный ответ",
        last_user_label="A",
    )

    assert result == "BOTH"


def test_no_override_keeps_original_next_speaker() -> None:
    session = _session()

    result = _resolve_next_speaker_with_guardrail(
        session=session,
        proposed_next_speaker="A",
        ai_message="Pasha, что тебе сейчас важнее всего донести?",
        last_user_message="обычный ответ",
        last_user_label="B",
    )

    assert result == "A"
