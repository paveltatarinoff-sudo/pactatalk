from __future__ import annotations

import asyncio
import html
import io
import re
from datetime import datetime

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker
import structlog

from bot.config import settings
from bot.fsm.states import SessionFlow
from bot.models.session import SessionState
from bot.repositories.session_repo import SessionRepository
from bot.services.claude_service import MAX_MESSAGE_LENGTH, OpenAIServiceError
from bot.services.resume_choice import (
    RESUME_CHOICE_ALIGNMENT_PENDING,
    RESUME_CHOICE_CONTINUE,
    RESUME_CHOICE_NEW_TOPIC,
    get_resume_resolution,
    get_alignment_replies,
    process_alignment_reply,
)
from bot.services.loop_guard import append_history_entry, maybe_build_loop_mode_shift
from bot.services.session_service import (
    SessionService,
    format_bot_dialog_message,
    format_participant_dialog_block,
    format_participant_dialog_label,
)
from bot.services.shared import claude as _claude
from bot.utils.keyboards import post_session_keyboard, end_session_keyboard, end_session_button, main_menu_keyboard

router = Router(name="facilitator")
log = structlog.get_logger()
MESSAGE_THROTTLE_TTL_SECONDS = 5

# Защита от одновременных запросов к Claude для одной сессии
_locks: dict[str, asyncio.Lock] = {}
ADDRESS_FEEDBACK_PATTERNS = (
    "вопрос не тому",
    "не тому задал",
    "задай вопрос мне",
    "спроси меня",
    "это баг",
    "ты перепутал",
    "ты не меня спрашиваешь",
    "это я отвечаю",
)
END_SESSION_INTENT_PATTERNS = (
    "завершить сессию",
    "закончить сессию",
    "закончим сессию",
    "давай закончим",
    "давайте закончим",
    "пора закончить",
    "остановимся",
    "хочу закончить",
    "хочу завершить",
    "хотел бы закончить",
    "хотел бы завершить",
    "хотела бы закончить",
    "хотела бы завершить",
    "предлагаю закончить",
    "предлагаю завершить",
    "давай завершим",
    "давайте завершим",
    "на этом закончим",
    "на этом завершим",
    "не могу сейчас продолжать",
    "не хочу сейчас продолжать",
    "не готов сейчас продолжать",
    "не готова сейчас продолжать",
    "сейчас не могу продолжать",
    "сейчас не хочу продолжать",
    "хочу закончить на сегодня",
    "хочу завершить на сегодня",
    "завершаем",
    "на сегодня все",
    "на сегодня всё",
)
END_SESSION_VERB_MARKERS = (
    "заверш",
    "законч",
    "останов",
    "закры",
)
END_SESSION_CONTEXT_MARKERS = (
    "сесси",
    "разговор",
    "на сегодня",
    "на этом",
    "сейчас",
)
END_SESSION_DEFER_PATTERNS = (
    "продолжим позже",
    "давай продолжим позже",
    "давайте продолжим позже",
    "вернемся позже",
    "вернемся к этому позже",
    "вернемся к разговору позже",
    "вернемся к этому потом",
    "вернемся к разговору потом",
    "вернемся к этой теме позже",
    "вернемся к этой теме потом",
    "поговорим позже",
    "обсудим позже",
    "давай потом",
    "давайте потом",
)
END_SESSION_PAUSE_MARKERS = (
    "не могу сейчас",
    "не хочу сейчас",
    "неудобно сейчас",
    "неудобно продолжать",
    "не готов продолжать",
    "не готова продолжать",
    "не готовы продолжать",
    "сейчас не могу",
    "сейчас неудобно",
)
END_SESSION_CONFIRM_YES_PATTERNS = (
    "да",
    "давай",
    "да, давайте",
    "да, завершаем",
    "готов",
    "готова",
    "готовы",
    "согласен",
    "согласна",
    "подтверждаю",
)
END_SESSION_CONFIRM_NO_PATTERNS = (
    "нет",
    "не надо",
    "не сейчас",
    "еще нет",
    "ещё нет",
    "давай продолжим",
    "давайте продолжим",
    "продолжим",
    "не заканчиваем",
    "не хочу заканчивать",
)
SETUP_TOPIC_SPLIT_SUMMARY = "setup_topic_split_guard"
SETUP_TOPIC_SPLIT_GENERIC_TOKENS = {
    "хочу",
    "хотел",
    "хотела",
    "хотим",
    "обсудить",
    "поговорить",
    "разговор",
    "разговора",
    "тему",
    "тема",
    "темы",
    "вопрос",
    "вопроса",
    "сейчас",
    "важно",
    "важнее",
    "просто",
    "этого",
    "этой",
    "этот",
    "того",
    "чтобы",
    "который",
    "которая",
    "которые",
    "готов",
    "готова",
    "готовы",
    "участвовать",
    "участвую",
    "участие",
    "сессия",
    "сессии",
    "пригласили",
    "пригласил",
    "пригласила",
    "просто",
    "любой",
    "вариант",
    "тема",
    "темой",
    "темах",
    "важнее",
    "удобнее",
    "лучше",
    "можно",
    "разницы",
    "знаю",
}
SETUP_TOPIC_SEED_SUMMARY_PREFIX = "setup_topic_seed:"
SETUP_ANSWER_SPECIFIC_TOPIC = "specific_topic"
SETUP_ANSWER_FLEXIBLE = "flexible"
SETUP_ANSWER_META = "meta_participation"
SETUP_ANSWER_UNCLEAR = "unclear"
SETUP_FLEXIBLE_MARKERS = (
    "без разницы",
    "любой вариант",
    "мне ок",
    "как хотите",
    "как скажете",
    "какая будет тема",
    "можно с любой темы",
    "могу с любой темы",
)
SETUP_META_MARKERS = (
    "готов участвовать",
    "готова участвовать",
    "готовы участвовать",
    "участвовать в сессии",
    "просто участвую",
    "просто участвовать",
    "меня пригласили",
    "меня пригласил",
    "меня пригласила",
    "я здесь чтобы участвовать",
)


def _get_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _locks:
        _locks[session_id] = asyncio.Lock()
    return _locks[session_id]


def _release_lock(session_id: str) -> None:
    """Освобождаем память при завершении сессии."""
    _locks.pop(session_id, None)


async def _acquire_message_throttle(redis, user_id: int) -> bool:
    return bool(
        await redis.set(
            f"throttle:{user_id}",
            "1",
            nx=True,
            ex=MESSAGE_THROTTLE_TTL_SECONDS,
        )
    )


def _apply_next_speaker(session: SessionState, next_speaker: str) -> None:
    """Обновляет waiting_for. GPT всегда возвращает next_speaker через Structured Outputs.
    Страховочный лимит consecutive_turns оставлен на случай зацикливания.
    """
    if next_speaker == "BOTH":
        session.waiting_for = "BOTH"
        session.speaker_turn = "facilitator"
        session.waiting_since = datetime.utcnow()
        session.timeout_reminders_sent = 0
        session.consecutive_turns = 0
        return

    current = session.waiting_for

    if next_speaker != current:
        session.consecutive_turns = 0
    else:
        session.consecutive_turns += 1

    session.waiting_for = next_speaker
    session.speaker_turn = next_speaker  # type: ignore[assignment]
    session.waiting_since = datetime.utcnow()
    session.timeout_reminders_sent = 0


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().replace("ё", "е").split())


_CYRILLIC_NAME_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ы": "y",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ь": "",
    "ъ": "",
}
_LATIN_NAME_MULTI = (
    ("shch", "щ"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
)
_LATIN_NAME_SINGLE = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "й",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "ы",
    "z": "з",
}


def _transliterate_name_to_latin(value: str) -> str:
    return "".join(_CYRILLIC_NAME_MAP.get(ch, ch) for ch in value.lower())


def _transliterate_name_to_cyrillic(value: str) -> str:
    transliterated = value.lower()
    transliterated = re.sub(r"([bcdfghjklmnpqrstvwxyz])ya", r"\1я", transliterated)
    transliterated = re.sub(r"([bcdfghjklmnpqrstvwxyz])yu", r"\1ю", transliterated)
    transliterated = re.sub(r"([bcdfghjklmnpqrstvwxyz])yo", r"\1ё", transliterated)
    transliterated = re.sub(r"([bcdfghjklmnpqrstvwxyz])ye", r"\1е", transliterated)
    for latin, cyr in _LATIN_NAME_MULTI:
        transliterated = transliterated.replace(latin, cyr)
    return "".join(_LATIN_NAME_SINGLE.get(ch, ch) for ch in transliterated)


def _name_variants(name: str) -> set[str]:
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        return set()
    first_token = re.split(r"[\s,;/|]+", cleaned, maxsplit=1)[0]
    variants = {cleaned, first_token}
    expanded: set[str] = set()
    for item in variants:
        if not item:
            continue
        expanded.add(item)
        expanded.add(_transliterate_name_to_latin(item))
        expanded.add(_transliterate_name_to_cyrillic(item))
    return {variant for variant in expanded if variant}


def _starts_with_partner_name(message: str, name: str) -> bool:
    stripped = (message or "").strip()
    candidates = sorted(_name_variants(name), key=len, reverse=True)
    if not stripped or not candidates:
        return False
    for candidate in candidates:
        prefix_pattern = rf"(^|[.!?\n]\s*){re.escape(candidate)}\s*[:,]"
        suffix_vocative_pattern = rf"[,;:]\s*{re.escape(candidate)}\s*(?:[?!.]|$)"
        if (
            re.search(prefix_pattern, stripped, flags=re.IGNORECASE)
            or re.search(suffix_vocative_pattern, stripped, flags=re.IGNORECASE)
        ):
            return True
    return False


def _detect_explicit_reply_addressee(session: SessionState, reply: str) -> str | None:
    if _starts_with_partner_name(reply, session.name_a):
        return "A"
    if _starts_with_partner_name(reply, session.name_b):
        return "B"

    normalized = _normalize_text(reply)
    joint_markers = (
        "вы оба",
        "вам обоим",
        "каждый из вас",
        "оба говорите",
        "у вас обоих",
    )
    if any(normalized.startswith(marker) for marker in joint_markers):
        return "BOTH"
    return None

def _looks_like_address_feedback(message: str) -> bool:
    normalized = _normalize_text(message)
    return any(pattern in normalized for pattern in ADDRESS_FEEDBACK_PATTERNS)


def _extract_topic_signal_tokens(text: str) -> set[str]:
    normalized = _normalize_text(text)
    tokens = re.findall(r"[a-zа-я0-9]+", normalized)
    return {
        token
        for token in tokens
        if len(token) >= 4 and token not in SETUP_TOPIC_SPLIT_GENERIC_TOKENS
    }


def _classify_setup_opening_answer(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return SETUP_ANSWER_UNCLEAR
    if any(marker in normalized for marker in SETUP_FLEXIBLE_MARKERS):
        return SETUP_ANSWER_FLEXIBLE

    tokens = _extract_topic_signal_tokens(text)
    if tokens:
        return SETUP_ANSWER_SPECIFIC_TOPIC

    if any(marker in normalized for marker in SETUP_META_MARKERS):
        return SETUP_ANSWER_META

    return SETUP_ANSWER_UNCLEAR


def _looks_like_setup_topic_split(text_a: str, text_b: str) -> bool:
    normalized_a = _normalize_text(text_a)
    normalized_b = _normalize_text(text_b)
    if not normalized_a or not normalized_b:
        return False
    if len(normalized_a) > 120 or len(normalized_b) > 120:
        return False

    if _classify_setup_opening_answer(text_a) != SETUP_ANSWER_SPECIFIC_TOPIC:
        return False
    if _classify_setup_opening_answer(text_b) != SETUP_ANSWER_SPECIFIC_TOPIC:
        return False

    tokens_a = _extract_topic_signal_tokens(text_a)
    tokens_b = _extract_topic_signal_tokens(text_b)
    if not tokens_a or not tokens_b:
        return False

    families_a = {token[:3] for token in tokens_a}
    families_b = {token[:3] for token in tokens_b}
    if families_a & families_b:
        return False

    return True


def _setup_topic_split_prompt() -> str:
    return (
        "Похоже, сейчас звучат две разные темы.\n\n"
        "Прежде чем идти дальше, напишите каждый коротко: "
        "<b>это одна общая тема с двух сторон или вам важно сначала выбрать одну тему?</b>\n"
        "Отвечайте независимо — я жду ответа от вас обоих."
    )


def _detect_setup_topic_seed(
    text_a: str,
    text_b: str,
) -> tuple[str, str, str] | None:
    kind_a = _classify_setup_opening_answer(text_a)
    kind_b = _classify_setup_opening_answer(text_b)

    if kind_a == SETUP_ANSWER_SPECIFIC_TOPIC and kind_b != SETUP_ANSWER_SPECIFIC_TOPIC:
        return "A", text_a, kind_b
    if kind_b == SETUP_ANSWER_SPECIFIC_TOPIC and kind_a != SETUP_ANSWER_SPECIFIC_TOPIC:
        return "B", text_b, kind_a
    return None


def _setup_topic_seed_prompt(
    session: SessionState,
    *,
    proposer_label: str,
    topic_text: str,
    other_kind: str,
) -> str:
    proposer_name = session.name_a if proposer_label == "A" else session.name_b
    other_name = session.name_b if proposer_label == "A" else session.name_a
    safe_topic_text = html.escape(topic_text.strip())

    if other_kind == SETUP_ANSWER_FLEXIBLE:
        other_line = (
            f"{html.escape(other_name)}, ты пока не предлагаешь отдельную тему и готов(а) идти "
            "с тем, что сейчас важнее."
        )
    elif other_kind == SETUP_ANSWER_META:
        other_line = (
            f"{html.escape(other_name)}, ты пока не предлагаешь отдельную тему и просто готов(а) "
            "участвовать в разговоре."
        )
    else:
        other_line = f"От {html.escape(other_name)} пока не прозвучала отдельная тема."

    return (
        f"Похоже, тему на старт сейчас предлагает {html.escape(proposer_name)}:\n"
        f"<blockquote>{safe_topic_text}</blockquote>\n\n"
        f"{other_line}\n\n"
        "Если вам ок начать с этой темы, напишите каждый коротко: <b>да</b>.\n"
        "Если кому-то важнее другая тема, напишите её в одной фразе."
    )


def _speaker_signature(session: SessionState) -> str:
    """Индикатор очерёдности в начале следующего сообщения — кого бот ждёт."""
    if session.waiting_for == "BOTH":
        name_a = html.escape(session.name_a)
        name_b = html.escape(session.name_b)
        return f"\n\n<b>👥 {name_a} и {name_b}, теперь ваш ход →</b>"
    name = html.escape(session.name_a if session.waiting_for == "A" else session.name_b)
    return f"\n\n<b>👉 {name}, теперь твой ход →</b>"


def _reply_extras(session: SessionState) -> tuple[str, object]:
    """
    Возвращает (signature, keyboard) в зависимости от фазы сессии.
    - closing фаза → кнопка «Завершить сессию» + «Продолжить», без подписи
    - обычная фаза → только подпись без кнопки завершения
    """
    if session.phase == "closing":
        return "", end_session_keyboard()
    return _speaker_signature(session), None


def _looks_like_end_session_intent(message: str) -> bool:
    normalized = _normalize_text(message)
    if any(pattern in normalized for pattern in END_SESSION_INTENT_PATTERNS):
        return True

    if (
        any(marker in normalized for marker in END_SESSION_VERB_MARKERS)
        and any(marker in normalized for marker in END_SESSION_CONTEXT_MARKERS)
    ):
        return True

    if any(pattern in normalized for pattern in END_SESSION_DEFER_PATTERNS):
        return True

    if (
        any(marker in normalized for marker in END_SESSION_PAUSE_MARKERS)
        and any(pattern in normalized for pattern in END_SESSION_DEFER_PATTERNS)
    ):
        return True

    return False


def _looks_like_end_session_yes(message: str) -> bool:
    normalized = _normalize_text(message)
    return normalized in END_SESSION_CONFIRM_YES_PATTERNS


def _looks_like_end_session_no(message: str) -> bool:
    normalized = _normalize_text(message)
    return normalized in END_SESSION_CONFIRM_NO_PATTERNS


async def _request_end_session_confirmation(
    *,
    session: SessionState,
    repo: SessionRepository,
    bot: Bot,
) -> None:
    session.close_confirmation_pending = True
    session.close_choice_active = False
    session.close_continue_votes = ""
    await repo.save(session)
    await _svc(bot, repo).notify_both(
        session,
        "Похоже, вы хотите завершить сессию.\n\n"
        "Готовы закончить разговор сейчас? Ответьте коротко: <b>да</b> или <b>нет</b>.",
    )


async def _clear_end_session_choice_buttons(session: SessionState, bot: Bot) -> None:
    for chat_id, message_id, side in (
        (session.user_a_id, session.close_choice_msg_id_a, "A"),
        (session.user_b_id, session.close_choice_msg_id_b, "B"),
    ):
        if not message_id:
            continue
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
        except Exception:
            log.warning(
                "end_session_choice_clear_buttons_failed",
                session_id=session.session_id,
                side=side,
                user_id=chat_id,
                message_id=message_id,
            )


async def _present_end_session_choice(
    *,
    session: SessionState,
    repo: SessionRepository,
    bot: Bot,
) -> None:
    await _clear_end_session_choice_buttons(session, bot)
    session.close_confirmation_pending = False
    session.close_choice_active = True
    session.close_continue_votes = ""
    session.close_choice_msg_id_a = 0
    session.close_choice_msg_id_b = 0

    text = (
        "Один из вас открыл завершение сессии.\n\n"
        "Если хотите закончить сейчас, нажмите <b>«Завершить сессию»</b>.\n"
        "Если хотите продолжить, нажмите <b>«Продолжить разговор»</b>."
    )

    for user_id, attr_name in (
        (session.user_a_id, "close_choice_msg_id_a"),
        (session.user_b_id, "close_choice_msg_id_b"),
    ):
        if not user_id:
            continue
        sent = await bot.send_message(user_id, text, reply_markup=end_session_keyboard())
        setattr(session, attr_name, getattr(sent, "message_id", 0))

    await repo.save(session)


async def _present_direct_end_session_button(
    *,
    session: SessionState,
    repo: SessionRepository,
    bot: Bot,
) -> None:
    await _clear_end_session_choice_buttons(session, bot)
    session.close_confirmation_pending = False
    session.close_choice_active = True
    session.close_continue_votes = ""
    session.close_choice_msg_id_a = 0
    session.close_choice_msg_id_b = 0

    text = (
        "Похоже, вы хотите закончить разговор на сегодня.\n\n"
        "Если хотите завершить сессию сейчас, нажмите кнопку ниже."
    )

    for user_id, attr_name in (
        (session.user_a_id, "close_choice_msg_id_a"),
        (session.user_b_id, "close_choice_msg_id_b"),
    ):
        if not user_id:
            continue
        sent = await bot.send_message(user_id, text, reply_markup=end_session_button())
        setattr(session, attr_name, getattr(sent, "message_id", 0))

    await repo.save(session)


async def _resolve_end_session_confirmation(
    *,
    session: SessionState,
    repo: SessionRepository,
    bot: Bot,
    user_id: int,
    text: str,
) -> bool:
    if not session.close_confirmation_pending:
        return False

    if _looks_like_end_session_yes(text):
        await _present_end_session_choice(session=session, repo=repo, bot=bot)
        return True

    if _looks_like_end_session_no(text):
        session.close_confirmation_pending = False
        session.close_choice_active = False
        session.close_continue_votes = ""
        await repo.save(session)
        await _svc(bot, repo).notify_both(
            session,
            "Понял. Сессию не завершаю, можно продолжать разговор.",
        )
        return True

    await bot.send_message(
        user_id,
        "Если хотите завершить сессию, ответьте коротко: <b>да</b> или <b>нет</b>.",
    )
    return True


async def _maybe_apply_loop_mode_shift(
    *,
    session: SessionState,
    repo: SessionRepository,
    text: str,
    sender_label: str,
) -> tuple[str, bool, str, dict[str, str | bool]] | None:
    if not hasattr(repo, "get_history") or not hasattr(repo, "save_history"):
        return None

    history = await repo.get_history(session.session_id)
    history_with_user = append_history_entry(
        history,
        role="user",
        content=f"[{sender_label}]: {text}",
    )
    mode_shift = maybe_build_loop_mode_shift(session, history_with_user)
    if mode_shift is None:
        return None

    await repo.save_history(
        session.session_id,
        append_history_entry(history_with_user, role="assistant", content=mode_shift.reply),
    )
    session.last_turn_summary = mode_shift.reply[:150].strip()
    log.info(
        "loop_mode_shift_triggered",
        session_id=session.session_id,
        dialogue_state=session.dialogue_state,
        sender_label=sender_label,
        reason=mode_shift.reason,
    )
    return (
        mode_shift.reply,
        False,
        mode_shift.next_speaker,
        {
            "addressed_to": mode_shift.addressed_to,
            "next_speaker": mode_shift.next_speaker,
            "next_state": session.dialogue_state,
            "dialogue_state_before": session.dialogue_state,
            "dialogue_state_after": session.dialogue_state,
            "waiting_for_before": session.waiting_for,
            "risk_flag": False,
        },
    )


def _extract_resume_field(resume_context: str, field_name: str) -> str:
    prefix = f"{field_name}:"
    for raw_line in resume_context.splitlines():
        line = raw_line.strip()
        if line.lower().startswith(prefix.lower()):
            return line.split(":", 1)[1].strip()
    return ""


def _has_meaningful_resume_field(value: str) -> bool:
    normalized = value.strip().strip(".")
    if not normalized:
        return False
    return normalized.lower() not in {"нет", "не указано", "-", "—", "n/a"}


def _resume_continue_intro(session: SessionState) -> str:
    stopping_point = _extract_resume_field(session.resume_context, "Где остановились")
    unresolved = _extract_resume_field(session.resume_context, "Что осталось недосказанным")

    if _has_meaningful_resume_field(stopping_point):
        safe_stopping_point = html.escape(stopping_point)
        return (
            "Продолжим прошлую тему.\n\n"
            "<b>👥 Первый вопрос — к каждому из вас.</b>\n\n"
            "В прошлый раз вы остановились вот здесь:\n"
            f"<blockquote>{safe_stopping_point}</blockquote>\n\n"
            "Напишите каждый коротко: <b>что вам хочется сказать именно отсюда?</b>\n"
            "Отвечайте независимо — я жду ответа от вас обоих."
        )

    if _has_meaningful_resume_field(unresolved):
        safe_unresolved = html.escape(unresolved)
        return (
            "Продолжим прошлую тему.\n\n"
            "<b>👥 Первый вопрос — к каждому из вас.</b>\n\n"
            "Похоже, в прошлый раз здесь осталось что-то важное:\n"
            f"<blockquote>{safe_unresolved}</blockquote>\n\n"
            "Напишите каждый коротко: <b>что вам хочется договорить или прояснить сначала?</b>\n"
            "Отвечайте независимо — я жду ответа от вас обоих."
        )

    return (
        "Продолжим прошлую тему.\n\n"
        "<b>👥 Первый вопрос — к каждому из вас.</b>\n\n"
        "Напишите каждый коротко: <b>с какого места вам лучше продолжить этот разговор?</b>\n"
        "Отвечайте независимо — я жду ответа от вас обоих."
    )


def _default_resume_alignment_resolution(session: SessionState) -> str:
    stopping_point = _extract_resume_field(session.resume_context, "Где остановились")
    unresolved = _extract_resume_field(session.resume_context, "Что осталось недосказанным")
    if _has_meaningful_resume_field(stopping_point) or _has_meaningful_resume_field(unresolved):
        return RESUME_CHOICE_CONTINUE
    return RESUME_CHOICE_NEW_TOPIC


def _resume_alignment_retry_intro(
    session: SessionState,
    *,
    reply_a: str,
    reply_b: str,
) -> str:
    return (
        "Пока у вас не сложилось общее решение по старту.\n\n"
        "Сейчас я понял это так:\n\n"
        f"{format_participant_dialog_block(session.name_a, html.escape(reply_a.strip()))}\n\n"
        f"{format_participant_dialog_block(session.name_b, html.escape(reply_b.strip()))}\n\n"
        "Напишите каждый ещё раз коротко и прямо одним из вариантов: "
        "<b>продолжить прошлую тему</b>, <b>начать новую</b> или "
        "<b>мне ок любой вариант</b>."
    )


def _regular_setup_intro() -> str:
    return (
        "Давайте начнём. Я здесь, чтобы помочь вам услышать друг друга.\n\n"
        "Как это работает:\n"
        "• Пишешь сообщение или голосовое 🎤 — фасилитатор отвечает вам обоим\n"
        "• Говорит один, второй слушает — я слежу за очерёдностью\n"
        "• Если захотите закончить сессию, просто напишите об этом в чат\n\n"
        "<b>👥 Первый вопрос — к каждому из вас.</b>\n\n"
        "Напишите каждый своё: <b>с какой темы вам важно начать сегодня или что вам важнее всего обсудить?</b>\n"
        "Отвечайте независимо — я жду ответа от вас обоих."
    )


def _apply_resume_resolution(session: SessionState, resolution: str) -> str:
    if resolution == RESUME_CHOICE_CONTINUE:
        return _resume_continue_intro(session)
    session.resume_context = ""
    return _regular_setup_intro()


async def _handle_resume_alignment_text(
    *,
    session: SessionState,
    user_id: int,
    text: str,
    bot: Bot,
    redis,
    repo: SessionRepository,
) -> None:
    status, resolution, _, _ = await process_alignment_reply(
        redis,
        session_id=session.session_id,
        user_id=user_id,
        user_a_id=session.user_a_id,
        user_b_id=session.user_b_id,
        text=text,
        default_resolution=_default_resume_alignment_resolution(session),
    )
    if status == "waiting":
        await bot.send_message(
            user_id,
            "Принято. Жду ответа партнёра, чтобы понять, как начать разговор.",
        )
        return

    svc = _svc(bot, repo)
    if status == "resolved" and resolution is not None:
        followup = _apply_resume_resolution(session, resolution)
        await repo.save(session)
        log.info(
            "resume_choice_alignment_resolved",
            session_id=session.session_id,
            resolution=resolution,
        )
        await svc.notify_both(session, followup)
        return

    reply_a, reply_b = await get_alignment_replies(
        redis,
        session_id=session.session_id,
        user_a_id=session.user_a_id,
        user_b_id=session.user_b_id,
    )
    log.info("resume_choice_alignment_retry", session_id=session.session_id)
    await svc.notify_both(
        session,
        _resume_alignment_retry_intro(
            session,
            reply_a=reply_a or "",
            reply_b=reply_b or "",
        ),
    )


async def _notify_admins_about_risk(bot: Bot, session: SessionState) -> None:
    if not settings.admin_ids:
        return

    text = (
        "risk_flag_triggered\n"
        f"session_id={session.session_id}\n"
        f"user_a_id={session.user_a_id}\n"
        f"user_b_id={session.user_b_id}\n"
        f"details={session.risk_details[:200]}"
    )
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            log.warning(
                "risk_flag_admin_notify_failed",
                session_id=session.session_id,
                admin_id=admin_id,
            )


# ─── Текстовые сообщения ──────────────────────────────────────────────────────

@router.message(F.text)
async def handle_session_message(
    message: Message,
    bot: Bot,
    redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    user_id = message.from_user.id
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(user_id)

    if session is None:
        return
    if session.user_b_id == 0:
        await message.answer("Ожидаем партнёра. Как только он присоединится — начнём.")
        return

    sender_label = session.partner_name(user_id)
    if sender_label is None:
        return
    bound_log = log.bind(session_id=session.session_id, user_id=user_id, sender=sender_label)

    if message.text and session.close_confirmation_pending:
        handled = await _resolve_end_session_confirmation(
            session=session,
            repo=repo,
            bot=bot,
            user_id=user_id,
            text=message.text,
        )
        if handled:
            return

    # Триггер завершения сессии — от любого участника и вне очереди
    if message.text and _looks_like_end_session_intent(message.text):
        if session.close_choice_active:
            await message.answer("Кнопка завершения уже открыта. Если готовы, нажмите её.")
            return
        await _present_direct_end_session_button(session=session, repo=repo, bot=bot)
        return
    if message.text and len(message.text) > MAX_MESSAGE_LENGTH:
        await message.answer(
            "Сообщение получилось слишком длинным. Лучше выделить главное и отправить короче."
        )
        return

    resume_resolution = None
    if session.resume_context:
        resume_resolution = await get_resume_resolution(redis, session.session_id)
        if resume_resolution is None:
            await message.answer("Сначала выберите на кнопке: продолжить прошлую тему или начать новую.")
            return
        if resume_resolution == RESUME_CHOICE_ALIGNMENT_PENDING:
            throttle_ok = await _acquire_message_throttle(redis, user_id)
            if not throttle_ok:
                bound_log.info("message_throttled", input_type="text")
                await message.answer("Нужно немного подождать перед следующим сообщением.")
                return

            lock = _get_lock(session.session_id)
            if lock.locked():
                bound_log.info("turn_rejected_lock_busy")
                await message.answer("Слушаю внимательно...")
                return

            async with lock:
                fresh = await repo.get(session.session_id)
                if fresh is not None:
                    session = fresh
                await _handle_resume_alignment_text(
                    session=session,
                    user_id=user_id,
                    text=message.text or "",
                    bot=bot,
                    redis=redis,
                    repo=repo,
                )
            return

    if not session.is_active_speaker(user_id):
        bound_log.info("turn_rejected_not_active_speaker", waiting_for=session.waiting_for)
        await message.answer("Я вижу, тебе есть что сказать. Дождёмся ответа партнёра — скоро будет твоя очередь.")
        return

    throttle_ok = await _acquire_message_throttle(redis, user_id)
    if not throttle_ok:
        bound_log.info("message_throttled", input_type="text")
        await message.answer("Нужно немного подождать перед следующим сообщением.")
        return

    lock = _get_lock(session.session_id)
    if lock.locked():
        bound_log.info("turn_rejected_lock_busy")
        await message.answer("Слушаю внимательно...")
        return

    async with lock:
        # Перечитываем сессию внутри лока — актуальное состояние
        fresh = await repo.get(session.session_id)
        if fresh is not None:
            session = fresh
            bound_log = bound_log.bind(waiting_for=session.waiting_for, dialogue_state=session.dialogue_state)

        safe_relay = html.escape(message.text or "")
        if session.waiting_for == "BOTH":
            await _collect_for_both(
                text=message.text or "",
                relay_text=safe_relay,
                message=message,
                session=session,
                sender_label=sender_label,
                bot=bot,
                repo=repo,
                state=state,
            )
        else:
            await _process_turn(
                text=message.text or "",
                relay_text=safe_relay,
                message=message,
                session=session,
                sender_label=sender_label,
                bot=bot,
                repo=repo,
                state=state,
            )


# ─── Голосовые сообщения ──────────────────────────────────────────────────────

@router.message(F.voice)
async def handle_voice_message(
    message: Message,
    bot: Bot,
    redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    user_id = message.from_user.id
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(user_id)

    if session is None:
        return
    if session.user_b_id == 0:
        await message.answer("Ожидаем партнёра. Как только он присоединится — начнём.")
        return

    sender_label = session.partner_name(user_id)
    if sender_label is None:
        return
    bound_log = log.bind(session_id=session.session_id, user_id=user_id, sender=sender_label)

    resume_resolution = None
    if session.resume_context:
        resume_resolution = await get_resume_resolution(redis, session.session_id)
        if resume_resolution is None:
            await message.answer("Сначала выберите на кнопке: продолжить прошлую тему или начать новую.")
            return

    throttle_ok = await _acquire_message_throttle(redis, user_id)
    if not throttle_ok:
        bound_log.info("message_throttled", input_type="voice")
        await message.answer("Нужно немного подождать перед следующим сообщением.")
        return

    lock = _get_lock(session.session_id)
    if lock.locked():
        bound_log.info("voice_rejected_lock_busy")
        await message.answer("Слушаю внимательно...")
        return

    async with lock:
        fresh = await repo.get(session.session_id)
        if fresh is not None:
            session = fresh
            if session.resume_context and resume_resolution is None:
                resume_resolution = await get_resume_resolution(redis, session.session_id)

        await bot.send_chat_action(message.chat.id, "typing")
        try:
            file = await bot.get_file(message.voice.file_id)
            buf = io.BytesIO()
            await bot.download_file(file.file_path, buf)
            text = await _claude.transcribe_voice(buf.getvalue())
        except OpenAIServiceError as exc:
            bound_log.warning("voice_transcription_error", error=str(exc))
            await message.answer(exc.user_message)
            return
        except Exception:
            bound_log.exception("voice_transcription_unexpected_error")
            await message.answer("Не удалось распознать голосовое. Попробуй ещё раз или напиши текстом.")
            return

        if not text:
            await message.answer("Голосовое пустое или неразборчивое. Попробуй ещё раз.")
            return
        if len(text) > MAX_MESSAGE_LENGTH:
            await message.answer(
                "Голосовое получилось слишком длинным после распознавания. "
                "Лучше разбить мысль на несколько коротких сообщений."
            )
            return

        safe_text = html.escape(text)
        await message.answer(f"🎤 <i>{safe_text}</i>")

        if _looks_like_end_session_intent(text):
            if session.close_choice_active:
                await message.answer("Кнопка завершения уже открыта. Если готовы, нажмите её.")
                return
            await _present_direct_end_session_button(session=session, repo=repo, bot=bot)
            return

        if resume_resolution == RESUME_CHOICE_ALIGNMENT_PENDING:
            await _handle_resume_alignment_text(
                session=session,
                user_id=user_id,
                text=text,
                bot=bot,
                redis=redis,
                repo=repo,
            )
            return

        if not session.is_active_speaker(user_id):
            bound_log.info("voice_rejected_not_active_speaker", waiting_for=session.waiting_for)
            await message.answer("Я вижу, тебе есть что сказать. Дождёмся ответа партнёра — скоро будет твоя очередь.")
            return

        if session.waiting_for == "BOTH":
            await _collect_for_both(
                text=text,
                relay_text=f"🎤 <i>{safe_text}</i>",
                message=message,
                session=session,
                sender_label=sender_label,
                bot=bot,
                repo=repo,
                state=state,
            )
        else:
            await _process_turn(
                text=text,
                relay_text=f"🎤 <i>{safe_text}</i>",
                message=message,
                session=session,
                sender_label=sender_label,
                bot=bot,
                repo=repo,
                state=state,
            )


# ─── Режим BOTH: сбор ответов от обоих партнёров ─────────────────────────────

async def _collect_for_both(
    text: str,
    relay_text: str,
    message: Message,
    session: SessionState,
    sender_label: str,
    bot: Bot,
    repo: SessionRepository,
    state: FSMContext,
) -> None:
    """Собирает ответы обоих партнёров, затем отправляет Claude объединённый запрос."""
    partner_id = session.user_b_id if sender_label == "A" else session.user_a_id
    other_name = session.name_b if sender_label == "A" else session.name_a
    await repo.append_event(
        session_id=session.session_id,
        role="user",
        speaker_label=sender_label,
        content=text,
        dialogue_state_before=session.dialogue_state,
        dialogue_state_after=session.dialogue_state,
        waiting_for_before=session.waiting_for,
        waiting_for_after=session.waiting_for,
    )

    # Проверяем не ответил ли уже этот партнёр
    already = session.pending_a_message if sender_label == "A" else session.pending_b_message
    if already:
        await message.answer(f"Ты уже ответил(а). Жду ответа от {html.escape(other_name)}.")
        return

    # Сохраняем ответ
    if sender_label == "A":
        session.pending_a_message = text
    else:
        session.pending_b_message = text

    # Проверяем — ответил ли уже второй партнёр
    other_pending = session.pending_b_message if sender_label == "A" else session.pending_a_message
    if not other_pending:
        session.waiting_since = datetime.utcnow()
        session.timeout_reminders_sent = 0
        await message.answer("Принято. Жду ответа от второго партнёра.")
        await repo.save(session)
        return

    # Оба ответили — собираем объединённое сообщение для Claude
    both_answers = (
        f"{format_participant_dialog_block(session.name_a, html.escape(session.pending_a_message))}\n\n"
        f"{format_participant_dialog_block(session.name_b, html.escape(session.pending_b_message))}"
    )
    combined = (
        f"[A]: {session.pending_a_message}\n"
        f"[B]: {session.pending_b_message}"
    )
    for uid in (session.user_a_id, session.user_b_id):
        if uid:
            try:
                await bot.send_message(uid, both_answers)
            except Exception:
                log.warning(
                    "both_relay_delivery_failed",
                    session_id=session.session_id,
                    target_user_id=uid,
                )
    text_a = session.pending_a_message
    text_b = session.pending_b_message
    session.pending_a_message = ""
    session.pending_b_message = ""
    await repo.save(session)

    if session.dialogue_state == "SETUP" and not session.last_turn_summary:
        setup_seed = _detect_setup_topic_seed(text_a, text_b)
        if setup_seed is not None:
            proposer_label, topic_text, other_kind = setup_seed
            proposer_name = session.name_a if proposer_label == "A" else session.name_b
            log.info(
                "setup_topic_seed_prompt_triggered",
                session_id=session.session_id,
                proposer=proposer_label,
                other_kind=other_kind,
            )
            _apply_next_speaker(session, "BOTH")
            session.last_turn_summary = (
                f"{SETUP_TOPIC_SEED_SUMMARY_PREFIX}"
                f"{proposer_name}: {topic_text[:120].strip()}"
            )
            prompt = _setup_topic_seed_prompt(
                session,
                proposer_label=proposer_label,
                topic_text=topic_text,
                other_kind=other_kind,
            )
            await repo.append_event(
                session_id=session.session_id,
                role="assistant",
                speaker_label="BOT",
                content=prompt,
                dialogue_state_before=session.dialogue_state,
                dialogue_state_after=session.dialogue_state,
                waiting_for_before="BOTH",
                waiting_for_after=session.waiting_for,
                next_speaker="BOTH",
                addressed_to="BOTH",
                risk_flag=False,
            )
            await repo.save(session)
            await _svc(bot, repo).notify_both(session, prompt)
            return

    if (
        session.dialogue_state == "SETUP"
        and not session.last_turn_summary
        and _looks_like_setup_topic_split(text_a, text_b)
    ):
        tokens_a = sorted(_extract_topic_signal_tokens(text_a))
        tokens_b = sorted(_extract_topic_signal_tokens(text_b))
        log.info(
            "setup_topic_split_guard_triggered",
            session_id=session.session_id,
            topic_tokens_a=tokens_a,
            topic_tokens_b=tokens_b,
        )
        _apply_next_speaker(session, "BOTH")
        session.last_turn_summary = SETUP_TOPIC_SPLIT_SUMMARY
        prompt = _setup_topic_split_prompt()
        await repo.append_event(
            session_id=session.session_id,
            role="assistant",
            speaker_label="BOT",
            content=prompt,
            dialogue_state_before=session.dialogue_state,
            dialogue_state_after=session.dialogue_state,
            waiting_for_before="BOTH",
            waiting_for_after=session.waiting_for,
            next_speaker="BOTH",
            addressed_to="BOTH",
            risk_flag=False,
        )
        await repo.save(session)
        await _svc(bot, repo).notify_both(session, prompt)
        return

    await bot.send_chat_action(message.chat.id, "typing")
    if partner_id:
        await bot.send_chat_action(partner_id, "typing")

    address_feedback = _looks_like_address_feedback(combined)

    try:
        reply, risk_detected, next_speaker, response_meta = await _claude.get_facilitator_response(
            session,
            combined,
            "BOTH",
            repo,
            address_feedback=address_feedback,
            feedback_target=None,
        )
    except OpenAIServiceError as exc:
        log.warning("facilitator_api_error", session_id=session.session_id, mode="both", error=str(exc))
        await message.answer(exc.user_message)
        return
    except Exception:
        log.exception("facilitator_unexpected_error", session_id=session.session_id, mode="both")
        await message.answer("Не удалось получить ответ фасилитатора. Попробуй ещё раз.")
        return

    if risk_detected:
        session.risk_flag = True
        session.risk_details = f"BOTH mode: {combined[:100]}"
        log.warning(
            "risk_flag_triggered",
            session_id=session.session_id,
            mode="both",
            details=session.risk_details,
        )
        await _notify_admins_about_risk(bot, session)
        svc = _svc(bot, repo)
        await svc.end_session(session)
        await svc.notify_both(session, html.escape(reply))
        await svc.notify_both(
            session,
            "Сессия остановлена. Если кому-то сейчас небезопасно, "
            "пожалуйста, обратитесь за немедленной очной помощью.",
            reply_markup=post_session_keyboard(),
        )
        await _claude.clear_history(session.session_id, repo)
        if session.ephemeral_mode:
            await repo.delete(session)
        _release_lock(session.session_id)
        return

    dialogue_state_before = response_meta.get("dialogue_state_before")
    waiting_for_before = response_meta.get("waiting_for_before")
    explicit_addressee = _detect_explicit_reply_addressee(session, reply)
    if explicit_addressee in ("A", "B", "BOTH") and explicit_addressee != next_speaker:
        log.info(
            "facilitator_reply_routing_observed_conflict",
            session_id=session.session_id,
            next_speaker_was=next_speaker,
            detected_addressee=explicit_addressee,
        )
    _apply_next_speaker(session, next_speaker)
    signature, keyboard = _reply_extras(session)
    full_reply = reply + signature
    await repo.append_event(
        session_id=session.session_id,
        role="assistant",
        speaker_label="BOT",
        content=full_reply,
        dialogue_state_before=dialogue_state_before if isinstance(dialogue_state_before, str) else None,
        dialogue_state_after=session.dialogue_state,
        waiting_for_before=waiting_for_before if isinstance(waiting_for_before, str) else None,
        waiting_for_after=session.waiting_for,
        next_speaker=next_speaker,
        addressed_to=response_meta.get("addressed_to") if isinstance(response_meta.get("addressed_to"), str) else None,
        risk_flag=bool(response_meta.get("risk_flag")),
    )
    await repo.save(session)

    for uid in (session.user_a_id, session.user_b_id):
        if uid:
            try:
                await bot.send_message(uid, format_bot_dialog_message(full_reply), reply_markup=keyboard)
            except Exception:
                log.warning(
                    "both_bot_reply_delivery_failed",
                    session_id=session.session_id,
                    target_user_id=uid,
                )


# ─── Обычный ход (один отправитель) ──────────────────────────────────────────

async def _process_turn(
    text: str,
    relay_text: str,
    message: Message,
    session: SessionState,
    sender_label: str,
    bot: Bot,
    repo: SessionRepository,
    state: FSMContext,
) -> None:
    sender_name = session.name_a if sender_label == "A" else session.name_b
    partner_id = session.user_b_id if sender_label == "A" else session.user_a_id
    await repo.append_event(
        session_id=session.session_id,
        role="user",
        speaker_label=sender_label,
        content=text,
        dialogue_state_before=session.dialogue_state,
        dialogue_state_after=session.dialogue_state,
        waiting_for_before=session.waiting_for,
        waiting_for_after=session.waiting_for,
    )

    # Передать сообщение партнёру
    if partner_id and partner_id != message.from_user.id:
        try:
            await bot.send_message(
                partner_id,
                f"<b>{format_participant_dialog_label(sender_name)}:</b> {relay_text}",
            )
        except Exception:
            log.exception(
                "partner_message_relay_failed",
                session_id=session.session_id,
                sender=sender_label,
                partner_id=partner_id,
            )

    await bot.send_chat_action(message.from_user.id, "typing")
    if partner_id:
        await bot.send_chat_action(partner_id, "typing")

    address_feedback = _looks_like_address_feedback(text)
    loop_mode_shift_response = await _maybe_apply_loop_mode_shift(
        session=session,
        repo=repo,
        text=text,
        sender_label=sender_label,
    )

    if loop_mode_shift_response is not None:
        reply, risk_detected, next_speaker, response_meta = loop_mode_shift_response
    else:
        try:
            reply, risk_detected, next_speaker, response_meta = await _claude.get_facilitator_response(
                session,
                text,
                sender_name,
                repo,
                address_feedback=address_feedback,
                feedback_target=sender_label,
            )
        except OpenAIServiceError as exc:
            log.warning("facilitator_api_error", session_id=session.session_id, mode="single", error=str(exc))
            await message.answer(exc.user_message)
            return
        except Exception:
            log.exception("facilitator_unexpected_error", session_id=session.session_id, mode="single")
            await message.answer("Не удалось получить ответ фасилитатора. Попробуй ещё раз.")
            return

    if risk_detected:
        session.risk_flag = True
        session.risk_details = f"Triggered by [{sender_name}]: {text[:100]}"
        log.warning(
            "risk_flag_triggered",
            session_id=session.session_id,
            mode="single",
            details=session.risk_details,
        )
        await _notify_admins_about_risk(bot, session)
        svc = _svc(bot, repo)
        await svc.end_session(session)
        await svc.notify_both(session, html.escape(reply))
        await svc.notify_both(
            session,
            "Сессия остановлена. Если кому-то сейчас небезопасно, "
            "пожалуйста, обратитесь за немедленной очной помощью.",
            reply_markup=post_session_keyboard(),
        )
        await _claude.clear_history(session.session_id, repo)
        if session.ephemeral_mode:
            await repo.delete(session)
        _release_lock(session.session_id)
        return

    dialogue_state_before = response_meta.get("dialogue_state_before")
    waiting_for_before = response_meta.get("waiting_for_before")
    explicit_addressee = _detect_explicit_reply_addressee(session, reply)
    if explicit_addressee in ("A", "B", "BOTH") and explicit_addressee != next_speaker:
        log.info(
            "facilitator_reply_routing_observed_conflict",
            session_id=session.session_id,
            next_speaker_was=next_speaker,
            detected_addressee=explicit_addressee,
        )
    _apply_next_speaker(session, next_speaker)
    signature, keyboard = _reply_extras(session)
    full_reply = reply + signature
    await repo.append_event(
        session_id=session.session_id,
        role="assistant",
        speaker_label="BOT",
        content=full_reply,
        dialogue_state_before=dialogue_state_before if isinstance(dialogue_state_before, str) else None,
        dialogue_state_after=session.dialogue_state,
        waiting_for_before=waiting_for_before if isinstance(waiting_for_before, str) else None,
        waiting_for_after=session.waiting_for,
        next_speaker=next_speaker,
        addressed_to=response_meta.get("addressed_to") if isinstance(response_meta.get("addressed_to"), str) else None,
        risk_flag=bool(response_meta.get("risk_flag")),
    )
    await repo.save(session)

    for uid in (message.from_user.id, partner_id):
        if uid and uid not in (0, None):
            try:
                await bot.send_message(uid, format_bot_dialog_message(full_reply), reply_markup=keyboard)
            except Exception:
                log.warning(
                    "single_bot_reply_delivery_failed",
                    session_id=session.session_id,
                    target_user_id=uid,
                )


def _svc(bot: Bot, repo: SessionRepository) -> SessionService:
    return SessionService(repo, bot)
