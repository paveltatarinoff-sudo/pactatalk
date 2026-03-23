from __future__ import annotations

from dataclasses import dataclass

from bot.models.session import SessionState
from bot.services.claude_service import ClaudeService, MAX_CONTEXT_MESSAGES

_DIRECT_LOOP_FEEDBACK_MARKERS: tuple[str, ...] = (
    "ты повторяешься",
    "ты по кругу",
    "ходишь по кругу",
    "мы ходим по кругу",
    "идем по кругу",
    "идем по одному и тому же кругу",
    "это уже было",
    "это уже обсуждали",
    "одно и то же",
    "опять то же самое",
    "опять одно и то же",
    "буксуем",
    "застряли",
)

_LOW_ENERGY_MARKERS: tuple[str, ...] = (
    "не знаю",
    "не понимаю",
    "не могу сказать",
    "нечего сказать",
    "не уверен",
    "не уверена",
    "не вижу",
    "не получается",
    "сложно",
    "тяжело сказать",
    "не помогает",
    "не подходит",
    "не то",
    "не работает",
    "никак",
    "мимо",
)

_LOW_ENERGY_EXACT: tuple[str, ...] = (
    "не знаю",
    "не понимаю",
    "не могу сказать",
    "нечего сказать",
    "не уверен",
    "не уверена",
    "не вижу",
    "не получается",
    "сложно",
    "не помогает",
    "не подходит",
    "не то",
    "не работает",
    "никак",
    "мимо",
)

_REFLECTIVE_QUESTION_MARKERS: tuple[str, ...] = (
    "что",
    "как",
    "когда",
    "где",
    "почему",
    "для тебя",
    "внутри",
    "слышишь",
    "чувствуешь",
)

_HARD_RISK_MARKERS: tuple[str, ...] = (
    "боюсь идти домой",
    "он бил",
    "она била",
    "ударил",
    "ударила",
    "запрещает видеть друзей",
    "следит за телефоном",
    "не хочу жить",
    "лучше бы меня не было",
    "я его убью",
    "я ее убью",
    "пусть пожалеет",
    "угрожает",
    "небезопасно",
)


@dataclass(frozen=True)
class LoopModeShift:
    reason: str
    reply: str
    next_speaker: str
    addressed_to: str


def append_history_entry(history: list[dict], *, role: str, content: str) -> list[dict]:
    updated = [*history, {"role": role, "content": content}]
    if len(updated) > MAX_CONTEXT_MESSAGES:
        updated = updated[-MAX_CONTEXT_MESSAGES:]
    return updated


def maybe_build_loop_mode_shift(session: SessionState, history: list[dict]) -> LoopModeShift | None:
    if session.dialogue_state not in ("DEEPEN", "CLARIFY", "DEESCALATE"):
        return None

    turns = ClaudeService._recent_user_turns(history, limit=3)
    if not turns:
        return None

    current_speaker, latest_text = turns[-1]
    if current_speaker not in ("A", "B"):
        return None
    if ClaudeService._contains_any(latest_text, _HARD_RISK_MARKERS):
        return None

    if ClaudeService._contains_any(latest_text, _DIRECT_LOOP_FEEDBACK_MARKERS):
        return _build_mode_shift(session, current_speaker, "explicit_loop_feedback")

    same_speaker_turns = _recent_same_speaker_user_turns(history, current_speaker, limit=3)
    if len(same_speaker_turns) < 2:
        return None

    low_energy_count = sum(1 for text in same_speaker_turns if _is_low_energy_or_rejection(text))
    if low_energy_count < 2:
        return None

    assistant_turns = _recent_assistant_turns(history, limit=3)
    reflective_questions = sum(1 for text in assistant_turns if _looks_like_reflective_question(text))
    if reflective_questions < 2:
        return None

    return _build_mode_shift(session, current_speaker, "low_energy_repetition")


def _recent_same_speaker_user_turns(history: list[dict], speaker: str, limit: int) -> list[str]:
    turns: list[str] = []
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        parsed = ClaudeService._extract_user_turn(item.get("content", ""))
        if parsed is None:
            continue
        turn_speaker, text = parsed
        if turn_speaker != speaker:
            break
        turns.append(text)
        if len(turns) >= limit:
            break
    return list(reversed(turns))


def _recent_assistant_turns(history: list[dict], limit: int) -> list[str]:
    turns: list[str] = []
    for item in reversed(history):
        if item.get("role") != "assistant":
            continue
        turns.append(item.get("content", ""))
        if len(turns) >= limit:
            break
    return list(reversed(turns))


def _is_low_energy_or_rejection(text: str) -> bool:
    normalized = ClaudeService._normalize_text(text)
    if normalized in _LOW_ENERGY_EXACT:
        return True
    if ClaudeService._contains_any(text, ClaudeService._ACTION_REJECTION_MARKERS):
        return True
    return len(normalized.split()) <= 6 and ClaudeService._contains_any(text, _LOW_ENERGY_MARKERS)


def _looks_like_reflective_question(text: str) -> bool:
    if "?" not in text:
        return False
    if ClaudeService._assistant_looks_like_action_proposal(text):
        return False
    normalized = ClaudeService._normalize_text(text)
    return any(marker in normalized for marker in _REFLECTIVE_QUESTION_MARKERS)


def _build_mode_shift(session: SessionState, speaker: str, reason: str) -> LoopModeShift:
    speaker_name = session.name_a if speaker == "A" else session.name_b
    opening = (
        "похоже, я правда начал ходить по кругу."
        if reason == "explicit_loop_feedback"
        else "похоже, этот формат сейчас буксует, и еще один похожий вопрос не поможет."
    )
    reply = (
        f"{speaker_name}, {opening}\n\n"
        "Что сейчас полезнее:\n"
        "1. Назвать главный тупик одной фразой.\n"
        "2. Попросить у меня один более конкретный вопрос или короткую структуру ответа.\n"
        "3. Взять паузу и вернуться позже."
    )
    return LoopModeShift(
        reason=reason,
        reply=reply,
        next_speaker=speaker,
        addressed_to=speaker,
    )
