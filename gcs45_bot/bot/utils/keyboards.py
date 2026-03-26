from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from typing import Optional


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать сессию", callback_data="session:new")],
        [InlineKeyboardButton(text="Присоединиться по коду", callback_data="session:join")],
        [InlineKeyboardButton(text="Как это работает", callback_data="menu:help_guide")],
    ])


def help_guide_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать сессию", callback_data="session:new")],
        [InlineKeyboardButton(text="Присоединиться по коду", callback_data="session:join")],
    ])


def end_session_keyboard() -> InlineKeyboardMarkup:
    """Closing phase: с кнопкой «Продолжить»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Завершить сессию", callback_data="session:end")],
        [InlineKeyboardButton(text="Продолжить разговор", callback_data="session:continue")],
    ])


def end_session_button() -> InlineKeyboardMarkup:
    """Тихая кнопка завершения — показывается в каждом сообщении бота."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏹ Завершить сессию", callback_data="session:end")],
    ])


def session_control_keyboard(speaker_turn: str = "", user_is_speaker: bool = False) -> Optional[InlineKeyboardMarkup]:
    rows = []
    if user_is_speaker:
        rows.append([InlineKeyboardButton(text="➡️ Передать слово", callback_data="session:pass_turn")])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def post_session_keyboard(survey_enabled: bool = False) -> Optional[InlineKeyboardMarkup]:
    if not survey_enabled:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ответить на короткий опрос", callback_data="session:survey")],
    ])

def join_confirm_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Присоединиться", callback_data=f"join:confirm:{code}")],
        [InlineKeyboardButton(text="Отклонить", callback_data="join:decline")],
    ])


def onboarding_initiator_intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Как это работает", callback_data="onboarding:init:step2")],
        [InlineKeyboardButton(text="Сразу начать", callback_data="session:new")],
    ])


def onboarding_initiator_step_two_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Дальше", callback_data="onboarding:init:step3")],
        [InlineKeyboardButton(text="Назад", callback_data="onboarding:init:intro")],
        [InlineKeyboardButton(text="Сразу создать сессию", callback_data="session:new")],
    ])


def onboarding_initiator_step_three_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать сессию", callback_data="session:new")],
        [InlineKeyboardButton(text="Открыть полный гайд", callback_data="menu:help_guide")],
        [InlineKeyboardButton(text="Назад", callback_data="onboarding:init:step2")],
    ])


def onboarding_partner_intro_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Присоединиться", callback_data=f"join:confirm:{code}")],
        [InlineKeyboardButton(text="Как это работает", callback_data=f"onboarding:partner:details:{code}")],
    ])


def onboarding_partner_details_keyboard(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Присоединиться к сессии", callback_data=f"join:confirm:{code}")],
        [InlineKeyboardButton(text="Назад", callback_data=f"onboarding:partner:intro:{code}")],
    ])


def resume_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Продолжить", callback_data="session:resume_continue")],
        [InlineKeyboardButton(text="Начать новую", callback_data="session:resume_new_topic")],
    ])


def feedback_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Что было полезно", callback_data="feedback:category:positive")],
        [InlineKeyboardButton(text="Что было неудобно", callback_data="feedback:category:friction")],
        [InlineKeyboardButton(text="Нашёл баг", callback_data="feedback:category:bug")],
        [InlineKeyboardButton(text="Отмена", callback_data="menu:cancel")],
    ])


def support_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Техническая проблема", callback_data="support:category:tech")],
        [InlineKeyboardButton(text="Проблема с оплатой", callback_data="support:category:billing")],
        [InlineKeyboardButton(text="Вопрос о данных", callback_data="support:category:data")],
        [InlineKeyboardButton(text="Связаться с человеком", callback_data="support:category:human")],
        [InlineKeyboardButton(text="Отмена", callback_data="menu:cancel")],
    ])


def help_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои данные", callback_data="help:my_data")],
        [InlineKeyboardButton(text="Удалить данные", callback_data="help:delete_data")],
        [InlineKeyboardButton(text="Политика приватности", callback_data="help:privacy")],
    ])


def data_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Посмотреть, что сохранено", callback_data="data:details")],
        [InlineKeyboardButton(text="Экспортировать данные", callback_data="data:export")],
        [InlineKeyboardButton(text="Удалить все данные", callback_data="data:delete")],
        [InlineKeyboardButton(text="Политика приватности", callback_data="data:privacy")],
    ])


def progress_delete_prompt_keyboard(session_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить этот итог", callback_data=f"progress:delete:{session_id}")],
        [InlineKeyboardButton(text="Отмена", callback_data="progress:cancel_delete")],
    ])


def progress_delete_all_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить все итоги", callback_data="progress:delete_all")],
        [InlineKeyboardButton(text="Отмена", callback_data="progress:cancel_delete")],
    ])


def inbox_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ответить", callback_data=f"inbox:reply:{request_id}")],
        [InlineKeyboardButton(text="Закрыть обращение", callback_data=f"inbox:close:{request_id}")],
    ])
