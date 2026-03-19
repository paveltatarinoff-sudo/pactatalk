import html

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.repositories.user_repo import UserRepository
from bot.utils.keyboards import main_menu_keyboard, join_confirm_keyboard

router = Router(name="start")

DISCLAIMER_TEXT = (
    "Прежде чем начать\n\n"
    "PactaTalk — инструмент для <b>структурированного диалога</b>, основанный "
    "на адаптированных принципах коммуникации (EFT, Gottman, IBCT, CBT).\n\n"
    "Это <b>НЕ является</b>:\n"
    "— психотерапией или медицинской услугой\n"
    "— заменой работы с лицензированным специалистом\n"
    "— диагностикой психологических расстройств\n\n"
    "Для кого <b>НЕ подходит</b>:\n"
    "— ситуации с физическим насилием или угрозами\n"
    "— острые кризисы, требующие немедленной помощи\n"
    "— если кто-то думает о причинении вреда себе или другим\n\n"
    "В экстренных случаях: <b>112</b> | 8-800-2000-122 (РФ) | 0 800 500 335 (UA)"
)


def disclaimer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Понятно, продолжить →", callback_data="consent:accept")],
    ])


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    bot: Bot,
    session_factory: async_sessionmaker,
) -> None:
    user = message.from_user
    name = html.escape((user.first_name or user.username or "друг") if user else "друг")

    # Регистрируем пользователя
    async with session_factory() as db:
        repo = UserRepository(db)
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
            "Тебя пригласили на сессию PactaTalk!\n\n"
            "<i>PactaTalk — инструмент для структурированного диалога. "
            "Это не терапия. Продолжая, ты соглашаешься с этими ограничениями.</i>\n\n"
            "Нажми кнопку чтобы присоединиться:",
            reply_markup=join_confirm_keyboard(code),
        )
        return

    # Показываем дисклеймер перед главным меню
    await message.answer(
        f"Привет, {name}! Я — PactaTalk, AI-фасилитатор диалога для пар.\n\n"
        + DISCLAIMER_TEXT,
        reply_markup=disclaimer_keyboard(),
    )


@router.callback_query(F.data == "consent:accept")
async def cb_consent_accept(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Отлично! Я помогу вам провести структурированный разговор: "
        "сохраню очерёдность, прослежу за временем и помогу "
        "прийти к договорённости.\n\n"
        "Что хочешь сделать?",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды бота:\n\n"
        "/new_session — создать сессию (получишь инвайт-код для партнёра)\n"
        "/join CODE — присоединиться к сессии по коду\n"
        "/status — статус текущей сессии\n"
        "/end_session — завершить сессию досрочно\n"
        "/my_data — посмотреть свои данные\n"
        "/delete_data — удалить все данные\n"
        "/privacy — политика приватности\n"
        "/help — эта справка",
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    await message.answer(
        "Политика приватности PactaTalk:\n\n"
        "Во время и после сессии система хранит данные, связанные с диалогом: "
        "текущую сессию, историю для работы бота, служебный transcript и краткий контекст "
        "для продолжения следующей сессии.\n\n"
        "Итоговое резюме для участников хранится отдельно и доступно ограниченное время.\n\n"
        "Если захочешь удалить связанные данные, используй /delete_data.\n\n"
        "Команды: /my_data, /delete_data, /export_data"
    )
