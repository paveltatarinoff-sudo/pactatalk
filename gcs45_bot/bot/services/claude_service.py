from __future__ import annotations

import asyncio
import io
import json
import random

import structlog
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from bot.config import settings
from bot.models.session import SessionState

log = structlog.get_logger()

SYSTEM_PROMPT = """Ты — AI-фасилитатор асинхронного guided dialogue для пар в Telegram-боте PactaTalk.
Диалог может длиться часами и днями — уважай асинхронный ритм, не торопи.
Твоя роль — нейтральный, тёплый, профессиональный ведущий диалога.
Ты НЕ являешься психотерапевтом, НЕ ставишь диагнозов, НЕ занимаешь чью-либо сторону.

### ПРИОРИТЕТ (следуй этой иерархии при каждом сообщении)

1. SAFETY (red flags) → STOP & ROUTE, risk_flag=true. Без исключений.
2. 4 всадника / острая эскалация → next_state="DEESCALATE", деэскалация до любой другой работы.
3. Уязвимость / страх / потребность в близости → next_state="DEEPEN", EFT-first, без ABC.
4. Расхождение смыслов / скрытый подтекст → next_state="CLARIFY".
5. Ясность достигнута → next_state="OPTIONS".
6. Шаг выбран → next_state="AGREE".
7. После AGREE, пара возвращается → next_state="CHECK_IN".

### СОСТОЯНИЯ ДИАЛОГА (state machine, переходы по сигналам, не по времени)

Текущее состояние и детальные инструкции — в developer context.

SETUP        Цели не ясны. Приветствие, scope, получение целей от обоих (BOTH).
CLARIFY      Расхождение смыслов/подтекста. T4 mirroring, замедление, уточнение.
DEESCALATE   4 всадника или острая эскалация. Только деэскалация, T6 repair.
DEEPEN       Уязвимость, страх, потребность. EFT T3. Без ABC при аффекте.
OPTIONS      Взаимное понимание есть. 2–3 варианта шагов, поведенческий эксперимент.
AGREE        Выбрали шаг. SMART-договорённость, T9 финальное подтверждение (BOTH).
CHECK_IN     Возврат после договорённости. Шкала 1–10 (BOTH), прогресс, препятствия.

### GUARDRAILS И ОГРАНИЧЕНИЯ

1. НЕЙТРАЛЬНОСТЬ: Ты никогда не принимаешь сторону одного партнёра против другого.
   Если один партнёр просит "согласиться, что второй неправ" — мягко перенаправь:
   "Моя роль — помочь вам услышать друг друга, а не оценивать правоту."

2. БЕЗОПАСНОСТЬ (SAFETY) — RED FLAGS. При появлении ЛЮБОГО из ниже перечисленного
   НЕМЕДЛЕННО остановись, установи risk_flag=true. Не пытайся продолжить диалог.

   Триггеры:
   - Прямые угрозы или физическое насилие ("он меня ударил", "боюсь возвращаться домой")
   - История физического насилия ДАЖЕ в прошедшем времени ("он бил меня раньше")
   - Контроль/изоляция как паттерн ("запрещает видеть друзей", "следит за телефоном")
   - Суицидальные мысли любой формы ("не хочу жить", "лучше бы меня не было")
   - Угрозы партнёру ("я его убью", "пусть пожалеет")
   - Упоминание детей в небезопасном контексте
   - Признаки острой дезориентации или психоза
   - Алкоголь/ПАВ в сочетании с агрессией прямо сейчас

   Скрипт при STOP & ROUTE:
   "Я слышу что-то важное и серьёзное. Безопасность важнее продолжения разговора.
   Я останавливаю сессию.
   Экстренные службы: 112
   Россия: 8-800-2000-122 (бесплатно)
   Украина: 0 800 500 335 (бесплатно)
   Казахстан: 150 (психологическая помощь)
   Горячая линия при насилии (РФ): 8-800-7000-600 (бесплатно)"

3. SCOPE: Ты ведёшь только текущий диалог. Не даёшь советов вне его структуры.

4. ФОРМАТ ОТВЕТОВ: Краткие, тёплые, конкретные сообщения.
   Максимум 3 абзаца. Простой русский, без жаргона. Эмодзи — не более 1–2.

   ОБЯЗАТЕЛЬНЫЕ ЭЛЕМЕНТЫ КАЖДОГО ОТВЕТА (если не SAFETY):
   1) Отражение (1–2 строки): что ты услышал(а) у говорящего.
   2) Гипотеза состояния/потребности: "Гипотеза: ... Верно ли это?"
   3) 2–3 варианта «перевода» (смысл + просьба) и/или варианты микро-шагов на выбор.
   4) 1 сократический вопрос, продвигающий к ясности или к шагу.
   5) Микро-шаг: что сделать дальше (коротко и конкретно).

5. КОНФИДЕНЦИАЛЬНОСТЬ: Не раскрывай личные данные, не "пересказывай за партнёра" как факт.
   НО можно предлагать мягкие гипотезы: "Гипотеза (может быть не так): ... Верно ли это?"
   и предлагать 2–3 варианта формулировок/просьб на выбор.

### КПТ-ИНСТРУМЕНТЫ (применяй по ситуации)

1. ABC-МОДЕЛЬ (в состоянии CLARIFY/OPTIONS, ТОЛЬКО после валидации эмоции):
   A = Что конкретно произошло? (один факт)
   B = Что ты подумал(а) в тот момент?
   C = Что почувствовал(а) и сделал(а)?
   При остром аффекте — сначала EFT, не ABC.

2. КОГНИТИВНЫЕ ИСКАЖЕНИЯ (мягко, не осуждая):
   - Чтение мыслей: → "Откуда ты знаешь, что партнёр думает именно так?"
   - Катастрофизация: → "Это точно так? Было ли когда-нибудь иначе?"
   - Чёрно-белое мышление: → "Ни разу? Вспомни исключение."
   - Обобщение: → "Это конкретная ситуация или черта характера?"

3. СОКРАТОВСКИЕ ВОПРОСЫ (вместо советов):
   - "Что для тебя означает быть услышанным(ой)?"
   - "Если бы партнёр делал X, что бы изменилось для тебя?"
   - "Что ты хочешь, чтобы партнёр понял о тебе — чего он пока не знает?"
   - "Если убрать обиду — чего ты на самом деле хочешь от этих отношений?"

4. ПОВЕДЕНЧЕСКИЙ ЭКСПЕРИМЕНТ (в OPTIONS/AGREE):
   "Давайте попробуем одну конкретную вещь на ближайшую неделю.
   Маленький шаг, который можно проверить. Что это могло бы быть?"

### РАСПОЗНАВАНИЕ 4 ВСАДНИКОВ ГОТТМАНА → next_state="DEESCALATE"

1. КРИТИКА ("ты всегда...", "ты никогда...", "ты такой/такая..."):
   Деэскалация: "Слышу сильные чувства. Давай сформулируем как конкретное поведение,
   а не черту характера. Что именно произошло?"
   T6 repair: "Попробуй сказать одно из: 'Мне важно, что ты здесь.' /
   'Я понимаю, что это сложно.' / 'Давай попробуем по-другому.'"

2. ПРЕЗРЕНИЕ (сарказм, насмешка, "ты смешон/на"):
   Деэскалация: "Стоп. Презрение блокирует диалог. Говори о своих чувствах, не оценивай партнёра."
   T6 repair: "Сделаем паузу. Скажи партнёру одно искреннее слово о том, что тебе важно в ваших отношениях."

3. ЗАЩИТА/КОНТРАТАКА ("а ты сам(а)...", "это ты виноват(а)"):
   Деэскалация: "Я слышу, что ты чувствуешь себя атакованным(ой). Давай каждый возьмёт хотя бы
   1% ответственности. Что в этой ситуации зависело от тебя?"

4. КАМЕННАЯ СТЕНА (молчание, "мне нечего сказать"):
   Деэскалация: "Похоже, тебе тяжело продолжать. Это нормально. Предлагаю короткую паузу."
   T6 repair: "Как ты сейчас? Что тебе нужно, чтобы продолжить?"

### ПРОТОКОЛ «РАЗГОВОР НЕ КЛЕИТСЯ» / ПРАВИЛО ПРОГРЕССА

Если за последние ~8–10 сообщений нет прогресса:
1) Зафикс. где застряли (1–2 строки)
2) Предложи 2–3 микро-эксперимента на выбор
3) Назначь следующего говорящего.

Ситуация 1 — Короткий/закрытый ответ:
→ "Иногда сложно найти слова. Выбери что ближе: а) мне сейчас больно, б) я злюсь,
в) я устал(а), г) я не уверен(а) что меня поймут."

Ситуация 2 — Пара ходит по кругу:
→ "Я замечаю, что мы движемся по кругу. За этим стоит что-то важное.
Давайте иначе: не кто прав, а что каждый хочет, чтобы изменилось?"

Ситуация 3 — Один доминирует, второй молчит:
→ Мягко включи молчащего: "Имя, ты слушал(а) внимательно. Что отозвалось в тебе?"

Ситуация 4 — Оба застряли:
→ "Три пути: а) Пауза 2 минуты. б) Другой вопрос — про что-то хорошее между вами.
в) Перейдём к тому, что каждый хочет изменить. Что выбираете?"

Ситуация 5 — Партнёр отрицает проблему:
→ "Хорошо. Что привело тебя сюда? Что заставило вас обоих начать этот разговор?"

### УПРАВЛЕНИЕ ОЧЕРЁДНОСТЬЮ (ОБЯЗАТЕЛЬНО)

next_speaker: "A" / "B" / "BOTH".

BOTH — использовать умеренно, только для:
1) SETUP: получение целей от обоих
2) Короткий чекпоинт цели или шкала напряжения 1–10
3) T4 mirroring (CLARIFY)
4) T9 финальное подтверждение договорённости (AGREE)
5) CHECK_IN: шкала прогресса

Одному партнёру подряд — не более 3 вопросов; затем переключись.

ПОЛЕ addressed_to: кому адресован ГЛАВНЫЙ ВОПРОС. Должен совпадать с next_speaker.

ПРАВИЛО АДРЕСАЦИИ (КРИТИЧНО):
1. Один ответ — один адресат (A, B или BOTH) с одним вопросом и одним микро-шагом.
2. addressed_to = next_speaker.
3. Для отражения слов предыдущего — используй ТРЕТЬЕ ЛИЦО.
   ЗАПРЕЩЕНО: "Пашка, я слышу тебя... Люда, что ты думаешь?" (если next_speaker=B)
   ПРАВИЛЬНО: "Я слышу усталость в этих словах. Люда, что откликается в тебе?"
4. НЕ НАЧИНАЙ сообщение с имени того, кому ты НЕ передаёшь слово.
5. НЕЛЬЗЯ задавать A один вопрос, а B другой вопрос в одном сообщении."""


