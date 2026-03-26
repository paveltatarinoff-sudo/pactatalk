from __future__ import annotations

import html
import re

from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import settings
from bot.fsm.states import AdminFlow
from bot.repositories.session_repo import SessionRepository
from bot.repositories.user_repo import UserRepository

router = Router(name="admin")
REPLY_PROMPT_RE = re.compile(r"по обращению\s+(\d+)", re.IGNORECASE)


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def _inbox_targets() -> list[int]:
    return settings.support_inbox_ids or settings.admin_ids


def _can_use_inbox(user_id: int, chat_id: int | None) -> bool:
    if is_admin(user_id):
        return True
    if chat_id is None:
        return False
    return chat_id in settings.support_inbox_ids


async def _deliver_admin_reply(
    *,
    message: Message,
    bot: Bot,
    repo: SessionRepository,
    state: FSMContext,
    request_id: int,
    target_user_id: int,
    reply_text: str,
) -> None:
    await bot.send_message(
        target_user_id,
        "<b>Сообщение от команды Pacta</b>\n\n" + html.escape(reply_text),
    )
    await repo.update_user_request_status(
        request_id,
        status="replied",
        admin_reply_text=reply_text,
    )
    await state.clear()
    await message.answer(
        f"Ответ по обращению <code>{request_id}</code> отправлен пользователю <code>{target_user_id}</code>."
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, session_factory: async_sessionmaker) -> None:
    if not is_admin(message.from_user.id):
        return  # Молча игнорируем

    async with session_factory() as db:
        repo = UserRepository(db)
        user_count = await repo.count_users()

    await message.answer(
        f"PactaTalk — Панель администратора\n\n"
        f"Пользователей: {user_count}\n"
        f"Inbox поддержки: {'настроен' if _inbox_targets() else 'не настроен'}\n"
        f"Inbox targets: {len(_inbox_targets())}\n"
        f"Admin IDs: {len(settings.admin_ids)}\n\n"
        f"Команды:\n"
        f"/admin — открыть эту панель\n"
        f"/chat_id — показать id текущего чата"
    )


@router.message(Command("chat_id"))
async def cmd_chat_id(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    chat = message.chat
    chat_title = getattr(chat, "title", "") or "—"
    await message.answer(
        "Текущий чат:\n"
        f"ID: <code>{chat.id}</code>\n"
        f"Тип: <code>{chat.type}</code>\n"
        f"Название: <code>{html.escape(chat_title)}</code>"
    )


@router.callback_query(F.data.startswith("inbox:reply:"))
async def cb_inbox_reply(
    callback: CallbackQuery,
    redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    chat_id = callback.message.chat.id if callback.message else None
    if not _can_use_inbox(callback.from_user.id, chat_id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    repo = SessionRepository(redis, session_factory)
    request_id = int(callback.data.rsplit(":", 1)[-1])
    request = await repo.get_user_request(request_id)
    if request is None:
        await callback.answer("Обращение не найдено.", show_alert=True)
        return

    await state.set_state(AdminFlow.replying_to_request)
    await state.update_data(
        request_id=request_id,
        target_user_id=request.telegram_id,
        inbox_chat_id=callback.message.chat.id if callback.message else 0,
    )
    await callback.message.answer(
        f"Чтобы ответить пользователю <code>{request.telegram_id}</code>, отправь в этот чат команду:\n\n"
        f"<code>/reply {request_id} Текст ответа</code>\n\n"
        f"Пользователь получит сообщение прямо в чате с PactaTalk Bot."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("inbox:close:"))
async def cb_inbox_close(
    callback: CallbackQuery,
    redis,
    session_factory: async_sessionmaker,
) -> None:
    chat_id = callback.message.chat.id if callback.message else None
    if not _can_use_inbox(callback.from_user.id, chat_id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    repo = SessionRepository(redis, session_factory)
    request_id = int(callback.data.rsplit(":", 1)[-1])
    await repo.update_user_request_status(request_id, status="closed")
    if callback.message:
        await callback.message.answer(f"Обращение <code>{request_id}</code> отмечено как закрытое.")
    await callback.answer()


@router.message(F.reply_to_message.text.regexp(REPLY_PROMPT_RE), F.text)
async def handle_admin_reply_to_prompt(
    message: Message,
    bot: Bot,
    redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    if not _can_use_inbox(message.from_user.id, message.chat.id):
        return

    prompt_text = message.reply_to_message.text or ""
    match = REPLY_PROMPT_RE.search(prompt_text)
    if match is None:
        return

    request_id = int(match.group(1))
    reply_text = (message.text or "").strip()
    if not reply_text:
        await message.answer("Нужен текстовый ответ.")
        return

    repo = SessionRepository(redis, session_factory)
    request = await repo.get_user_request(request_id)
    if request is None:
        await message.answer("Не удалось найти обращение. Попробуй снова из inbox.")
        return

    await _deliver_admin_reply(
        message=message,
        bot=bot,
        repo=repo,
        state=state,
        request_id=request_id,
        target_user_id=request.telegram_id,
        reply_text=reply_text,
    )


@router.message(Command("reply"))
async def cmd_reply(
    message: Message,
    bot: Bot,
    redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    if not _can_use_inbox(message.from_user.id, message.chat.id):
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Используй формат: <code>/reply request_id текст ответа</code>")
        return

    try:
        request_id = int(parts[1])
    except ValueError:
        await message.answer("Не удалось распознать request_id. Пример: <code>/reply 12 Спасибо, мы проверим это.</code>")
        return

    reply_text = parts[2].strip()
    if not reply_text:
        await message.answer("Нужен текстовый ответ.")
        return

    repo = SessionRepository(redis, session_factory)
    request = await repo.get_user_request(request_id)
    if request is None:
        await message.answer("Обращение не найдено.")
        return

    await _deliver_admin_reply(
        message=message,
        bot=bot,
        repo=repo,
        state=state,
        request_id=request_id,
        target_user_id=request.telegram_id,
        reply_text=reply_text,
    )


@router.message(AdminFlow.replying_to_request)
async def handle_admin_reply(
    message: Message,
    bot: Bot,
    redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    if not _can_use_inbox(message.from_user.id, message.chat.id):
        await state.clear()
        return

    data = await state.get_data()
    request_id = int(data.get("request_id", 0))
    target_user_id = int(data.get("target_user_id", 0))
    if not request_id or not target_user_id:
        await state.clear()
        await message.answer("Не удалось определить обращение для ответа. Начни заново из inbox.")
        return

    repo = SessionRepository(redis, session_factory)
    reply_text = (message.text or "").strip()
    if not reply_text:
        await message.answer("Нужен текстовый ответ.")
        return

    await _deliver_admin_reply(
        message=message,
        bot=bot,
        repo=repo,
        state=state,
        request_id=request_id,
        target_user_id=target_user_id,
        reply_text=reply_text,
    )
