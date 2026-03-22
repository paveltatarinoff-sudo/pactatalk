from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User, Transaction


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, telegram_id: int, first_name: str, username: Optional[str] = None) -> User:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=telegram_id,
                first_name=first_name,
                username=username,
            )
            self._session.add(user)
            await self._session.commit()
            await self._session.refresh(user)
        else:
            user.last_active_at = datetime.utcnow()
            await self._session.commit()
        return user

    async def get(self, telegram_id: int) -> Optional[User]:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_transactions(self, telegram_id: int) -> list[Transaction]:
        result = await self._session.execute(
            select(Transaction).where(Transaction.telegram_id == telegram_id)
        )
        return list(result.scalars().all())

    async def delete_user_data(self, telegram_id: int) -> None:
        """Удалить все данные пользователя (GDPR)."""
        await self._session.execute(
            delete(Transaction).where(Transaction.telegram_id == telegram_id)
        )
        await self._session.execute(
            delete(User).where(User.telegram_id == telegram_id)
        )
        await self._session.commit()

    async def count_users(self) -> int:
        result = await self._session.execute(select(User))
        return len(result.scalars().all())
