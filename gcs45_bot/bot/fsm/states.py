from aiogram.fsm.state import State, StatesGroup


class UserFlow(StatesGroup):
    """Состояния пользователя вне сессии."""
    joining = State()        # Вводит инвайт-код вручную
    feedback_category = State()
    feedback_message = State()
    support_category = State()
    support_message = State()


class AdminFlow(StatesGroup):
    replying_to_request = State()


class SessionFlow(StatesGroup):
    """Состояния активной сессии."""
    waiting_partner = State()   # Создал сессию, ждёт партнёра
    opening = State()           # Оба вошли, фаза 0–5 мин
