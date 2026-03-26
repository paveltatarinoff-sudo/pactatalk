from __future__ import annotations

import html
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker
import structlog

from bot.fsm.states import UserFlow, SessionFlow
from bot.config import settings
from bot.handlers.privacy import send_data_dashboard
from bot.models.session import SessionState
from bot.repositories.session_repo import SessionRepository
from bot.services.resume_choice import (
    RESUME_CHOICE_ALIGNMENT_PENDING,
    RESUME_CHOICE_CONTINUE,
    RESUME_CHOICE_NEW_TOPIC,
    get_resume_resolution,
    normalize_resume_choice,
    record_resume_vote,
    reset_resume_choice_state,
)
from bot.services.session_service import SessionService
from bot.services.session_service import format_bot_dialog_message
from bot.services.shared import claude as _claude
from bot.handlers.menu import decode_summary_meta, encode_summary_meta
from bot.handlers.facilitator import (
    _clear_end_session_choice_buttons,
    _present_end_session_choice,
    _release_lock,
)
from bot.utils.keyboards import (
    data_actions_keyboard,
    session_control_keyboard,
    join_confirm_keyboard,
    main_menu_keyboard,
    post_session_keyboard,
    resume_confirmation_keyboard,
)

router = Router(name="session")
log = structlog.get_logger()

JOIN_TARGET_USE_EXISTING = "use_existing"
JOIN_TARGET_JOIN = "join"
JOIN_TARGET_INVALID = "invalid"
JOIN_TARGET_SELF = "self"
JOIN_TARGET_BLOCK_ACTIVE = "block_active"


def _make_service(bot: Bot, redis: Redis, session_factory: Optional[async_sessionmaker] = None) -> SessionService:
    return SessionService(SessionRepository(redis, session_factory), bot)


async def _safe_answer_callback(callback: CallbackQuery) -> None:
    try:
        await callback.answer()
    except Exception:
        log.warning(
            "callback_answer_failed",
            user_id=callback.from_user.id,
            callback_data=callback.data,
        )


