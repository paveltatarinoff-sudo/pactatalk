from __future__ import annotations

from typing import Optional

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Message, CallbackQuery
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker
import structlog

from bot.fsm.states import UserFlow, SessionFlow
from bot.repositories.session_repo import SessionRepository
from bot.services.session_service import SessionService
from bot.services.shared import claude as _claude
from bot.handlers.facilitator import _release_lock
from bot.utils.keyboards import (
    session_control_keyboard,
    post_session_keyboard,
    join_confirm_keyboard,
    main_menu_keyboard,
    end_session_button,
)

router = Router(name="session")
log = structlog.get_logger()


def _make_service(bot: Bot, redis: Redis, session_factory: Optional[async_sessionmaker] = None) -> SessionService:
    return SessionService(SessionRepository(redis, session_factory), bot)


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
    user_id = event.from_user.id

    svc = _make_service(bot, redis, session_factory)

    # Атомарная блокировка — защита от гонки при двойном нажатии
    lock_key = f"lock:create_session:{user_id}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=5)
    if not acquired:
        if isinstance(event, CallbackQuery):
            await event.answer()
        return

    # Проверить нет ли уже активной сессии
    existing = await svc.get_user_session(user_id)
    if existing is not None:
        await redis.delete(lock_key)
        await msg.answer("У тебя уже есть активная сессия. Используй /status или /end_session.")
        if isinstance(event, CallbackQuery):
            await event.answer()
        return

    session = await svc.create_session(user_id)
    log.info("session_created", session_id=session.session_id, user_id=user_id)
    await redis.delete(lock_key)
    await state.set_state(SessionFlow.waiting_partner)
    await state.update_data(session_id=session.session_id)

    bot_info = await bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start=join_{session.invite_code}"
    inviter_name = event.from_user.first_name

    await msg.answer("Перешли следующее сообщение партнёру 👇")
    await msg.answer(
        f"💬 <b>{inviter_name} приглашает тебя на совместную сессию в PactaTalk</b>\n\n"
        f"PactaTalk — это пространство для честного и бережного разговора. "
        f"AI-фасилитатор поможет нам услышать друг друга, соблюсти очерёдность "
        f"и прийти к договорённости.\n\n"
        f"Нажми на ссылку чтобы присоединиться:\n"
        f"{invite_link}"
    )

    if isinstance(event, CallbackQuery):
        await event.answer()


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

    # Извлечь код из команды: /join XXXXXX
    code = None
    if isinstance(event, Message) and event.text:
        parts = event.text.strip().split()
        if len(parts) == 2:
            code = parts[1].upper()

    if not code:
        await state.set_state(UserFlow.joining)
        await msg.answer("Введи инвайт-код от партнёра:")
        if isinstance(event, CallbackQuery):
            await event.answer()
        return

    await _process_join(msg, user_id, code, bot, redis, session_factory, state)
    if isinstance(event, CallbackQuery):
        await event.answer()


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
    svc = _make_service(bot, redis, session_factory)

    existing = await svc.get_user_session(user_id)
    if existing is not None:
        await msg.answer("У тебя уже есть активная сессия. Используй /status или /end_session.")
        return

    # Атомарная блокировка invite-кода — защита от двойного join с одним кодом
    lock_key = f"lock:join:{code}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=10)
    if not acquired:
        await msg.answer("Этот код уже используется. Попробуй через несколько секунд.")
        return

    session = await svc.join_session(user_id, code)
    await redis.delete(lock_key)

    if session is None:
        await msg.answer(
            "Код не найден или уже использован.\n"
            "Проверь код и попробуй снова, или попроси партнёра создать новую сессию."
        )
        return
    log.info("session_joined", session_id=session.session_id, user_id=user_id)

    await state.set_state(SessionFlow.opening)
    await state.update_data(session_id=session.session_id)

    # BUG-011: безопасное получение имён
    try:
        chat_a = await bot.get_chat(session.user_a_id)
        partner_name = chat_a.first_name or chat_a.username or "Партнёр"
    except Exception:
        partner_name = "Партнёр"

    try:
        chat_b = await bot.get_chat(user_id)
        joiner_name = chat_b.first_name or chat_b.username or "Партнёр"
    except Exception:
        joiner_name = "Партнёр"

    # Уведомить B
    await msg.answer(
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
        pass


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
    svc = _make_service(bot, redis, session_factory)

    # Пробуем найти уже присоединённую сессию
    session = await svc.get_user_session(user_id)

    if session is None:
        # Партнёр пришёл по deep link — ещё не присоединился, делаем это сейчас
        code = callback.data.split(":")[-1]
        session = await svc.join_session(user_id, code)
        if session is None:
            await callback.answer("Сессия не найдена или код истёк.", show_alert=True)
            return

    # Сохраняем имена участников (BUG-011: защита от ошибок get_chat)
    try:
        chat_a = await bot.get_chat(session.user_a_id)
        session.name_a = chat_a.first_name or chat_a.username or "Партнёр A"
    except Exception:
        session.name_a = "Партнёр A"
    try:
        chat_b = await bot.get_chat(user_id)
        session.name_b = chat_b.first_name or chat_b.username or "Партнёр B"
    except Exception:
        session.name_b = "Партнёр B"

    repo = SessionRepository(redis, session_factory)

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
        pass  # некритично — facilitator работает без FSM-фильтра

    if session.resume_context:
        common_intro = (
            f"С возвращением! Я помню наш прошлый разговор.\n\n"
            f"Как это работает:\n"
            f"• Пишешь сообщение или голосовое 🎤 — фасилитатор отвечает вам обоим\n"
            f"• Говорит один, второй слушает — я слежу за очерёдностью\n"
            f"• Завершить сессию можно в любой момент кнопкой ниже\n\n"
            f"<b>👥 Первый вопрос — к каждому из вас.</b>\n\n"
            f"Напишите каждый: <b>хотите продолжить прошлую тему или начать новую?</b>\n"
            f"Отвечайте независимо — я жду ответа от вас обоих."
        )
    else:
        common_intro = (
            f"Давайте начнём. Я здесь, чтобы помочь вам услышать друг друга.\n\n"
            f"Как это работает:\n"
            f"• Пишешь сообщение или голосовое 🎤 — фасилитатор отвечает вам обоим\n"
            f"• Говорит один, второй слушает — я слежу за очерёдностью\n"
            f"• Завершить сессию можно в любой момент кнопкой ниже\n\n"
            f"<b>👥 Первый вопрос — к каждому из вас.</b>\n\n"
            f"Напишите каждый своё: <b>что ты хочешь получить от этого разговора?</b>\n"
            f"Отвечайте независимо — я жду ответа от вас обоих."
        )
    m_a = await bot.send_message(session.user_a_id, common_intro, reply_markup=end_session_button())
    m_b = await bot.send_message(session.user_b_id, common_intro, reply_markup=end_session_button())
    session.first_msg_id_a = m_a.message_id
    session.first_msg_id_b = m_b.message_id
    await repo.save(session)
    log.info("session_started", session_id=session.session_id, user_a_id=session.user_a_id, user_b_id=session.user_b_id)

    await callback.answer()


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
            pass
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



@router.callback_query(F.data == "session:end")
@router.message(Command("end_session"))
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

    elapsed = session.elapsed_minutes()
    await svc.end_session(session)
    await state.clear()

    repo = SessionRepository(redis, session_factory)

    # Генерируем резюме ДО очистки истории — сохраняем в Redis на 24ч
    try:
        summary_text = await _claude.generate_summary(session, repo)
        summary_ttl = 60 * 60 * 24
        await redis.set(f"summary:{session.user_a_id}", summary_text, ex=summary_ttl)
        await redis.set(f"summary:{session.user_b_id}", summary_text, ex=summary_ttl)
    except Exception:
        pass

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

    await svc.notify_both(
        session,
        f"Сессия завершена. Длительность: {elapsed} мин.\n\n"
        f"Что хотите сделать с доступными данными этой сессии — сохранить краткое резюме или удалить их сейчас?",
        reply_markup=post_session_keyboard(),
    )
    await svc.notify_both(
        session,
        "Готовы к новому разговору?",
        reply_markup=main_menu_keyboard(),
    )
    log.info("session_ended", session_id=session.session_id, user_id=user_id, elapsed_minutes=elapsed)


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
    if session:
        first_msg_id = session.first_msg_id_a if user_id == session.user_a_id else session.first_msg_id_b
        await repo.delete(session)
        _release_lock(session.session_id)

    # Если сессия уже удалена (ephemeral) — берём first_msg_id из отдельного ключа
    if not first_msg_id:
        raw = await redis.get(f"first_msg:{user_id}")
        if raw:
            try:
                first_msg_id = int(raw)
            except (ValueError, TypeError):
                first_msg_id = 0

    # Убираем служебные ключи
    await redis.delete(f"first_msg:{user_id}")
    await redis.delete(f"summary:{user_id}")

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
    name = callback.from_user.first_name or "друг"
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
async def cb_continue_session(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Управление данными:\n"
        "/my_data — посмотреть данные\n"
        "/delete_data — удалить все данные\n"
        "/export_data — экспортировать данные\n"
        "/privacy — политика приватности"
    )
    await callback.answer()


@router.callback_query(F.data == "session:save_summary")
async def cb_save_summary(callback: CallbackQuery, redis: Redis, session_factory: async_sessionmaker) -> None:
    user_id = callback.from_user.id
    raw = await redis.get(f"summary:{user_id}")

    if not raw:
        await callback.message.answer(
            "Резюме недоступно — возможно, сессия была слишком короткой или данные уже удалены."
        )
        await callback.answer()
        return

    summary = raw.decode() if isinstance(raw, bytes) else raw
    await callback.message.answer(f"📋 <b>Резюме сессии</b>\n\n{summary}")
    # Удаляем после отправки — данные одноразовые
    await redis.delete(f"summary:{user_id}")
    await callback.answer()
