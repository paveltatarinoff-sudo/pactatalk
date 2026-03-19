from aiogram.fsm.state import State, StatesGroup


class UserFlow(StatesGroup):
    """Состояния пользователя вне сессии."""
    joining = State()        # Вводит инвайт-код вручную


class SessionFlow(StatesGroup):
    """Состояния активной сессии."""
    waiting_partner = State()   # Создал сессию, ждёт партнёра
    opening = State()           # Оба вошли, фаза 0–5 мин
