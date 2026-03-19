from __future__ import annotations

import html
import json
import structlog

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.repositories.session_repo import SessionRepository
from bot.repositories.user_repo import UserRepository
from bot.utils.keyboards import main_menu_keyboard

router = Router(name="privacy")
log = structlog.get_logger()


@router.message(Command("my_data"))
async def cmd_my_data(message: Message, session_factory: async_sessionmaker) -> None:
    async with session_factory() as db:
        repo = UserRepository(db)
        user = await repo.get(message.from_user.id)
        txs = await repo.get_transactions(message.from_user.id)

    if user is None:
        await message.answer("Данных о тебе не найдено.")
        return

    tx_count = len(txs)
    first_name = html.escape(user.first_name or "—")
    username = html.escape(user.username or "—")
    await message.answer(
        f"Данные о тебе в PactaTalk:\n\n"
        f"Имя: {first_name}\n"
        f"Username: @{username}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Зарегистрирован: {user.created_at.strftime('%d.%m.%Y')}\n"
        f"Транзакций: {tx_count}\n\n"
        f"Здесь показаны только данные аккаунта и транзакций.\n"
        f"Данные сессий и связанные артефакты в этой команде сейчас не перечисляются отдельно.\n\n"
        f"Команды: /delete_data — удалить всё, /export_data — скачать JSON"
    )


@router.message(Command("delete_data"))
async def cmd_delete_data(message: Message) -> None:
    await message.answer(
        "Удалить все твои данные из PactaTalk?\n\n"
        "Это действие необратимо: будут удалены данные аккаунта, история транзакций "
        "и связанные данные сессий, включая резюме и служебные артефакты.",
        reply_markup=_confirm_delete_keyboard(),
    )


@router.callback_query(F.data == "privacy:confirm_delete")
async def cb_confirm_delete(
    callback: CallbackQuery,
    session_factory: async_sessionmaker,
    redis,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id

    repo = SessionRepository(redis, session_factory)
    log.info("privacy_wipe_started", user_id=user_id)

    try:
        wipe_summary = await repo.delete_all_user_session_data(user_id)

        # Удалить данные из PostgreSQL
        async with session_factory() as db:
            user_repo = UserRepository(db)
            await user_repo.delete_user_data(user_id)

        await state.clear()
        log.info("privacy_full_wipe_completed", user_id=user_id, **wipe_summary)
        await callback.message.answer(
            "Все твои данные удалены. До свидания!\n\n"
            "Если захочешь вернуться — просто напиши /start",
        )
    except Exception:
        log.error("privacy_wipe_failed", user_id=user_id, exc_info=True)
        await callback.message.answer(
            "При удалении данных произошла ошибка.\n"
            "Часть данных могла уже быть удалена.\n"
            "Попробуй выполнить команду ещё раз позже.",
        )
    finally:
        await callback.answer()


@router.callback_query(F.data == "privacy:cancel_delete")
async def cb_cancel_delete(callback: CallbackQuery) -> None:
    await callback.message.answer("Отменено. Данные сохранены.", reply_markup=main_menu_keyboard())
    await callback.answer()


@router.message(Command("export_data"))
async def cmd_export_data(message: Message, session_factory: async_sessionmaker) -> None:
    async with session_factory() as db:
        repo = UserRepository(db)
        user = await repo.get(message.from_user.id)
        txs = await repo.get_transactions(message.from_user.id)

    if user is None:
        await message.answer("Данных для экспорта нет.")
        return

    data = {
        "user": {
            "telegram_id": user.telegram_id,
            "first_name": user.first_name,
            "username": user.username,
            "created_at": user.created_at.isoformat(),
            "last_active_at": user.last_active_at.isoformat(),
        },
        "transactions": [
            {
                "payload": tx.payload,
                "amount_rub": tx.amount / 100,
                "credits": tx.credits_granted,
                "date": tx.created_at.isoformat(),
            }
            for tx in txs
        ],
        "note": "Это экспорт данных аккаунта и транзакций. Session-related данные и служебные артефакты сюда сейчас не входят.",
    }

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    file = BufferedInputFile(json_bytes, filename="pactatalk_my_data.json")
    await message.answer_document(file, caption="Твои данные из PactaTalk.")


def _confirm_delete_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить всё", callback_data="privacy:confirm_delete")],
        [InlineKeyboardButton(text="Отмена", callback_data="privacy:cancel_delete")],
    ])