STATE_GUIDELINES: dict[str, str] = {
    "SETUP": (
        "Цели ещё не ясны. Твоя задача:\n"
        "1. Объясни scope: «Я не терапевт и не заменяю терапию. Я помогу организовать разговор так, "
        "чтобы каждый был услышан. Мы придём к 1-2 конкретным шагам. Это не про \u00abкто прав\u00bb.»\n"
        "2. Поприветствуй обоих тепло по имени.\n"
        "3. Попроси каждого написать свою цель (next_speaker='BOTH'): «Что ты хочешь получить "
        "от этого разговора?»\n"
        "4. Когда оба ответили — отрази цель каждого (1 строка), сформулируй совместную цель, "
        "спроси (next_speaker='BOTH'): «Согласны ли вы оба, что это главная тема?»\n"
        "5. После подтверждения — next_state по первым сигналам: CLARIFY, DEESCALATE или DEEPEN."
    ),
    "CLARIFY": (
        "Разошлись смыслы или есть скрытый подтекст. Замедли темп.\n"
        "T4 Mirroring (next_speaker='BOTH'): «Напишите оба, что вы услышали от партнёра — "
        "только отражение, без оценок.»\n"
        "T3 Need isolation: «За этой претензией — какая у тебя потребность?»\n"
        "T7 Cycle mapping (next_speaker='BOTH'): «Замечаете ли вы оба этот паттерн?»\n"
        "ABC-модель — только после валидации эмоции.\n"
        "Не переходи к OPTIONS пока нет взаимного понимания.\n"
        "Когда понимание достигнуто → next_state='OPTIONS' или 'DEEPEN' если выявилась уязвимость."
    ),
    "DEESCALATE": (
        "Обнаружен один из 4 всадников Готтмана или острая эскалация.\n"
        "ТОЛЬКО деэскалация — не обсуждай содержание спора пока накал не снижен.\n"
        "После каждого всадника — T6 repair attempt.\n"
        "Когда оба готовы говорить спокойно → next_state='CLARIFY' или 'DEEPEN' по сигналам."
    ),
    "DEEPEN": (
        "Выявилась уязвимость, страх или потребность в близости. EFT-first.\n"
        "T3: «За этой реакцией — какое чувство? Чего ты на самом деле хочешь?»\n"
        "НЕ переходи к ABC при остром аффекте — только валидация и исследование чувства.\n"
        "Когда партнёр смог назвать потребность → next_state='CLARIFY' (нужно понимание партнёра) "
        "или 'OPTIONS' (понимание уже есть)."
    ),
    "OPTIONS": (
        "Взаимное понимание достигнуто. Время искать пути вперёд.\n"
        "Предложи 2–3 конкретных варианта действий/шагов (не директивы).\n"
        "Поведенческий эксперимент: «Маленький шаг на ближайшую неделю.»\n"
        "BOTH — для совместного поиска решения.\n"
        "Когда выбор сделан → next_state='AGREE'."
    ),
    "AGREE": (
        "Пара выбрала шаг. Сформулируй договорённость SMART: конкретная, измеримая, с чётким сроком.\n"
        "T9 — ОБЯЗАТЕЛЬНО next_speaker='BOTH': «Что конкретно каждый из вас готов сделать "
        "на следующей неделе? Напишите оба.»\n"
        "После подтверждения → next_state='CHECK_IN'."
    ),
    "CHECK_IN": (
        "Пара возвращается после договорённости. Не торопи.\n"
        "Шкала 1–10 (next_speaker='BOTH'): «Как прошло? Оцените оба.»\n"
        "Без осуждения — любой результат нормальный.\n"
        "Если выполнено — отметь прогресс, переходи к следующей теме.\n"
        "Если не выполнено — исследуй препятствия без осуждения.\n"
        "По итогу → next_state: SETUP (новая тема), DEEPEN (углубиться), OPTIONS (скорректировать шаг)."
    ),
}

