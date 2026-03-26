from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime
import structlog

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.repositories.session_repo import SessionRepository
from bot.repositories.user_repo import UserRepository
from bot.utils.keyboards import main_menu_keyboard

router = Router(name="privacy")
log = structlog.get_logger()


@dataclass
class DataBundle:
    user: object | None
    transactions: list[object]
    insights: list[object]
    pair_resumes: list[object]
    requests: list[object]


def privacy_policy_text() -> str:
    return (
        "Политика приватности PactaTalk:\n\n"
        "Во время и после сессии система может хранить:\n"
        "• данные аккаунта\n"
        "• итоги разговоров\n"
        "• сохранённый контекст пары для продолжения следующей сессии\n"
        "• обращения в поддержку и обратную связь\n\n"
        "Если захочешь удалить связанные данные, используй удаление данных в меню или команду /delete_data."
    )


def _format_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d.%m.%Y")


def _yes_no(value: bool) -> str:
    return "есть" if value else "нет"


async def _load_data_bundle(
    *,
    user_id: int,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> DataBundle:
    async with session_factory() as db:
        user_repo = UserRepository(db)
        user = await user_repo.get(user_id)
        txs = await user_repo.get_transactions(user_id)

    session_repo = SessionRepository(redis, session_factory)
    insights = await session_repo.list_session_insights_for_user(user_id, limit=None)
    pair_resumes = await session_repo.list_pair_resumes_for_user(user_id, limit=None)
    requests = await session_repo.list_user_requests_for_user(user_id, limit=None)
    return DataBundle(
        user=user,
        transactions=txs,
        insights=insights,
        pair_resumes=pair_resumes,
        requests=requests,
    )


async def send_data_dashboard(
    message: Message,
    *,
    user_id: int,
    redis: Redis,
    session_factory: async_sessionmaker,
    reply_markup=None,
) -> None:
    bundle = await _load_data_bundle(user_id=user_id, redis=redis, session_factory=session_factory)
    await message.answer(
        "Мои данные в PactaTalk\n\n"
        "Сейчас у нас сохранено:\n"
        f"• Итоги разговоров: {len(bundle.insights)}\n"
        f"• Контекст для продолжения: {_yes_no(bool(bundle.pair_resumes))}\n"
        f"• Обращения в поддержку и feedback: {len(bundle.requests)}\n"
        f"• Данные аккаунта: {_yes_no(bundle.user is not None)}",
        reply_markup=reply_markup,
    )


async def send_data_details(
    message: Message,
    *,
    user_id: int,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> None:
    bundle = await _load_data_bundle(user_id=user_id, redis=redis, session_factory=session_factory)
    user = bundle.user
    username = "—"
    first_name = "—"
    registered_at = "—"
    if user is not None:
        first_name = html.escape(getattr(user, "first_name", "") or "—")
        username_value = getattr(user, "username", None)
        username = f"@{html.escape(username_value)}" if username_value else "—"
        registered_at = _format_date(getattr(user, "created_at", None))

    last_insight_at = bundle.insights[0].created_at if bundle.insights else None
    last_resume_at = bundle.pair_resumes[0].updated_at if bundle.pair_resumes else None
    last_request_at = bundle.requests[0].created_at if bundle.requests else None

    await message.answer(
        "Что сейчас сохранено\n\n"
        "<b>Данные аккаунта</b>\n"
        f"• Есть: {_yes_no(user is not None)}\n"
        f"• Имя: {first_name}\n"
        f"• Username: {username}\n"
        f"• Зарегистрирован: {registered_at}\n"
        f"• Транзакций: {len(bundle.transactions)}\n\n"
        "<b>Итоги разговоров</b>\n"
        f"• Сохранено итогов: {len(bundle.insights)}\n"
        f"• Последний итог: {_format_date(last_insight_at)}\n\n"
        "<b>Контекст для продолжения</b>\n"
        f"• Сохранён: {_yes_no(bool(bundle.pair_resumes))}\n"
        f"• Последнее обновление: {_format_date(last_resume_at)}\n\n"
        "<b>Обращения</b>\n"
        f"• Сохранено: {len(bundle.requests)}\n"
        f"• Последнее обращение: {_format_date(last_request_at)}"
    )


async def send_delete_data_prompt(message: Message) -> None:
    await message.answer(
        "Удалить все твои данные из PactaTalk?\n\n"
        "Это действие необратимо: будут удалены данные аккаунта, история транзакций "
        "и связанные данные сессий, включая резюме и служебные артефакты.",
        reply_markup=_confirm_delete_keyboard(),
    )


async def send_export_data_file(
    message: Message,
    *,
    user_id: int,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> None:
    bundle = await _load_data_bundle(user_id=user_id, redis=redis, session_factory=session_factory)
    user = bundle.user

    data = {
        "user": None if user is None else {
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
            for tx in bundle.transactions
        ],
        "session_insights": [
            {
                "session_id": insight.session_id,
                "user_a_id": insight.user_a_id,
                "user_b_id": insight.user_b_id,
                "topic": insight.topic,
                "clarified_text": insight.clarified_text,
                "agreement_text": insight.agreement_text,
                "summary_text": insight.summary_text,
                "created_at": insight.created_at.isoformat(),
                "updated_at": insight.updated_at.isoformat(),
            }
            for insight in bundle.insights
        ],
        "pair_resumes": [
            {
                "pair_key": resume.pair_key,
                "session_id": resume.session_id,
                "name_a": resume.name_a,
                "name_b": resume.name_b,
                "resume_context": resume.resume_context,
                "dialogue_state": resume.dialogue_state,
                "created_at": resume.created_at.isoformat(),
                "updated_at": resume.updated_at.isoformat(),
            }
            for resume in bundle.pair_resumes
        ],
        "user_requests": [
            {
                "id": request.id,
                "kind": request.kind,
                "category": request.category,
                "message_text": request.message_text,
                "session_id": request.session_id,
                "created_at": request.created_at.isoformat(),
                "status": request.status,
                "admin_reply_text": request.admin_reply_text,
            }
            for request in bundle.requests
        ],
        "note": "Это экспорт данных аккаунта, итогов разговоров, контекста для продолжения и обращений в поддержку.",
    }

    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    file = BufferedInputFile(json_bytes, filename="pactatalk_my_data.json")
    await message.answer_document(file, caption="Твои данные из PactaTalk.")


@router.message(Command("my_data"))
async def cmd_my_data(message: Message, redis: Redis, session_factory: async_sessionmaker) -> None:
    await send_data_details(message, user_id=message.from_user.id, redis=redis, session_factory=session_factory)


@router.message(Command("delete_data"))
async def cmd_delete_data(message: Message) -> None:
    await send_delete_data_prompt(message)


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
async def cmd_export_data(message: Message, redis: Redis, session_factory: async_sessionmaker) -> None:
    await send_export_data_file(message, user_id=message.from_user.id, redis=redis, session_factory=session_factory)


def _confirm_delete_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить всё", callback_data="privacy:confirm_delete")],
        [InlineKeyboardButton(text="Отмена", callback_data="privacy:cancel_delete")],
    ])
