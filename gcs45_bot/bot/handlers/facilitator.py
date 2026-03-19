from __future__ import annotations

import asyncio
import html
import io
from datetime import datetime

from aiogram import Router, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker
import structlog

from bot.fsm.states import SessionFlow
from bot.models.session import SessionState
from bot.repositories.session_repo import SessionRepository
from bot.services.claude_service import MAX_MESSAGE_LENGTH, OpenAIServiceError
from bot.services.session_service import SessionService
from bot.services.shared import claude as _claude
from bot.utils.keyboards import post_session_keyboard, end_session_keyboard, end_session_button, main_menu_keyboard

router = Router(name="facilitator")
log = structlog.get_logger()

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


def _get_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _locks:
        _locks[session_id] = asyncio.Lock()
    return _locks[session_id]


def _release_lock(session_id: str) -> None:
    """Освобождаем память при завершении сессии."""
    _locks.pop(session_id, None)


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


def _looks_like_address_feedback(message: str) -> bool:
    normalized = _normalize_text(message)
    return any(pattern in normalized for pattern in ADDRESS_FEEDBACK_PATTERNS)


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
    - обычная фаза → подпись + тихая кнопка завершения
    """
    if session.phase == "closing":
        return "", end_session_keyboard()
    return _speaker_signature(session), end_session_button()


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

    # Триггер завершения сессии — от любого участника
    if message.text and message.text.strip().lower() == "закончить сессию":
        await message.answer("Вы хотите завершить сессию?", reply_markup=end_session_keyboard())
        return
    if message.text and len(message.text) > MAX_MESSAGE_LENGTH:
        await message.answer(
            "Сообщение получилось слишком длинным. Лучше выделить главное и отправить короче."
        )
        return

    if not session.is_active_speaker(user_id):
        bound_log.info("turn_rejected_not_active_speaker", waiting_for=session.waiting_for)
        await message.answer("Я вижу, тебе есть что сказать. Дождёмся ответа партнёра — скоро будет твоя очередь.")
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

    if not session.is_active_speaker(user_id):
        bound_log.info("voice_rejected_not_active_speaker", waiting_for=session.waiting_for)
        await message.answer("Я вижу, тебе есть что сказать. Дождёмся ответа партнёра — скоро будет твоя очередь.")
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
        f"<b>{html.escape(session.name_a)}:</b>\n"
        f"{html.escape(session.pending_a_message)}\n\n"
        f"<b>{html.escape(session.name_b)}:</b>\n"
        f"{html.escape(session.pending_b_message)}"
    )
    combined = (
        f"[{session.name_a}]: {session.pending_a_message}\n"
        f"[{session.name_b}]: {session.pending_b_message}"
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
    session.pending_a_message = ""
    session.pending_b_message = ""
    await repo.save(session)

    await bot.send_chat_action(message.chat.id, "typing")
    if partner_id:
        await bot.send_chat_action(partner_id, "typing")

    address_feedback = _looks_like_address_feedback(combined)

    try:
        reply, risk_detected, next_speaker, response_meta = await _claude.get_facilitator_response(
            session,
            combined,
            f"{session.name_a} и {session.name_b}",
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
        await svc.notify_both(session, reply)
        await svc.notify_both(
            session,
            "Сессия остановлена. Если кому-то сейчас небезопасно:\n"
            "🇷🇺 8-800-2000-122 (бесплатно)\n"
            "🇺🇦 0 800 500 335 (бесплатно)\n"
            "🇰🇿 150 (психологическая помощь)\n"
            "Экстренные службы: 112",
            reply_markup=post_session_keyboard(),
        )
        await _claude.clear_history(session.session_id, repo)
        if session.ephemeral_mode:
            await repo.delete(session)
        _release_lock(session.session_id)
        return

    dialogue_state_before = response_meta.get("dialogue_state_before")
    waiting_for_before = response_meta.get("waiting_for_before")
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
                await bot.send_message(uid, full_reply, reply_markup=keyboard)
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
            await bot.send_message(partner_id, f"<b>{html.escape(sender_name)}:</b> {relay_text}")
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
        await svc.notify_both(session, reply)
        await svc.notify_both(
            session,
            "Сессия остановлена. Если кому-то сейчас небезопасно:\n"
            "🇷🇺 8-800-2000-122 (бесплатно)\n"
            "🇺🇦 0 800 500 335 (бесплатно)\n"
            "🇰🇿 150 (психологическая помощь)\n"
            "Экстренные службы: 112",
            reply_markup=post_session_keyboard(),
        )
        await _claude.clear_history(session.session_id, repo)
        if session.ephemeral_mode:
            await repo.delete(session)
        _release_lock(session.session_id)
        return

    dialogue_state_before = response_meta.get("dialogue_state_before")
    waiting_for_before = response_meta.get("waiting_for_before")
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
                await bot.send_message(uid, full_reply, reply_markup=keyboard)
            except Exception:
                log.warning(
                    "single_bot_reply_delivery_failed",
                    session_id=session.session_id,
                    target_user_id=uid,
                )


def _svc(bot: Bot, repo: SessionRepository) -> SessionService:
    return SessionService(repo, bot)
