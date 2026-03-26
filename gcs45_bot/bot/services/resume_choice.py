from __future__ import annotations

from typing import Iterable

from redis.asyncio import Redis

RESUME_CHOICE_CONTINUE = "continue"
RESUME_CHOICE_NEW_TOPIC = "new_topic"
RESUME_CHOICE_FLEXIBLE = "flexible"
RESUME_CHOICE_ALIGNMENT_PENDING = "alignment_pending"
RESUME_CHOICE_TTL_SECONDS = 60 * 60 * 24

_CONTINUE_MARKERS = (
    "продолж",
    "с этого места",
    "прошлую тему",
    "эту тему",
    "вернуться к прошлому",
)
_NEW_TOPIC_MARKERS = (
    "новую тему",
    "начать заново",
    "начать новую",
    "сначала",
    "не продолжать",
    "не похоже",
    "не то",
)
_FLEXIBLE_MARKERS = (
    "без разницы",
    "мне ок любой вариант",
    "мне ок любой",
    "мне подойдет любой",
    "мне подойдет любой",
    "любой вариант",
    "как вам удобнее",
    "как вам лучше",
    "как хотите",
    "как скажете",
    "не важно",
    "неважно",
    "можно и так и так",
    "можно как угодно",
    "могу и так и так",
)


def normalize_resume_choice(raw_choice: str | None) -> str | None:
    mapping = {
        "continue": RESUME_CHOICE_CONTINUE,
        "session:resume_continue": RESUME_CHOICE_CONTINUE,
        "new_topic": RESUME_CHOICE_NEW_TOPIC,
        "session:resume_new_topic": RESUME_CHOICE_NEW_TOPIC,
        "not_accurate": RESUME_CHOICE_NEW_TOPIC,
        "session:resume_not_accurate": RESUME_CHOICE_NEW_TOPIC,
    }
    return mapping.get(raw_choice or "")


def classify_resume_resolution_text(text: str) -> str | None:
    normalized = " ".join((text or "").strip().lower().replace("ё", "е").split())
    if not normalized:
        return None
    if any(marker in normalized for marker in _FLEXIBLE_MARKERS):
        return RESUME_CHOICE_FLEXIBLE
    has_continue = any(marker in normalized for marker in _CONTINUE_MARKERS)
    has_new_topic = any(marker in normalized for marker in _NEW_TOPIC_MARKERS)
    if has_continue and not has_new_topic:
        return RESUME_CHOICE_CONTINUE
    if has_new_topic and not has_continue:
        return RESUME_CHOICE_NEW_TOPIC
    return None


def decide_resume_resolution(
    text_a: str,
    text_b: str,
    *,
    default_resolution: str | None = None,
) -> str | None:
    choice_a = classify_resume_resolution_text(text_a)
    choice_b = classify_resume_resolution_text(text_b)
    concrete_choices = {RESUME_CHOICE_CONTINUE, RESUME_CHOICE_NEW_TOPIC}

    if choice_a in concrete_choices and choice_a == choice_b:
        return choice_a
    if choice_a == RESUME_CHOICE_FLEXIBLE and choice_b in concrete_choices:
        return choice_b
    if choice_b == RESUME_CHOICE_FLEXIBLE and choice_a in concrete_choices:
        return choice_a
    if choice_a == RESUME_CHOICE_FLEXIBLE and choice_b == RESUME_CHOICE_FLEXIBLE:
        return default_resolution
    return None


def _vote_key(session_id: str, user_id: int) -> str:
    return f"resume_vote:{session_id}:{user_id}"


def _resolution_key(session_id: str) -> str:
    return f"resume_resolution:{session_id}"


def _reply_key(session_id: str, user_id: int) -> str:
    return f"resume_alignment_reply:{session_id}:{user_id}"


async def get_resume_resolution(redis: Redis, session_id: str) -> str | None:
    value = await redis.get(_resolution_key(session_id))
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value or None


async def _set_resume_resolution(redis: Redis, session_id: str, resolution: str) -> None:
    await redis.set(_resolution_key(session_id), resolution, ex=RESUME_CHOICE_TTL_SECONDS)


async def get_resume_vote(redis: Redis, session_id: str, user_id: int) -> str | None:
    value = await redis.get(_vote_key(session_id, user_id))
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value or None


