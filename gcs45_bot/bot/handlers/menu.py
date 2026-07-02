from __future__ import annotations

import html
import json

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import settings
from bot.fsm.states import UserFlow
from bot.handlers.privacy import (
    privacy_policy_text,
    send_data_dashboard,
    send_data_details,
    send_delete_data_prompt,
    send_export_data_file,
)
from bot.repositories.session_repo import SessionRepository
from bot.utils.keyboards import (
    data_actions_keyboard,
    feedback_category_keyboard,
    help_guide_keyboard,
    inbox_request_keyboard,
    main_menu_keyboard,
    progress_delete_all_prompt_keyboard,
    progress_delete_prompt_keyboard,
    support_category_keyboard,
)

router = Router(name="menu")
log = structlog.get_logger()

FEEDBACK_CATEGORY_LABELS = {
    "positive": "Что было полезно",
    "friction": "Что было неудобно",
    "bug": "Нашёл баг",
}

SUPPORT_CATEGORY_LABELS = {
    "tech": "Техническая проблема",
    "billing": "Проблема с оплатой",
    "data": "Вопрос о данных",
    "human": "Связаться с человеком",
}


async def _clear_callback_markup(callback: CallbackQuery) -> None:
    try:
        await callback.message.delete()
        return
    except Exception:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


def _format_insight_date(value) -> str:
    return value.strftime("%d.%m.%Y")


def _inbox_targets() -> list[int]:
    return settings.support_inbox_ids or settings.admin_ids


def _help_text() -> str:
    return (
        "PactaTalk — AI-фасилитатор для пар.\n\n"
        "🧭 Что делает бот:\n"
        "PactaTalk помогает вам вести разговор более спокойно, ясно и структурированно. "
        "Он удерживает ход разговора, задаёт вопросы, помогает распутывать напряжённые моменты, "
        "объяснять сложные чувства простым языком и двигаться к пониманию и договорённостям.\n\n"
        "💬 Как начинается сессия:\n"
        "Один из вас создаёт сессию и пересылает приглашение партнёру. "
        "Партнёр присоединяется по ссылке, после чего бот начинает общую сессию.\n\n"
        "🗣️ Как проходит разговор:\n"
        "В начале бот помогает определить тему разговора. Дальше он задаёт как общие, "
        "так и личные вопросы, помогает точнее сформулировать мысли, чувства и потребности, "
        "замечает, где вы начинаете терять друг друга, и предлагает более удачные ходы разговора.\n\n"
        "🤖 Что можно делать во время сессии:\n"
        "Вы можете отвечать текстом и голосом, задавать боту вопросы, "
        "уточнять смысл его ответов и поправлять его, если он где-то неточен.\n\n"
        "🧠 Что умеет бот:\n"
        "Он помогает прояснять эмоции и смысл сказанного, переводить разговор из претензий "
        "в более глубокое понимание, опирается на сильные подходы фасилитации и коммуникации "
        "и предлагает варианты движения разговора и решения вопроса.\n\n"
        "🚪 Как завершить сессию:\n"
        "Завершить сессию можно в любой момент через меню Telegram или просто написав, "
        "что вы хотите завершить разговор.\n\n"
        "🙂 Что происходит после завершения:\n"
        "После сессии бот присылает итоги разговора. Следующую сессию можно начать "
        "как продолжение предыдущей темы или как новый разговор.\n\n"
        "☰ Что еще есть в меню:\n"
        "В меню можно посмотреть управление данными, обратиться в поддержку и оставить фидбэк."
    )


def _progress_card(insight) -> str:
    return (
        f"<b>{_format_insight_date(insight.created_at)}</b>\n"
        f"<b>Тема:</b> {html.escape(insight.topic)}\n"
        f"<b>Что прояснили:</b> {html.escape(insight.clarified_text)}\n"
        f"<b>О чём договорились:</b> {html.escape(insight.agreement_text)}"
    )


