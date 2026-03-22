from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать сессию", callback_data="session:new")],
        [InlineKeyboardButton(text="Присоединиться по коду", callback_data="session:join")],
    ])


def end_session_keyboard() -> InlineKeyboardMarkup:
    """Closing phase: с кнопкой «Продолжить»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Завершить сессию", callback_data="session:end")],
        [InlineKeyboardButton(text="Продолжить", callback_data="session:continue")],
    ])


def end_session_button() -> InlineKeyboardMarkup:
    """Тихая кнопка завершения — показывается в каждом сообщении бота."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Завершить сессию", callback_data="session:end")],
    ])


def session_control_keyboard(speaker_turn: str = "", user_is_speaker: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if user_is_speaker:
        rows.append([InlineKeyboardButton(text="➡️ Передать слово", callback_data="session:pass_turn")])
    rows.append([InlineKeyboardButton(text="⏹ Завершить сессию", callback_data="session:end")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def post_session_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сохранить резюме", callback_data="session:save_summary")],
        [InlineKeyboardButton(text="Удалить всё", callback_data="session:delete_now")],
        [InlineKeyboardButton(text="Настройки", callback_data="settings")],
    ])

def join_confirm_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Присоединиться", callback_data=f"join:confirm:{code}")],
        [InlineKeyboardButton(text="Отклонить", callback_data="join:decline")],
    ])


def resume_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="session:resume_continue")],
        [InlineKeyboardButton(text="Начать новую", callback_data="session:resume_new_topic")],
    ])
