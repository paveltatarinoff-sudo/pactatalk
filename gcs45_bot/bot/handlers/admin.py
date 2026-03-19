from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import settings
from bot.repositories.user_repo import UserRepository

router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message, session_factory: async_sessionmaker) -> None:
    if not is_admin(message.from_user.id):
        return  # Молча игнорируем

    async with session_factory() as db:
        repo = UserRepository(db)
        user_count = await repo.count_users()

    await message.answer(
        f"PactaTalk — Панель администратора\n\n"
        f"Пользователей: {user_count}\n\n"
        f"Команды:\n"
        f"/admin — открыть эту панель"
    )