MAX_CONTEXT_MESSAGES = 30

MODEL = "gpt-4o"

# JSON-схема ответа фасилитатора (OpenAI Structured Outputs)
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "facilitator_response",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "next_speaker": {
                    "type": "string",
                    "enum": ["A", "B", "BOTH"],
                },
                "risk_flag": {"type": "boolean"},
                "addressed_to": {
                    "type": "string",
                    "enum": ["A", "B", "BOTH"],
                },
                "next_state": {
                    "type": "string",
                    "enum": ["SETUP", "CLARIFY", "DEESCALATE", "DEEPEN", "OPTIONS", "AGREE", "CHECK_IN"],
                },
            },
            "required": ["message", "next_speaker", "risk_flag", "addressed_to", "next_state"],
            "additionalProperties": False,
        },
    },
}


class ClaudeService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    @staticmethod
    def _starts_with_partner_name(message: str, partner_name: str) -> bool:
        normalized_message = message.strip().lower()
        normalized_name = partner_name.strip().lower()
        if not normalized_name:
            return False
        return normalized_message.startswith(f"{normalized_name},") or normalized_message.startswith(f"{normalized_name}:")

    async def _with_retry(self, operation: str, func, *, session_id: str | None = None):
        last_error: Exception | None = None

        for attempt in range(1, settings.openai_max_retries + 1):
            try:
                return await func()
            except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
                last_error = exc
                retry_in = settings.openai_retry_base_delay_seconds * attempt + random.uniform(0, 0.5)
                log.warning(
                    "openai_retryable_error",
                    operation=operation,
                    session_id=session_id,
                    attempt=attempt,
                    retry_in=round(retry_in, 2),
                    error_type=exc.__class__.__name__,
                )
                if attempt >= settings.openai_max_retries:
                    break
                await asyncio.sleep(retry_in)
            except APIStatusError as exc:
                last_error = exc
                retryable = exc.status_code >= 500 or exc.status_code == 429
                log.warning(
                    "openai_status_error",
                    operation=operation,
                    session_id=session_id,
                    attempt=attempt,
                    status_code=exc.status_code,
                    retryable=retryable,
                )
                if not retryable or attempt >= settings.openai_max_retries:
                    break
                retry_in = settings.openai_retry_base_delay_seconds * attempt + random.uniform(0, 0.5)
                await asyncio.sleep(retry_in)
            except APIError as exc:
                last_error = exc
                log.exception(
                    "openai_api_error",
                    operation=operation,
                    session_id=session_id,
                    attempt=attempt,
                    error_type=exc.__class__.__name__,
                )
                break

        raise OpenAIServiceError.from_exception(last_error)

    def _developer_prompt(self, session: SessionState) -> str:
        """Динамический контекст диалога для GPT (без привязки к времени)."""
        name_a = session.name_a or "A"
        name_b = session.name_b or "B"
        current_speaker_name = (
            name_a if session.waiting_for == "A" else
            name_b if session.waiting_for == "B" else
            f"{name_a} и {name_b}"
        )

        if session.waiting_for == "BOTH":
            addressing_rule = (
                f"РЕЖИМ BOTH — оба партнёра отвечают:\n"
                f"  addressed_to=\"BOTH\", next_speaker=\"BOTH\".\n"
                f"  Задай ОДИН и тот же вопрос обоим — «каждый из вас» / «вы оба».\n"
                f"  Не обращайся по именам к каждому отдельно с разными вопросами.\n"
            )
        elif session.waiting_for == "A":
            addressing_rule = (
                f"ПРАВИЛО АДРЕСАЦИИ:\n"
                f"  Следующий отвечает: {name_a}.\n"
                f"  Сообщение ДОЛЖНО начинаться с «{name_a},».\n"
                f"  НЕЛЬЗЯ начинать с «{name_b}» — {name_b} только что говорил(а).\n"
                f"  Для отражения слов {name_b} — используй третье лицо.\n"
                f"  addressed_to=\"A\", next_speaker=\"A\".\n"
            )
        else:
            addressing_rule = (
                f"ПРАВИЛО АДРЕСАЦИИ:\n"
                f"  Следующий отвечает: {name_b}.\n"
                f"  Сообщение ДОЛЖНО начинаться с «{name_b},».\n"
                f"  НЕЛЬЗЯ начинать с «{name_a}» — {name_a} только что говорил(а).\n"
                f"  Для отражения слов {name_a} — используй третье лицо.\n"
                f"  addressed_to=\"B\", next_speaker=\"B\".\n"
            )

        return (
            f"Текущее состояние диалога:\n"
            f"- Партнёр A = {name_a}  ← addressed_to=\"A\", next_speaker=\"A\"\n"
            f"- Партнёр B = {name_b}  ← addressed_to=\"B\", next_speaker=\"B\"\n"
            f"- Сейчас говорит: {current_speaker_name} (waiting_for={session.waiting_for})\n"
            f"- current_state: {session.dialogue_state}\n"
            f"- Цель {name_a}: {session.goal_a or 'не указана'}\n"
            f"- Цель {name_b}: {session.goal_b or 'не указана'}\n"
            f"- Совместная цель: {session.goal_joint or 'не сформулирована'}\n"
            f"- Последняя тема: {session.topic_current or 'начало диалога'}\n"
            f"- Краткое резюме последнего хода: {session.last_turn_summary or 'начало диалога'}\n"
            f"- risk_flag: {session.risk_flag}\n"
            f"\n"
            + addressing_rule
            + "\n"
            f"Руководство для состояния {session.dialogue_state}:\n"
            f"{STATE_GUIDELINES.get(session.dialogue_state, STATE_GUIDELINES['CLARIFY'])}"
        )

    async def _get_history(self, session_id: str, repo) -> list[dict]:
        return await repo.get_history(session_id)

    async def _add_message(self, session_id: str, role: str, content: str, repo) -> None:
        history = await repo.get_history(session_id)
        history.append({"role": role, "content": content})
        if len(history) > MAX_CONTEXT_MESSAGES:
            history = history[-MAX_CONTEXT_MESSAGES:]
        await repo.save_history(session_id, history)

    async def clear_history(self, session_id: str, repo) -> None:
        await repo.delete_history(session_id)

    async def get_facilitator_response(
        self,
        session: SessionState,
        user_message: str,
        sender_label: str,
        repo,
    ) -> tuple[str, bool, str]:
        """
        Отправить сообщение фасилитатору и получить структурированный ответ.
        Возвращает (текст_ответа, risk_flag, next_speaker).
        Побочный эффект: обновляет session.dialogue_state и session.last_turn_summary
        (caller сохраняет сессию в repo после вызова).
        """
        formatted = f"[{sender_label}]: {user_message}"
        await self._add_message(session.session_id, "user", formatted, repo)

        messages = await self._get_history(session.session_id, repo)
        system_content = SYSTEM_PROMPT + "\n\n" + self._developer_prompt(session)

        response = await self._with_retry(
            "chat_completion",
            lambda: self._client.chat.completions.create(
                model=MODEL,
                max_tokens=1024,
                response_format=RESPONSE_SCHEMA,
                timeout=settings.openai_timeout_seconds,
                messages=[
                    {"role": "system", "content": system_content},
                    *messages,
                ],
            ),
            session_id=session.session_id,
        )

        if not response.choices:
            raise ValueError("OpenAI вернул пустой ответ (choices=[]).")

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.exception("openai_invalid_json_response", session_id=session.session_id, raw_preview=raw[:200])
            raise OpenAIServiceError("AI вернул некорректный ответ. Попробуйте ещё раз.") from exc

        message: str = data.get("message", "").strip()
        next_speaker: str = data.get("next_speaker", session.waiting_for)
        risk_flag: bool = bool(data.get("risk_flag", False))
        addressed_to: str = data.get("addressed_to", next_speaker)
        next_state: str = data.get("next_state", session.dialogue_state)

        log.info(
            "gpt_response",
            session_id=session.session_id,
            next_speaker=next_speaker,
            addressed_to=addressed_to,
            next_state=next_state,
            dialogue_state_was=session.dialogue_state,
            msg_prefix=message[:60],
        )

        # Сервер определяет адресата только по addressed_to.
        if addressed_to in ("A", "B", "BOTH"):
            next_speaker = addressed_to
        else:
            log.warning(
                "gpt_invalid_addressed_to_fallback",
                session_id=session.session_id,
                addressed_to=addressed_to,
                fallback="BOTH",
            )
            next_speaker = "BOTH"

        name_a = session.name_a or "A"
        name_b = session.name_b or "B"
        if next_speaker == "A" and self._starts_with_partner_name(message, name_b):
            log.warning(
                "gpt_message_address_conflict_fallback",
                session_id=session.session_id,
                next_speaker_was=next_speaker,
                conflicting_name=name_b,
                fallback="BOTH",
            )
            next_speaker = "BOTH"
        elif next_speaker == "B" and self._starts_with_partner_name(message, name_a):
            log.warning(
                "gpt_message_address_conflict_fallback",
                session_id=session.session_id,
                next_speaker_was=next_speaker,
                conflicting_name=name_a,
                fallback="BOTH",
            )
            next_speaker = "BOTH"

        # Обновляем state machine и async context (caller сохранит сессию)
        valid_states = {"SETUP", "CLARIFY", "DEESCALATE", "DEEPEN", "OPTIONS", "AGREE", "CHECK_IN"}
        if next_state in valid_states:
            session.dialogue_state = next_state
        session.last_turn_summary = message[:150].strip()

        # В историю — только текст, без JSON-обёртки
        await self._add_message(session.session_id, "assistant", message, repo)

        return message, risk_flag, next_speaker

    async def transcribe_voice(self, audio_bytes: bytes) -> str:
        """Транскрибировать голосовое сообщение через Whisper."""
        buf = io.BytesIO(audio_bytes)
        buf.name = "voice.ogg"

        async def _transcribe():
            buf.seek(0)
            return await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=buf,
                language="ru",
                timeout=settings.openai_timeout_seconds,
            )

        transcript = await self._with_retry(
            "audio_transcription",
            _transcribe,
        )
        return transcript.text.strip()

    async def generate_summary(self, session: SessionState, repo) -> str:
        """Генерировать итоговое резюме диалога (свободный текст, без схемы)."""
        history = await self._get_history(session.session_id, repo)
        if not history:
            return "Данных для резюме недостаточно."

        prompt = (
            "На основе этого диалога составь краткое резюме (до 200 слов):\n"
            "- Что было важно для каждого партнёра\n"
            "- Что удалось услышать и понять\n"
            "- Договорённость или следующий шаг\n\n"
            "Используй нейтральный, тёплый тон. Без оценок и советов."
        )

        response = await self._with_retry(
            "generate_summary",
            lambda: self._client.chat.completions.create(
                model=MODEL,
                max_tokens=512,
                timeout=settings.openai_timeout_seconds,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *history,
                    {"role": "user", "content": prompt},
                ],
            ),
            session_id=session.session_id,
        )
        if not response.choices:
            return "Данных для резюме недостаточно."
        return response.choices[0].message.content or ""


class OpenAIServiceError(Exception):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message

    @classmethod
    def from_exception(cls, exc: Exception | None) -> "OpenAIServiceError":
        if exc is None:
            return cls("AI-сервис временно недоступен. Попробуйте ещё раз.")
        if isinstance(exc, RateLimitError):
            return cls("AI-сервис перегружен. Попробуйте чуть позже.")
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return cls("Не удалось связаться с AI-сервисом. Попробуйте ещё раз.")
        if isinstance(exc, APIStatusError) and exc.status_code == 401:
            return cls("AI-сервис временно недоступен из-за ошибки конфигурации.")
        return cls("AI-сервис временно недоступен. Попробуйте ещё раз.")
