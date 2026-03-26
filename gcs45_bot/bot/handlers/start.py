from __future__ import annotations

import html

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.handlers.privacy import privacy_policy_text
from bot.repositories.user_repo import UserRepository
from bot.utils.keyboards import (
    main_menu_keyboard,
    onboarding_initiator_intro_keyboard,
    onboarding_initiator_step_three_keyboard,
    onboarding_initiator_step_two_keyboard,
    onboarding_partner_details_keyboard,
    onboarding_partner_intro_keyboard,
)

router = Router(name="start")

INITIATOR_ONBOARDING_INTRO = (
    "PactaTalk — это <b>AI-фасилитатор для пар</b>.\n\n"
    "Он помогает спокойно и структурированно обсуждать сложные темы: "
    "держит ход разговора, задаёт вопросы, помогает лучше понять друг друга "
    "и подводит итоги сессии.\n\n"
    "Если хочешь, я коротко покажу, как всё устроено."
)

INITIATOR_ONBOARDING_STEP_TWO = (
    "Как это работает:\n\n"
    "1. Ты создаёшь сессию.\n"
    "2. Пересылаешь приглашение партнёру.\n"
    "3. Партнёр присоединяется по ссылке.\n"
    "4. После этого я начинаю фасилитацию разговора: помогаю обозначить тему, "
    "удерживать фокус и двигаться шаг за шагом.\n\n"
    "В начале я обычно помогаю вам определить, с чего лучше начать разговор сегодня."
)

INITIATOR_ONBOARDING_STEP_THREE = (
    "Что именно делает бот\n\n"
    "Во время сессии я не просто слежу за очередностью.\n\n"
    "Я помогаю вам:\n"
    "• прояснять, что на самом деле стоит за словами и эмоциями;\n"
    "• объяснять сложные чувства простым и понятным языком;\n"
    "• замечать, где вы не слышите друг друга;\n"
    "• задавать как общие, так и личные вопросы;\n"
    "• переводить разговор из претензий в смысл, потребности и договорённости;\n"
    "• использовать сильные практики фасилитации и коммуникации, основанные на подходах EFT, Gottman, IBCT и CBT;\n"
    "• находить более удачные варианты продолжения разговора и решения вопроса.\n\n"
    "Вы можете отвечать текстом и голосом, задавать мне вопросы и поправлять меня, "
    "если я где-то неточен.\n\n"
    "Завершить сессию можно через меню Telegram или просто написав, "
    "что вы хотите завершить разговор. После этого я пришлю итоги сессии."
)

PARTNER_ONBOARDING_INTRO = (
    "Тебя пригласили в совместную сессию в PactaTalk.\n\n"
    "PactaTalk — это AI-фасилитатор для пар. Он помогает вести разговор "
    "более спокойно, понятно и структурированно, чтобы вам было легче услышать "
    "друг друга и прийти к ясности.\n\n"
    "Если хочешь, можешь присоединиться к сессии и продолжить разговор вместе с партнёром."
)

PARTNER_ONBOARDING_DETAILS = (
    "Что будет дальше:\n\n"
    "• я помогу вам начать разговор с темы, которая сейчас действительно важна;\n"
    "• буду задавать как общие, так и личные вопросы;\n"
    "• помогу лучше понять чувства, смысл и потребности друг друга;\n"
    "• смогу переформулировать сложные эмоции простым языком;\n"
    "• буду удерживать ход разговора и помогать не терять суть;\n"
    "• в конце пришлю итоги сессии.\n\n"
    "Во время разговора можно отвечать текстом и голосом, задавать мне вопросы "
    "и поправлять меня, если я где-то неточен."
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
        pass


async def _send_main_menu(message: Message, *, returning: bool = False, name: str | None = None) -> None:
    if returning:
        safe_name = html.escape(name or "друг")
        text = (
            f"С возвращением, {safe_name}.\n\n"
            "Можешь создать новую сессию, присоединиться к партнёру по коду "
            "или открыть гайд по работе с ботом."
        )
    else:
        text = (
            "Готово.\n\n"
            "Можешь создать новую сессию, присоединиться к партнёру по коду "
            "или открыть гайд по работе с ботом."
        )

    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    bot: Bot,
    session_factory: async_sessionmaker,
) -> None:
    user = message.from_user
    name = (user.first_name or user.username or "друг") if user else "друг"
    is_new_user = False

    # Регистрируем пользователя
    async with session_factory() as db:
        repo = UserRepository(db)
        existing = await repo.get(user.id)
        is_new_user = existing is None
        await repo.get_or_create(
            telegram_id=user.id,
            first_name=user.first_name,
            username=user.username,
        )

    # Deep link: /start join_XXXXXX — партнёр пришёл по ссылке
    args = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else ""
    if args.startswith("join_"):
        code = args[5:].upper()
        await message.answer(
            PARTNER_ONBOARDING_INTRO,
            reply_markup=onboarding_partner_intro_keyboard(code),
        )
        return

    if is_new_user:
        await message.answer(
            INITIATOR_ONBOARDING_INTRO,
            reply_markup=onboarding_initiator_intro_keyboard(),
        )
        return

    await _send_main_menu(message, returning=True, name=name)


@router.callback_query(F.data == "consent:accept")
async def cb_consent_accept(callback: CallbackQuery) -> None:
    await _delete_or_clear_callback_message(callback)
    await _send_main_menu(callback.message)
    await callback.answer()


@router.callback_query(F.data == "onboarding:init:intro")
async def cb_initiator_onboarding_intro(callback: CallbackQuery) -> None:
    await _delete_or_clear_callback_message(callback)
    await callback.message.answer(
        INITIATOR_ONBOARDING_INTRO,
        reply_markup=onboarding_initiator_intro_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding:init:step2")
async def cb_initiator_onboarding_step_two(callback: CallbackQuery) -> None:
    await _delete_or_clear_callback_message(callback)
    await callback.message.answer(
        INITIATOR_ONBOARDING_STEP_TWO,
        reply_markup=onboarding_initiator_step_two_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "onboarding:init:step3")
async def cb_initiator_onboarding_step_three(callback: CallbackQuery) -> None:
    await _delete_or_clear_callback_message(callback)
    await callback.message.answer(
        INITIATOR_ONBOARDING_STEP_THREE,
        reply_markup=onboarding_initiator_step_three_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboarding:partner:intro:"))
async def cb_partner_onboarding_intro(callback: CallbackQuery) -> None:
    code = callback.data.rsplit(":", 1)[-1].upper()
    await _delete_or_clear_callback_message(callback)
    await callback.message.answer(
        PARTNER_ONBOARDING_INTRO,
        reply_markup=onboarding_partner_intro_keyboard(code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("onboarding:partner:details:"))
async def cb_partner_onboarding_details(callback: CallbackQuery) -> None:
    code = callback.data.rsplit(":", 1)[-1].upper()
    await _delete_or_clear_callback_message(callback)
    await callback.message.answer(
        PARTNER_ONBOARDING_DETAILS,
        reply_markup=onboarding_partner_details_keyboard(code),
    )
    await callback.answer()


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(privacy_policy_text())