async def _set_resume_vote(redis: Redis, session_id: str, user_id: int, choice: str) -> None:
    await redis.set(_vote_key(session_id, user_id), choice, ex=RESUME_CHOICE_TTL_SECONDS)


async def _clear_resume_votes(redis: Redis, session_id: str, user_ids: Iterable[int]) -> None:
    await redis.delete(*[_vote_key(session_id, user_id) for user_id in user_ids])


async def record_resume_vote(
    redis: Redis,
    *,
    session_id: str,
    user_id: int,
    user_a_id: int,
    user_b_id: int,
    choice: str,
) -> tuple[str, str | None]:
    resolution = await get_resume_resolution(redis, session_id)
    if resolution in (RESUME_CHOICE_CONTINUE, RESUME_CHOICE_NEW_TOPIC, RESUME_CHOICE_ALIGNMENT_PENDING):
        return "resolved", resolution

    existing_vote = await get_resume_vote(redis, session_id, user_id)
    if existing_vote is not None:
        return "duplicate", existing_vote

    await _set_resume_vote(redis, session_id, user_id, choice)
    vote_a = await get_resume_vote(redis, session_id, user_a_id)
    vote_b = await get_resume_vote(redis, session_id, user_b_id)

    if not vote_a or not vote_b:
        return "waiting", choice

    if vote_a == vote_b:
        await _set_resume_resolution(redis, session_id, vote_a)
        await _clear_resume_votes(redis, session_id, (user_a_id, user_b_id))
        return "matched", vote_a

    await _set_resume_resolution(redis, session_id, RESUME_CHOICE_ALIGNMENT_PENDING)
    await _clear_resume_votes(redis, session_id, (user_a_id, user_b_id))
    return "mismatch", None


async def clear_resume_resolution(redis: Redis, session_id: str) -> None:
    await redis.delete(_resolution_key(session_id))


async def save_alignment_reply(redis: Redis, session_id: str, user_id: int, text: str) -> None:
    await redis.set(_reply_key(session_id, user_id), text, ex=RESUME_CHOICE_TTL_SECONDS)


async def get_alignment_replies(
    redis: Redis,
    *,
    session_id: str,
    user_a_id: int,
    user_b_id: int,
) -> tuple[str | None, str | None]:
    reply_a = await redis.get(_reply_key(session_id, user_a_id))
    reply_b = await redis.get(_reply_key(session_id, user_b_id))
    if isinstance(reply_a, bytes):
        reply_a = reply_a.decode("utf-8")
    if isinstance(reply_b, bytes):
        reply_b = reply_b.decode("utf-8")
    return reply_a, reply_b


async def process_alignment_reply(
    redis: Redis,
    *,
    session_id: str,
    user_id: int,
    user_a_id: int,
    user_b_id: int,
    text: str,
    default_resolution: str | None = None,
) -> tuple[str, str | None, str | None, str | None]:
    await save_alignment_reply(redis, session_id, user_id, text)
    reply_a, reply_b = await get_alignment_replies(
        redis,
        session_id=session_id,
        user_a_id=user_a_id,
        user_b_id=user_b_id,
    )

    if not reply_a or not reply_b:
        return "waiting", None, None, None

    choice_a = classify_resume_resolution_text(str(reply_a))
    choice_b = classify_resume_resolution_text(str(reply_b))
    resolution = decide_resume_resolution(
        str(reply_a),
        str(reply_b),
        default_resolution=default_resolution,
    )

    if resolution is None:
        return "retry", None, choice_a, choice_b

    await redis.delete(_reply_key(session_id, user_a_id), _reply_key(session_id, user_b_id))
    await _set_resume_resolution(redis, session_id, resolution)
    return "resolved", resolution, choice_a, choice_b


async def clear_alignment_replies(redis: Redis, session_id: str, user_ids: Iterable[int]) -> None:
    await redis.delete(*[_reply_key(session_id, user_id) for user_id in user_ids])


async def reset_resume_choice_state(redis: Redis, session_id: str, user_ids: Iterable[int]) -> None:
    await clear_resume_resolution(redis, session_id)
    await _clear_resume_votes(redis, session_id, user_ids)
    await clear_alignment_replies(redis, session_id, user_ids)