async def _delete_or_clear_callback_message(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.delete()
        return
    except Exception:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        log.warning(
            "callback_menu_cleanup_failed",
            user_id=callback.from_user.id,
            callback_data=callback.data,
            message_id=getattr(callback.message, "message_id", 0),
        )


def _is_orphan_waiting_session(session: SessionState, user_id: int) -> bool:
    return session.user_a_id == user_id and session.user_b_id == 0


async def _resolve_join_target(
    repo: SessionRepository,
    *,
    user_id: int,
    code: str,
) -> tuple[str, Optional[SessionState], Optional[SessionState]]:
    normalized_code = code.upper()
    existing = await repo.get_by_user(user_id)

    if (
        existing is not None
        and (existing.invite_code or "").upper() == normalized_code
        and existing.user_b_id == user_id
    ):
        return JOIN_TARGET_USE_EXISTING, existing, None

    target = await repo.get_by_invite(normalized_code)
    if target is None:
        return JOIN_TARGET_INVALID, None, None

    if target.user_a_id == user_id:
        return JOIN_TARGET_SELF, None, None

    if existing is None:
        return JOIN_TARGET_JOIN, target, None

    if existing.session_id == target.session_id:
        return JOIN_TARGET_USE_EXISTING, existing, None

    if _is_orphan_waiting_session(existing, user_id):
        return JOIN_TARGET_JOIN, target, existing

    return JOIN_TARGET_BLOCK_ACTIVE, None, existing


async def _cleanup_orphan_waiting_session(
    repo: SessionRepository,
    state: FSMContext,
    session: SessionState,
) -> None:
    log.info(
        "join_replaces_orphan_waiting_session",
        session_id=session.session_id,
        user_id=session.user_a_id,
    )
    await repo.delete_session_artifacts(session.session_id)
    await state.clear()


async def _clear_resume_confirmation_buttons(session: SessionState, bot: Bot) -> None:
    for chat_id, message_id, side in (
        (session.user_a_id, session.first_msg_id_a, "A"),
        (session.user_b_id, session.first_msg_id_b, "B"),
    ):
        if not message_id:
            continue
        try:
            await bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
        except Exception:
            log.warning(
                "resume_choice_clear_buttons_failed",
                session_id=session.session_id,
                side=side,
                user_id=chat_id,
                message_id=message_id,
            )


async def _clear_single_resume_button(callback: CallbackQuery, session_id: str) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        log.warning(
            "resume_choice_clear_single_button_failed",
            session_id=session_id,
            user_id=callback.from_user.id,
            message_id=callback.message.message_id,
        )


def _setup_question_block() -> str:
    return (
        "Первый вопрос к каждому из вас:\n"
        "с какой темы вам важнее всего начать сегодня?"
    )


def _regular_setup_intro() -> str:
    return (
        "Вы оба в сессии. Начинаем.\n\n"
        "Я помогу вам провести этот разговор более спокойно, ясно и по очереди. "
        "Буду удерживать фокус, задавать вопросы, помогать распаковывать сложные чувства "
        "и переводить разговор к лучшему пониманию и возможным договорённостям.\n\n"
        "Во время сессии я могу:\n"
        "• задавать вопросы вам обоим и каждому лично;\n"
        "• помогать точнее назвать, что вы чувствуете и что хотите донести;\n"
        "• объяснять напряжённые или сложные моменты простым языком;\n"
        "• предлагать более удачные формулировки и направления разговора;\n"
        "• опираться на сильные подходы фасилитации и коммуникации.\n\n"
        "Вы можете:\n"
        "• отвечать текстом или голосом;\n"
        "• задавать мне вопросы;\n"
        "• поправлять меня, если я неточен;\n"
        "• в любой момент написать, что хотите завершить сессию, или сделать это через меню Telegram.\n\n"
        f"{_setup_question_block()}"
    )


def _resume_confirmation_intro(session: SessionState) -> str:
    safe_resume = html.escape(session.resume_context)
    return (
        f"С возвращением! Я помню ваш прошлый разговор.\n\n"
        f"Вот как я его запомнил:\n\n"
        f"<blockquote>{safe_resume}</blockquote>\n\n"
        f"Если это похоже на ваш прошлый разговор, можно продолжить с этого места. "
        f"Если нет — начнём заново.\n\n"
        f"Выберите оба, как хотите начать этот разговор."
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


def _resume_alignment_intro() -> str:
    return (
        "Вы выбрали по-разному: один хочет продолжить прошлую тему, другой — начать новую.\n\n"
        "Напишите каждый одним-двумя предложениями: <b>вам сейчас важнее продолжить прошлую тему, "
        "начать новую или вам ок любой вариант — и почему?</b>\n"
        "Отвечайте независимо — я подожду ответы от вас обоих."
    )


def _build_post_session_survey_url(base_url: str, *, session_id: str, role: str) -> str:
    if not base_url:
        return ""

    parsed = urlsplit(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(
        {
            "session_id": session_id,
            "role": role,
            "source": "telegram_post_session",
        }
    )
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _post_session_summary_text(summary_text: str, *, has_survey: bool) -> str:
    survey_block = ""
    if has_survey:
        survey_block = (
            "\n\nЕсли захочешь помочь улучшить PactaTalk, "
            "ответь на 6 коротких вопросов ниже. Это займёт около 2 минут."
        )

    return (
        f"Сессия завершена.\n\n"
        f"📋 <b>Краткий итог разговора</b>\n\n"
        f"{html.escape(summary_text or 'Итог разговора сохранён.')}\n\n"
        f"Итог уже сохранён в разделе <b>«Мои итоги»</b>."
        f"{survey_block}"
    )


def _resume_alignment_retry_intro() -> str:
    return (
        "Пока у вас не сложилось общее решение.\n\n"
        "Напишите ещё раз коротко и прямо одним из вариантов: "
        "<b>продолжить прошлую тему</b>, <b>начать новую</b> или "
        "<b>мне ок любой вариант</b>."
    )


def _apply_resume_resolution(session: SessionState, resolution: str) -> str:
    if resolution == RESUME_CHOICE_CONTINUE:
        return _resume_continue_intro(session)

    session.resume_context = ""
    return _regular_setup_intro()


# ─── /new_session ────────────────────────────────────────────────────────────

@router.message(Command("new_session"))
@router.callback_query(F.data == "session:new")
async def cmd_new_session(
    event: Message | CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    msg = event if isinstance(event, Message) else event.message
    if msg is None:
        return

    user_id = event.from_user.id

    repo = SessionRepository(redis, session_factory)
    svc = SessionService(repo, bot)

    if isinstance(event, CallbackQuery):
        await _safe_answer_callback(event)
        await _delete_or_clear_callback_message(event)

    # Атомарная блокировка — защита от гонки при двойном нажатии
    lock_key = f"lock:create_session:{user_id}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=5)
    if not acquired:
        return

    try:
        # Проверить нет ли уже активной сессии
        existing = await svc.get_user_session(user_id)
        if existing is not None:
            await msg.answer("У тебя уже есть активная сессия. Используй /status или /end_session.")
            return

        session = await svc.create_session(user_id)
        log.info("session_created", session_id=session.session_id, user_id=user_id)

        try:
            bot_info = await bot.get_me()
            invite_link = f"https://t.me/{bot_info.username}?start=join_{session.invite_code}"

            await msg.answer("Перешли следующее сообщение партнёру 👇")
            await msg.answer(
                f"<b>Вас пригласили в диалог в PactaTalk</b>\n\n"
                f"PactaTalk помогает парам спокойно обсуждать сложные темы шаг за шагом.\n"
                f"Это не терапия, а инструмент для бережного диалога.\n\n"
                f"Если вам подходит такой формат, присоединяйтесь к сессии.\n\n"
                f"{invite_link}"
            )
        except Exception:
            log.exception(
                "session_invite_delivery_failed",
                session_id=session.session_id,
                user_id=user_id,
            )
            await repo.delete_session_artifacts(session.session_id)
            await state.clear()
            await msg.answer(
                "Не удалось создать сессию из-за временной ошибки. Попробуй ещё раз через несколько секунд."
            )
            return

        await state.set_state(SessionFlow.waiting_partner)
        await state.update_data(session_id=session.session_id)
    finally:
        await redis.delete(lock_key)


# ─── /join ───────────────────────────────────────────────────────────────────

@router.message(Command("join"))
@router.callback_query(F.data == "session:join")
async def cmd_join(
    event: Message | CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    msg = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id

    if isinstance(event, CallbackQuery):
        await _safe_answer_callback(event)

    # Извлечь код из команды: /join XXXXXX
    code = None
    if isinstance(event, Message) and event.text:
        parts = event.text.strip().split()
        if len(parts) == 2:
            code = parts[1].upper()

    if not code:
        await state.set_state(UserFlow.joining)
        if isinstance(event, CallbackQuery):
            await _delete_or_clear_callback_message(event)
        await msg.answer("Введи инвайт-код от партнёра:")
        return

    await _process_join(msg, user_id, code, bot, redis, session_factory, state)


@router.message(UserFlow.joining)
async def handle_join_code_input(
    message: Message,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    code = message.text.strip().upper() if message.text else ""
    if not code:
        await message.answer("Пожалуйста, введи код (6 символов):")
        return
    await _process_join(message, message.from_user.id, code, bot, redis, session_factory, state)


async def _process_join(
    msg: Message,
    user_id: int,
    code: str,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    code = code.upper()
    repo = SessionRepository(redis, session_factory)
    svc = SessionService(repo, bot)

    # Атомарная блокировка invite-кода — защита от двойного join с одним кодом
    lock_key = f"lock:join:{code}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=10)
    if not acquired:
        await msg.answer("Этот код уже используется. Попробуй через несколько секунд.")
        return

    cleanup_notice = ""
    try:
        action, _, orphan_session = await _resolve_join_target(repo, user_id=user_id, code=code)
        if action == JOIN_TARGET_INVALID:
            await msg.answer(
                "Код не найден или уже использован.\n"
                "Проверь код и попробуй снова, или попроси партнёра создать новую сессию."
            )
            return

        if action == JOIN_TARGET_SELF:
            await msg.answer("Это твоя собственная сессия. Перешли приглашение партнёру.")
            return

        if action == JOIN_TARGET_BLOCK_ACTIVE:
            await msg.answer(
                "У тебя уже есть другая активная сессия. Сначала заверши её через /status или /end_session."
            )
            return

        if orphan_session is not None:
            await _cleanup_orphan_waiting_session(repo, state, orphan_session)
            cleanup_notice = (
                "У тебя была незавершённая сессия ожидания. "
                "Я закрыл её и присоединил тебя к приглашению партнёра.\n\n"
            )

        session = await svc.join_session(user_id, code)
        if session is None:
            await msg.answer(
                "Код не найден или уже использован.\n"
                "Проверь код и попробуй снова, или попроси партнёра создать новую сессию."
            )
            return
    finally:
        await redis.delete(lock_key)

    log.info("session_joined", session_id=session.session_id, user_id=user_id)

    await state.set_state(SessionFlow.opening)
    await state.update_data(session_id=session.session_id)

    # BUG-011: безопасное получение имён
    try:
        chat_a = await bot.get_chat(session.user_a_id)
        partner_name = chat_a.first_name or chat_a.username or "Партнёр"
    except Exception:
        log.warning(
            "get_chat_failed_fallback_name",
            context="join_partner_name",
            session_id=session.session_id,
            user_id=session.user_a_id,
        )
        partner_name = "Партнёр"
    partner_name = html.escape(partner_name)

    try:
        chat_b = await bot.get_chat(user_id)
        joiner_name = chat_b.first_name or chat_b.username or "Партнёр"
    except Exception:
        log.warning(
            "get_chat_failed_fallback_name",
            context="join_joiner_name",
            session_id=session.session_id,
            user_id=user_id,
        )
        joiner_name = "Партнёр"
    joiner_name = html.escape(joiner_name)

    # Уведомить B
    await msg.answer(
        f"{cleanup_notice}"
        f"Отлично! Ты присоединился к сессии с {partner_name}.\n\n"
        f"Нажми кнопку ниже чтобы подтвердить — и мы начнём.",
        reply_markup=join_confirm_keyboard(code),
    )

    # Уведомить A
    try:
        await bot.send_message(
            session.user_a_id,
            f"{joiner_name} присоединился к сессии!\n\nОжидаем его подтверждения...",
        )
    except Exception:
        log.warning(
            "session_join_notify_a_failed",
            session_id=session.session_id,
            user_id=session.user_a_id,
        )


# ─── Подтверждение присоединения ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("join:confirm:"))
async def cb_join_confirm(
    callback: CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    code = callback.data.split(":")[-1].upper()
    repo = SessionRepository(redis, session_factory)
    svc = SessionService(repo, bot)

    lock_key = f"lock:join:{code}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=10)
    if not acquired:
        await callback.answer("Этот код уже используется. Попробуй через несколько секунд.", show_alert=True)
        return

    try:
        action, existing_session, orphan_session = await _resolve_join_target(repo, user_id=user_id, code=code)
        if action == JOIN_TARGET_INVALID:
            await callback.answer("Сессия не найдена или код истёк.", show_alert=True)
            return

        if action == JOIN_TARGET_SELF:
            await callback.answer("Это твоя сессия. Перешли приглашение партнёру.", show_alert=True)
            return

        if action == JOIN_TARGET_BLOCK_ACTIVE:
            await callback.answer(
                "У тебя уже есть другая активная сессия. Сначала заверши её через /end_session.",
                show_alert=True,
            )
            return

        await _safe_answer_callback(callback)
        await _delete_or_clear_callback_message(callback)

        if orphan_session is not None:
            await _cleanup_orphan_waiting_session(repo, state, orphan_session)
            if callback.message is not None:
                await callback.message.answer(
                    "У тебя была незавершённая сессия ожидания. "
                    "Я закрыл её и присоединил тебя к приглашению партнёра."
                )

        if action == JOIN_TARGET_USE_EXISTING:
            session = existing_session
        else:
            session = await svc.join_session(user_id, code)
            if session is None:
                if callback.message is not None:
                    await callback.message.answer(
                        "Код не найден или уже использован. Попроси партнёра создать новую сессию."
                    )
                return
    finally:
        await redis.delete(lock_key)

    # Сохраняем имена участников (BUG-011: защита от ошибок get_chat)
    try:
        chat_a = await bot.get_chat(session.user_a_id)
        session.name_a = chat_a.first_name or chat_a.username or "Партнёр A"
    except Exception:
        log.warning(
            "get_chat_failed_fallback_name",
            context="join_confirm_name_a",
            session_id=session.session_id,
            user_id=session.user_a_id,
        )
        session.name_a = "Партнёр A"
    try:
        chat_b = await bot.get_chat(user_id)
        session.name_b = chat_b.first_name or chat_b.username or "Партнёр B"
    except Exception:
        log.warning(
            "get_chat_failed_fallback_name",
            context="join_confirm_name_b",
            session_id=session.session_id,
            user_id=user_id,
        )
        session.name_b = "Партнёр B"

    # Load resume from previous session (P3.1)
    try:
        pair_resume = await repo.get_pair_resume(session.user_a_id, session.user_b_id)
        if pair_resume:
            # Validate names to prevent cross-pair contamination
            stored_names = {pair_resume.name_a.lower().strip(), pair_resume.name_b.lower().strip()} - {""}
            current_names = {(session.name_a or "").lower().strip(), (session.name_b or "").lower().strip()} - {""}
            if stored_names and current_names and not stored_names & current_names:
                log.warning(
                    "pair_resume_name_mismatch",
                    session_id=session.session_id,
                    stored_names=list(stored_names),
                    current_names=list(current_names),
                )
            else:
                session.resume_context = pair_resume.resume_context
                log.info(
                    "pair_resume_loaded",
                    session_id=session.session_id,
                    stored_names=[pair_resume.name_a, pair_resume.name_b],
                )
    except Exception:
        log.exception("pair_resume_load_failed", session_id=session.session_id)

    session = await svc.start_session(session)
    # Устанавливаем FSM-состояние для B (текущий пользователь)
    await state.set_state(SessionFlow.opening)
    # Устанавливаем FSM-состояние для A через storage напрямую
    try:
        storage_key_a = StorageKey(
            bot_id=bot.id,
            chat_id=session.user_a_id,
            user_id=session.user_a_id,
        )
        await state.storage.set_state(key=storage_key_a, state=SessionFlow.opening)
    except Exception:
        log.warning(
            "session_join_set_state_a_failed",
            session_id=session.session_id,
            user_id=session.user_a_id,
        )

    if session.resume_context:
        await reset_resume_choice_state(redis, session.session_id, (session.user_a_id, session.user_b_id))
        common_intro = _resume_confirmation_intro(session)
        reply_markup = resume_confirmation_keyboard()
    else:
        common_intro = _regular_setup_intro()
        reply_markup = None

    intro_message = format_bot_dialog_message(common_intro)
    m_a = await bot.send_message(session.user_a_id, intro_message, reply_markup=reply_markup)
    m_b = await bot.send_message(session.user_b_id, intro_message, reply_markup=reply_markup)
    session.first_msg_id_a = m_a.message_id
    session.first_msg_id_b = m_b.message_id
    await repo.save(session)
    log.info("session_started", session_id=session.session_id, user_a_id=session.user_a_id, user_b_id=session.user_b_id)


@router.callback_query(F.data.in_({"session:resume_continue", "session:resume_new_topic", "session:resume_not_accurate"}))
async def cb_resume_choice(
    callback: CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> None:
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(callback.from_user.id)
    if session is None:
        await callback.answer("Сессия не найдена.", show_alert=True)
        return

    choice = normalize_resume_choice(callback.data)
    if choice is None:
        await callback.answer("Не удалось распознать выбор.", show_alert=True)
        return

    existing_resolution = await get_resume_resolution(redis, session.session_id)
    if existing_resolution == RESUME_CHOICE_ALIGNMENT_PENDING:
        await callback.answer("Вы уже выбрали по-разному. Ответьте коротко текстом.", show_alert=True)
        return

    if existing_resolution in (RESUME_CHOICE_CONTINUE, RESUME_CHOICE_NEW_TOPIC):
        log.info(
            "resume_choice_resolution_already_exists",
            session_id=session.session_id,
            user_id=callback.from_user.id,
            choice=choice,
            resolution=existing_resolution,
        )
        await callback.answer("Выбор уже завершён. Продолжаем по нему.", show_alert=True)
        return

    status, resolution = await record_resume_vote(
        redis,
        session_id=session.session_id,
        user_id=callback.from_user.id,
        user_a_id=session.user_a_id,
        user_b_id=session.user_b_id,
        choice=choice,
    )

    if status == "resolved":
        await callback.answer("Выбор уже завершён. Продолжаем по нему.", show_alert=True)
        return

    svc = _make_service(bot, redis, session_factory)
    if status == "duplicate":
        log.info(
            "resume_choice_duplicate_ignored",
            session_id=session.session_id,
            user_id=callback.from_user.id,
            choice=choice,
            effective_choice=resolution,
        )
        await callback.answer("Твой выбор уже учтён. Ждём партнёра.", show_alert=True)
        return

    if status == "waiting":
        log.info(
            "resume_choice_recorded_waiting_partner",
            session_id=session.session_id,
            user_id=callback.from_user.id,
            choice=choice,
        )
        await _clear_single_resume_button(callback, session.session_id)
        await callback.answer("Твой выбор учтён. Ждём решение партнёра.")
        return

    if status == "matched" and resolution in (RESUME_CHOICE_CONTINUE, RESUME_CHOICE_NEW_TOPIC):
        followup = _apply_resume_resolution(session, resolution)
        await repo.save(session)
        log.info(
            "resume_choice_pair_matched",
            session_id=session.session_id,
            user_id=callback.from_user.id,
            resolution=resolution,
        )
        await _clear_resume_confirmation_buttons(session, bot)
        await svc.notify_both(session, followup)
        await callback.answer()
        return

    if status == "mismatch":
        log.info(
            "resume_choice_pair_mismatch",
            session_id=session.session_id,
            user_id=callback.from_user.id,
        )
        await _clear_resume_confirmation_buttons(session, bot)
        await repo.save(session)
        await svc.notify_both(session, _resume_alignment_intro())
        await callback.answer("Вы выбрали по-разному. Давайте коротко согласуем это текстом.")
        return

    await callback.answer("Не удалось обработать выбор.", show_alert=True)


@router.callback_query(F.data == "join:decline")
async def cb_join_decline(
    callback: CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(user_id)
    if session:
        # Уведомить партнёра A об отклонении
        try:
            await bot.send_message(
                session.user_a_id,
                "Партнёр отклонил приглашение. Сессия отменена.\n\n"
                "Создай новую сессию и отправь партнёру новый инвайт-код.",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            log.warning(
                "session_join_decline_notify_a_failed",
                session_id=session.session_id,
                user_id=session.user_a_id,
            )
        await repo.delete(session)
    await state.clear()
    await callback.message.answer(
        "Ты отклонил приглашение. Возвращайся когда будешь готов.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


# ─── Управление сессией ───────────────────────────────────────────────────────

@router.callback_query(F.data == "session:pass_turn")
async def cb_pass_turn(
    callback: CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    svc = _make_service(bot, redis, session_factory)
    session = await svc.get_user_session(user_id)

    if session is None:
        await callback.answer("Сессия не найдена.", show_alert=True)
        return
    if session.waiting_for == "BOTH":
        await callback.answer("Сейчас ждём ответа от обоих. Напишите оба — тогда продолжим.", show_alert=True)
        return
    if not session.is_active_speaker(user_id):
        await callback.answer("Сейчас не твоя очередь.", show_alert=True)
        return

    session = await svc.pass_turn(session)
    speaker_label = "A" if session.speaker_turn == "A" else "B"

    kb_a = session_control_keyboard(session.speaker_turn, session.is_active_speaker(session.user_a_id))
    kb_b = session_control_keyboard(session.speaker_turn, session.is_active_speaker(session.user_b_id))
    await bot.send_message(session.user_a_id, f"Слово передано партнёру {speaker_label}.", reply_markup=kb_a)
    await bot.send_message(session.user_b_id, f"Слово передано партнёру {speaker_label}.", reply_markup=kb_b)

    await callback.answer()



@router.message(Command("end_session"))
async def cmd_end_session(
    message: Message,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(message.from_user.id)
    if session is None:
        await message.answer("Активной сессии нет.")
        return

    await _present_end_session_choice(session=session, repo=repo, bot=bot)


@router.callback_query(F.data == "session:end")
async def cb_end_session(
    event: Message | CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    msg = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id
    svc = _make_service(bot, redis, session_factory)
    session = await svc.get_user_session(user_id)

    if session is None:
        await msg.answer("Активной сессии нет.")
        if isinstance(event, CallbackQuery):
            await event.answer()
        return

    await _clear_end_session_choice_buttons(session, bot)
    session.close_choice_active = False
    session.close_confirmation_pending = False
    session.close_continue_votes = ""
    session.close_choice_msg_id_a = 0
    session.close_choice_msg_id_b = 0
    elapsed = session.elapsed_minutes()
    await svc.end_session(session)
    await state.clear()

    repo = SessionRepository(redis, session_factory)

    insight_summary_text = ""
    # Генерируем итог ДО очистки истории — сохраняем в БД и мету на 24ч для post-session удаления
    try:
        insight = await _claude.generate_session_insight(session, repo)
        insight_summary_text = insight["summary_text"]
        await repo.save_session_insight(
            session_id=session.session_id,
            user_a_id=session.user_a_id,
            user_b_id=session.user_b_id,
            topic=insight["topic"],
            clarified_text=insight["clarified_text"],
            agreement_text=insight["agreement_text"],
            summary_text=insight["summary_text"],
        )
        summary_ttl = 60 * 60 * 24
        summary_meta = encode_summary_meta(
            session_id=session.session_id,
            user_a_id=session.user_a_id,
            user_b_id=session.user_b_id,
        )
        await redis.set(f"summary_meta:{session.user_a_id}", summary_meta, ex=summary_ttl)
        await redis.set(f"summary_meta:{session.user_b_id}", summary_meta, ex=summary_ttl)
    except Exception:
        log.warning("session_summary_save_failed", session_id=session.session_id)

    # Generate and save resume context for next session (P3.1)
    try:
        resume_ctx = await _claude.generate_resume_context(session, repo)
        if resume_ctx:
            await repo.save_pair_resume(session, resume_ctx)
            log.info("pair_resume_saved", session_id=session.session_id)
    except Exception:
        log.exception("pair_resume_save_failed", session_id=session.session_id)

    # Сохраняем first_msg_id для последующего удаления сообщений
    _ttl = 60 * 60 * 24
    if session.first_msg_id_a:
        await redis.set(f"first_msg:{session.user_a_id}", session.first_msg_id_a, ex=_ttl)
    if session.first_msg_id_b:
        await redis.set(f"first_msg:{session.user_b_id}", session.first_msg_id_b, ex=_ttl)

    # Ephemeral: удаляем историю диалога из Redis
    if session.ephemeral_mode:
        await _claude.clear_history(session.session_id, repo)
        await repo.delete(session)
        _release_lock(session.session_id)

    # Удаляем сообщение с кнопкой "Завершить сессию"
    if isinstance(event, CallbackQuery):
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.answer()

    survey_base_url = settings.post_session_survey_url.strip()
    for user_id, role in ((session.user_a_id, "A"), (session.user_b_id, "B")):
        if not user_id:
            continue
        survey_url = _build_post_session_survey_url(
            survey_base_url,
            session_id=session.session_id,
            role=role,
        )
        await bot.send_message(
            user_id,
            format_bot_dialog_message(
                _post_session_summary_text(
                    insight_summary_text or "Итог разговора сохранён.",
                    has_survey=bool(survey_url),
                )
            ),
            reply_markup=post_session_keyboard(bool(survey_url)),
        )
    log.info("session_ended", session_id=session.session_id, user_id=user_id, elapsed_minutes=elapsed)


@router.callback_query(F.data == "session:survey")
async def cb_post_session_survey(
    callback: CallbackQuery,
    redis: Redis,
) -> None:
    await _safe_answer_callback(callback)

    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            log.warning(
                "post_session_survey_markup_cleanup_failed",
                user_id=callback.from_user.id,
                message_id=getattr(callback.message, "message_id", 0),
            )

    survey_base_url = settings.post_session_survey_url.strip()
    summary_meta = decode_summary_meta(await redis.get(f"summary_meta:{callback.from_user.id}"))
    if not survey_base_url or summary_meta is None:
        await callback.answer("Ссылка на опрос недоступна.", show_alert=True)
        return

    role = "A" if int(summary_meta.get("user_a_id", 0)) == callback.from_user.id else "B"
    survey_url = _build_post_session_survey_url(
        survey_base_url,
        session_id=str(summary_meta.get("session_id", "")),
        role=role,
    )
    if not survey_url:
        await callback.answer("Ссылка на опрос недоступна.", show_alert=True)
        return

    try:
        await callback.answer(url=survey_url)
    except Exception:
        await callback.answer("Опрос готов. Открой его по ссылке, которую я сейчас отправлю.")
        if callback.message is not None:
            await callback.message.answer(
                f'Опрос готов: <a href="{html.escape(survey_url, quote=True)}">открыть анкету</a>'
            )


# ─── /status ─────────────────────────────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot, redis: Redis, session_factory: async_sessionmaker) -> None:
    svc = _make_service(bot, redis, session_factory)
    session = await svc.get_user_session(message.from_user.id)

    if session is None:
        await message.answer("Активной сессии нет.", reply_markup=main_menu_keyboard())
        return

    elapsed = session.elapsed_minutes()
    turn_label = "твоя" if session.is_active_speaker(message.from_user.id) else "партнёра"

    await message.answer(
        f"Статус сессии:\n\n"
        f"Фаза: {session.phase}\n"
        f"Время: {elapsed} мин\n"
        f"Очередь: {turn_label}\n"
        f"Режим: {session.mode}"
    )


# ─── После сессии ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "session:delete_now")
async def cb_delete_data(
    callback: CallbackQuery,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(user_id)

    first_msg_id = 0
    summary_meta = decode_summary_meta(await redis.get(f"summary_meta:{user_id}"))
    session_id_for_cleanup = None
    if session:
        first_msg_id = session.first_msg_id_a if user_id == session.user_a_id else session.first_msg_id_b
        session_id_for_cleanup = session.session_id
        await repo.delete(session)
        _release_lock(session.session_id)
    elif summary_meta is not None:
        session_id_for_cleanup = str(summary_meta.get("session_id", "")) or None

    # Если сессия уже удалена (ephemeral) — берём first_msg_id из отдельного ключа
    if not first_msg_id:
        raw = await redis.get(f"first_msg:{user_id}")
        if raw:
            try:
                first_msg_id = int(raw)
            except (ValueError, TypeError):
                first_msg_id = 0

    # Убираем служебные ключи
    if session_id_for_cleanup:
        await repo.delete_session_insight(session_id_for_cleanup)
    await redis.delete(f"first_msg:{user_id}")
    await redis.delete(f"summary_meta:{user_id}")

    await state.clear()
    await callback.answer()

    # Удаляем все сообщения диапазоном от первого сессионного до текущего
    last_msg_id = callback.message.message_id
    if first_msg_id:
        for msg_id in range(first_msg_id, last_msg_id + 1):
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass

    # Показываем приветственное сообщение
    name = html.escape(callback.from_user.first_name or "друг")
    await bot.send_message(
        chat_id,
        f"Привет, {name}!\n\n"
        "Я — PactaTalk, AI-фасилитатор диалога для пар.\n\n"
        "Я помогу вам провести структурированный разговор: "
        "сохраню очерёдность, прослежу за временем и помогу "
        "прийти к договорённости.\n\n"
        "Что хочешь сделать?",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "session:continue")
async def cb_continue_session(callback: CallbackQuery, bot: Bot, redis: Redis, session_factory: async_sessionmaker) -> None:
    repo = SessionRepository(redis, session_factory)
    session = await repo.get_by_user(callback.from_user.id)
    if session is None:
        await callback.answer("Активной сессии нет.", show_alert=True)
        return

    if not session.close_choice_active:
        if session.close_confirmation_pending:
            session.close_confirmation_pending = False
            await repo.save(session)
            await SessionService(repo, bot).notify_both(
                session,
                "Понял. Сессию не завершаю, продолжаем разговор.",
            )
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        return

    side = session.partner_name(callback.from_user.id)
    if side is None:
        await callback.answer("Эта кнопка недоступна.", show_alert=True)
        return

    votes = set(session.close_continue_votes)
    if side in votes:
        await callback.answer("Ваш выбор уже учтён.")
        return

    votes.add(side)
    session.close_continue_votes = "".join(sorted(votes))
    await repo.save(session)

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if votes == {"A", "B"}:
        await _clear_end_session_choice_buttons(session, bot)
        session.close_choice_active = False
        session.close_confirmation_pending = False
        session.close_continue_votes = ""
        session.close_choice_msg_id_a = 0
        session.close_choice_msg_id_b = 0
        await repo.save(session)
        await SessionService(repo, bot).notify_both(
            session,
            "Понял. Оба выбрали продолжить разговор, сессию не завершаю.",
        )
        await callback.answer()
        return

    await callback.message.answer(
        "Принял. Если второй партнёр тоже выберет <b>«Продолжить разговор»</b>, сессия продолжится.\n"
        "Если второй выберет <b>«Завершить сессию»</b>, разговор завершится."
    )
    await callback.answer()


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery, redis: Redis, session_factory: async_sessionmaker) -> None:
    await send_data_dashboard(
        callback.message,
        user_id=callback.from_user.id,
        redis=redis,
        session_factory=session_factory,
        reply_markup=data_actions_keyboard(),
    )
    await callback.answer()