def _progress_actions_keyboard(insights) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Удалить итог {_format_insight_date(insight.created_at)}",
                callback_data=f"progress:prompt_delete:{insight.session_id}",
            )
        ]
        for insight in insights
    ]
    rows.append([InlineKeyboardButton(text="Удалить все итоги", callback_data="progress:prompt_delete_all")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _notify_inbox(bot: Bot, text: str, *, reply_markup=None) -> bool:
    delivered = False
    targets = _inbox_targets()
    if not targets:
        log.warning("support_inbox_not_configured")
        return False
    for target_id in targets:
        try:
            await bot.send_message(target_id, text, reply_markup=reply_markup)
            delivered = True
        except Exception:
            log.warning("inbox_notification_failed", target_id=target_id)
    return delivered


async def _store_and_forward_request(
    *,
    message: Message,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
    kind: str,
) -> None:
    data = await state.get_data()
    category = data.get("request_category", "general")
    repo = SessionRepository(redis=redis, session_factory=session_factory)
    session = await repo.get_by_user(message.from_user.id)
    session_id = session.session_id if session is not None else None

    request_id = await repo.create_user_request(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name or "",
        kind=kind,
        category=category,
        message_text=message.text or "",
        session_id=session_id,
    )

    username = f"@{message.from_user.username}" if message.from_user.username else "—"
    request_label = "Обратная связь" if kind == "feedback" else "Поддержка"
    admin_text = (
        f"<b>{request_label}</b>\n"
        f"Категория: {html.escape(category)}\n"
        f"Имя: {html.escape(message.from_user.first_name or '—')}\n"
        f"Username: {html.escape(username)}\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Request ID: <code>{request_id or '—'}</code>\n"
        f"Активная сессия: {'да' if session_id else 'нет'}\n"
        f"Session ID: <code>{html.escape(session_id or '—')}</code>\n\n"
        f"{html.escape(message.text or '')}"
    )
    delivered = await _notify_inbox(
        bot,
        admin_text,
        reply_markup=inbox_request_keyboard(int(request_id)) if request_id is not None else None,
    )
    await state.clear()
    if delivered:
        await message.answer("Спасибо, я передал это команде.")
        return

    log.warning(
        "user_request_saved_without_admin_delivery",
        kind=kind,
        user_id=message.from_user.id,
        session_id=session_id,
    )
    await message.answer(
        "Спасибо, сообщение сохранено, но канал поддержки пока не настроен.\n"
        "Когда он будет подключён, команда увидит новые обращения."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(_help_text(), reply_markup=help_guide_keyboard())


@router.callback_query(F.data == "menu:help_guide")
async def cb_help_guide(callback: CallbackQuery) -> None:
    await _clear_callback_markup(callback)
    await callback.message.answer(_help_text(), reply_markup=help_guide_keyboard())
    await callback.answer()


@router.message(Command("data"))
async def cmd_data(message: Message, redis: Redis, session_factory: async_sessionmaker) -> None:
    await send_data_dashboard(
        message,
        user_id=message.from_user.id,
        redis=redis,
        session_factory=session_factory,
        reply_markup=data_actions_keyboard(),
    )


@router.callback_query(F.data == "help:my_data")
async def cb_help_my_data(callback: CallbackQuery, redis: Redis, session_factory: async_sessionmaker) -> None:
    await send_data_details(
        callback.message,
        user_id=callback.from_user.id,
        redis=redis,
        session_factory=session_factory,
    )
    await callback.answer()


@router.callback_query(F.data == "help:delete_data")
async def cb_help_delete_data(callback: CallbackQuery) -> None:
    await send_delete_data_prompt(callback.message)
    await callback.answer()


@router.callback_query(F.data == "help:privacy")
async def cb_help_privacy(callback: CallbackQuery) -> None:
    await callback.message.answer(privacy_policy_text())
    await callback.answer()


@router.callback_query(F.data.in_({"data:details", "data:my_data"}))
async def cb_data_my_data(callback: CallbackQuery, redis: Redis, session_factory: async_sessionmaker) -> None:
    await _clear_callback_markup(callback)
    await send_data_details(
        callback.message,
        user_id=callback.from_user.id,
        redis=redis,
        session_factory=session_factory,
    )
    await callback.answer()


@router.callback_query(F.data == "data:export")
async def cb_data_export(callback: CallbackQuery, redis: Redis, session_factory: async_sessionmaker) -> None:
    await _clear_callback_markup(callback)
    await send_export_data_file(
        callback.message,
        user_id=callback.from_user.id,
        redis=redis,
        session_factory=session_factory,
    )
    await callback.answer()


@router.callback_query(F.data == "data:delete")
async def cb_data_delete(callback: CallbackQuery) -> None:
    await _clear_callback_markup(callback)
    await send_delete_data_prompt(callback.message)
    await callback.answer()


@router.callback_query(F.data == "data:privacy")
async def cb_data_privacy(callback: CallbackQuery) -> None:
    await _clear_callback_markup(callback)
    await callback.message.answer(privacy_policy_text())
    await callback.answer()


@router.message(Command("feedback"))
async def cmd_feedback(message: Message, state: FSMContext) -> None:
    await state.set_state(UserFlow.feedback_category)
    await state.update_data(request_kind="feedback")
    await message.answer(
        "Что хочешь передать команде?",
        reply_markup=feedback_category_keyboard(),
    )


@router.callback_query(F.data.startswith("feedback:category:"))
async def cb_feedback_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.rsplit(":", 1)[-1]
    label = FEEDBACK_CATEGORY_LABELS.get(category, "Другое")
    await state.set_state(UserFlow.feedback_message)
    await state.update_data(request_kind="feedback", request_category=label)
    await _clear_callback_markup(callback)
    await callback.message.answer(
        f"Выбрано: <b>{html.escape(label)}</b>.\n\n"
        "Напиши одним сообщением, что именно хочешь передать."
    )
    await callback.answer()


@router.message(UserFlow.feedback_category)
async def feedback_category_guard(message: Message) -> None:
    await message.answer("Сначала выбери категорию ниже.")


@router.message(UserFlow.feedback_message)
async def handle_feedback_message(
    message: Message,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    await _store_and_forward_request(
        message=message,
        bot=bot,
        redis=redis,
        session_factory=session_factory,
        state=state,
        kind="feedback",
    )


@router.message(Command("support"))
async def cmd_support(message: Message, state: FSMContext) -> None:
    await state.set_state(UserFlow.support_category)
    await state.update_data(request_kind="support")
    await message.answer(
        "С чем нужна помощь?",
        reply_markup=support_category_keyboard(),
    )


@router.callback_query(F.data.startswith("support:category:"))
async def cb_support_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.rsplit(":", 1)[-1]
    label = SUPPORT_CATEGORY_LABELS.get(category, "Другое")
    await state.set_state(UserFlow.support_message)
    await state.update_data(request_kind="support", request_category=label)
    await _clear_callback_markup(callback)
    await callback.message.answer(
        f"Выбрано: <b>{html.escape(label)}</b>.\n\n"
        "Напиши коротко, с чем нужна помощь."
    )
    await callback.answer()


@router.message(UserFlow.support_category)
async def support_category_guard(message: Message) -> None:
    await message.answer("Сначала выбери категорию ниже.")


@router.message(UserFlow.support_message)
async def handle_support_message(
    message: Message,
    bot: Bot,
    redis: Redis,
    session_factory: async_sessionmaker,
    state: FSMContext,
) -> None:
    await _store_and_forward_request(
        message=message,
        bot=bot,
        redis=redis,
        session_factory=session_factory,
        state=state,
        kind="support",
    )


@router.message(Command("progress"))
async def cmd_progress(
    message: Message,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> None:
    repo = SessionRepository(redis=redis, session_factory=session_factory)
    insights = await repo.list_session_insights_for_user(message.from_user.id, limit=5)

    if not insights:
        await message.answer(
            "У вас пока нет сохранённых итогов разговоров.\n\n"
            "После завершения разговора новый итог автоматически появится здесь."
        )
        return

    blocks = []
    for insight in insights:
        blocks.append(_progress_card(insight))

    await message.answer(
        "Вот короткие итоги ваших последних разговоров.\n\n" + "\n\n".join(blocks),
        reply_markup=_progress_actions_keyboard(insights),
    )


@router.callback_query(F.data.startswith("progress:prompt_delete:"))
async def cb_progress_prompt_delete(
    callback: CallbackQuery,
) -> None:
    session_id = callback.data.rsplit(":", 1)[-1]
    await _clear_callback_markup(callback)
    await callback.message.answer(
        "Удалить этот итог?\n\nЭто удалит его из раздела «Мои итоги» для обоих участников.",
        reply_markup=progress_delete_prompt_keyboard(session_id),
    )
    await callback.answer()


@router.callback_query(F.data == "progress:prompt_delete_all")
async def cb_progress_prompt_delete_all(callback: CallbackQuery) -> None:
    await _clear_callback_markup(callback)
    await callback.message.answer(
        "Удалить все сохранённые итоги?\n\nЭто действие необратимо.",
        reply_markup=progress_delete_all_prompt_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("progress:delete:"))
async def cb_progress_delete(
    callback: CallbackQuery,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> None:
    session_id = callback.data.rsplit(":", 1)[-1]
    repo = SessionRepository(redis=redis, session_factory=session_factory)
    await repo.delete_session_insight(session_id)
    await _clear_callback_markup(callback)
    await callback.message.answer("Итог удалён. Чтобы увидеть обновлённый список, откройте «Мои итоги» ещё раз.")
    await callback.answer()


@router.callback_query(F.data == "progress:delete_all")
async def cb_progress_delete_all(
    callback: CallbackQuery,
    redis: Redis,
    session_factory: async_sessionmaker,
) -> None:
    repo = SessionRepository(redis=redis, session_factory=session_factory)
    await repo.delete_session_insights_for_user(callback.from_user.id)
    await _clear_callback_markup(callback)
    await callback.message.answer("Все сохранённые итоги удалены.")
    await callback.answer()


@router.callback_query(F.data == "progress:cancel_delete")
async def cb_progress_cancel_delete(callback: CallbackQuery) -> None:
    await _clear_callback_markup(callback)
    await callback.message.answer("Удаление отменено.")
    await callback.answer()


@router.callback_query(F.data == "menu:cancel")
async def cb_menu_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _clear_callback_markup(callback)
    await callback.message.answer("Отменено.")
    await callback.answer()


def encode_summary_meta(*, session_id: str, user_a_id: int, user_b_id: int) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "user_a_id": user_a_id,
            "user_b_id": user_b_id,
        }
    )


def decode_summary_meta(raw: str | bytes | None) -> dict[str, int | str] | None:
    if raw is None:
        return None
    value = raw.decode() if isinstance(raw, bytes) else raw
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload
