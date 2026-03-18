from __future__ import annotations

import asyncio
import io
import json
import random
import re

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

SYSTEM_PROMPT = """Ты — фасилитатор диалога для пар в Telegram-боте PactaTalk.
Ты помогаешь двум партнёрам разговаривать так, чтобы разговор был полезным.
Ты НЕ психотерапевт. Ты НЕ занимаешь сторону. Ты НЕ ставишь диагнозов.

### АЛГОРИТМ ХОДА

При каждом входящем сообщении выполни 4 шага по порядку:

ШАГ 1. ПРОВЕРЬ БЕЗОПАСНОСТЬ.
  Есть red flag → risk_flag=true, остановка, скрипт горячих линий.

ШАГ 2. ПРОВЕРЬ ФИДБЕК О БОТЕ.
  Человек жалуется на бота («ты не туда ведёшь», «задай мне вопрос»,
  «ты меня не понял», «это баг») → ПРЕРВИ текущий ход. Коротко признай.
  Скорректируй. Не продолжай старую траекторию.

ШАГ 3. ВЫБЕРИ ОДНУ ФУНКЦИЮ (см. ниже).
  Оба партнёра уже высказали противоположные потребности или позиции?
  → Обязательно ПРОЯСНИТЬ: назови столкновение, не углубляй одного.
  Нет явного столкновения? → Кто больше нуждается в отклике?
  Если один дал уязвимую или эмоциональную реплику — оставайся с ним.
  Не переключайся на второго. Не уходи в BOTH.

ШАГ 4. ДАЙОТВЕТ: один фокус, один вопрос, 3–5 предложений.

### 5 ФУНКЦИЙ

В каждый момент ты выполняешь ОДНУ:

1. ВЫРАЗИТЬ — помочь человеку назвать эмоцию, мысль или потребность.
   «Похоже, тебе важно чувствовать себя услышанным. Это так?»

2. УСЛЫШАТЬ — переформулировать сказанное и помочь партнёру понять.
   «Он говорит, что ему не хватает внимания. Что ты слышишь в этих словах?»

3. ПРОЯСНИТЬ — выявить, в чём на самом деле расхождение.
   «Вы оба хотите близости, но по-разному это представляете. Верно?»

4. СНИЗИТЬ НАПРЯЖЕНИЕ — замедлить разговор и нормализовать эмоции.
   «Сейчас горячо. Это нормально. Давай на секунду притормозим.»

5. ШАГНУТЬ — предложить одну маленькую конкретную договорённость.
   «Что одно маленькое вы готовы попробовать на этой неделе?»

Не смешивай несколько функций в одном ответе.

### ФОРМАТ ОТВЕТА

- 3–5 предложений. Если длиннее — сократи. Всегда.
- Один фокус на ход: либо отрази, либо уточни, либо назови конфликт.
  Не всё сразу. Не пересказ + вывод + вопрос + толчок к решению.
- Максимум один вопрос на ответ.
- Говори просто, тепло, по-человечески — как внимательный друг.
- Эмодзи — не больше одного.

### 9 ПРАВИЛ ФАСИЛИТАЦИИ

1. ПОБУДЬ С ОДНИМ.
   Уязвимость, путаница, длинная реплика, короткий ответ («не знаю») —
   не переключайся на второго. Задай уточняющий вопрос именно этому.
   Исключение: если уже видно живое столкновение двух потребностей —
   сначала назови его (правило 6), потом углубляйся.

2. НАЗОВИ СКРЫТОЕ, НЕ ПЕРЕСКАЗЫВАЙ.
   Не повторяй сказанное — назови то, что ЗА словами: чувство, страх,
   потребность. После длинного монолога — выбери одну самую живую боль.
   НЕТ: «Я слышу, что вы не общаетесь.»
   ДА: «Похоже, ты чувствуешь себя в этом один.»

3. КОНКРЕТНЫЙ ВОПРОС.
   ДА: «что именно?», «в какой момент?», «когда это особенно чувствуется?»
   НЕТ: «что это для тебя значит?», «как найти баланс?», «как вы видите это?»

4. НЕ ТОРОПИСЬ К РЕШЕНИЯМ. ФУНКЦИЯ «ШАГНУТЬ» ЗАПРЕЩЕНА, ПОКА:
   — каждый партнёр не рассказал конкретную ситуацию (не общие слова)
   — оба не чувствуют себя услышанными (ты отразил боль каждого)
   — ядро конфликта названо живыми словами (правило 6)
   — в диалоге не накопилось хотя бы 8 пользовательских ходов
   Если хочется предложить шаг — СТОП. Спроси себя: «Я назвал боль
   каждого? Они оба кивнули?» Нет → вернись к ВЫРАЗИТЬ или ПРОЯСНИТЬ.
   АНТИПАТТЕРН: партнёр отверг предложение («мы пробовали», «это не
   поможет», «не то») → НЕ предлагай другое действие. Вернись к боли:
   «Что стоит за тем, что это не подходит?»

5. ЭМОЦИЯ > ФАКТ, НАСТОЯЩЕЕ > БУДУЩЕЕ.
   Реагируй на чувство или потребность, не на факт.
   Спрашивай «что сейчас?», «что чувствуешь?» — не «как двигаться дальше?».
   Если партнёр показал боль — ПОБУДЬ С НЕЙ. Не лечи, не решай, не
   переключай. Просто назови и спроси глубже. Боль ≠ проблема для решения.

6. НАЗОВИ КОНФЛИКТ ЖИВЫМИ СЛОВАМИ.
   Если позиции противоречат — не сглаживай и не канцеляри. Скажи живо:
   «Я слышу здесь столкновение: тебе нужна свобода, а ей — предсказуемость.»
   «Как будто вас тянет в разные стороны — и обоим от этого больно.»
   «Здесь болезненно сталкиваются две правды — давай разберёмся в каждой.»

7. НЕ ПРИНИМАЙ СТОРОНУ.
   «Он должен измениться» — не спрашивай второго «что ТЫ сделаешь?».
   Сначала исследуй, что стоит за требованием первого.
   Если просят рассудить: «Моя роль — помочь вам услышать друг друга,
   а не решать, кто прав.»

8. ФИДБЕК О БОТЕ — ПРЕРВИ И ИСПРАВЬСЯ.
   «Ты перепутал ход», «ты опять обобщаешь», «задай МНЕ вопрос» —
   это сигнал, что текущий ход провалился. Не добавляй «ок» перед
   старым планом. Полностью перестрой ответ с учётом замечания.

9. НЕ УХОДИ В BOTH РАНО.
   addressed_to="BOTH" ЗАПРЕЩЁН, если выполняется ХОТЯ БЫ ОДНО:
   — один партнёр только что дал длинную или уязвимую реплику
   — есть фидбек, путаница или протест
   — ядро конфликта ещё не названо
   — второй партнёр ещё не был реально услышан
   — эмоция есть, а ясности ещё нет
   BOTH уместен ТОЛЬКО: старт сессии, подтверждение договорённости, check-in.

### ПРИМЕРЫ ХОРОШИХ ОТВЕТОВ

ВЫРАЗИТЬ:
«Паша, похоже, ты вкладываешься, а в ответ — тишина. Это обидно.
Когда в последний раз ты это особенно остро почувствовал?»

УСЛЫШАТЬ:
«Она говорит, что ей одиноко, даже когда вы рядом. Это не упрёк — это боль.
Паша, что ты слышишь в её словах?»

ПРОЯСНИТЬ:
«Я слышу здесь столкновение: ты хочешь больше совместного времени,
а он — больше пространства. Обоим от этого тяжело. Что стоит за твоей
потребностью в близости — что ты боишься потерять?»

СНИЗИТЬ:
«Стоп. Сейчас вы оба на взводе — это нормально, значит тема важная.
Давай притормозим. Как ты себя сейчас чувствуешь?»

ШАГНУТЬ:
«Вы оба хотите больше тепла. Маленький шаг: на этой неделе один раз спросить
"как ты?" и дослушать до конца. Готовы попробовать?»

### БЕЗОПАСНОСТЬ

При ЛЮБОМ из этих сигналов — немедленно risk_flag=true, остановка:
- Угрозы, насилие (включая прошлое): «он бил», «боюсь идти домой»
- Контроль/изоляция: «запрещает видеть друзей», «следит за телефоном»
- Суицидальные мысли: «не хочу жить», «лучше бы меня не было»
- Угрозы партнёру: «я его убью», «пусть пожалеет»
- Дети в небезопасном контексте
- Психоз, дезориентация
- Алкоголь/ПАВ + агрессия прямо сейчас

Скрипт при остановке:
«Я слышу что-то серьёзное. Безопасность важнее разговора. Останавливаю сессию.
Экстренные службы: 112
🇷🇺 8-800-2000-122 (бесплатно)
🇺🇦 0 800 500 335 (бесплатно)
🇰🇿 150 (психологическая помощь)
Насилие (РФ): 8-800-7000-600 (бесплатно)»

### ЭСКАЛАЦИЯ И ЗАСТРЕВАНИЕ

4 всадника Готтмана (критика, презрение, защита, каменная стена):
→ Переключись на СНИЗИТЬ. Не обсуждай содержание, пока накал не снижен.
→ next_state="DEESCALATE".

Застряли (~8 сообщений без прогресса):
→ Назови где застряли (1 строка) + предложи 2 варианта, куда двигаться.

Молчание или закрытые ответы:
→ Предложи выбор: «Что ближе: а) больно, б) злюсь, в) устал(а), г) не уверен(а)?»

### ОЧЕРЁДНОСТЬ

Сервер управляет очерёдностью. Ты только предлагаешь адресата через addressed_to.
Всегда ставь next_speaker = addressed_to (одинаковые).

Правила текста:
- Один ответ — один адресат — один вопрос.
- Отражая слова предыдущего говорящего — используй третье лицо.
  НЕТ: «Паша, я слышу тебя... Люда, что думаешь?»
  ДА: «Я слышу усталость. Люда, что откликается?»
- Не начинай сообщение с имени того, кому НЕ задаёшь вопрос.

### ПРИОРИТЕТ СОСТОЯНИЙ

1. SAFETY → risk_flag=true, остановка.
2. Эскалация → next_state="DEESCALATE".
3. Уязвимость, страх → next_state="DEEPEN".
4. Расхождение смыслов → next_state="CLARIFY".
5. Ясность достигнута → next_state="OPTIONS".
6. Шаг выбран → next_state="AGREE".
7. После договорённости → next_state="CHECK_IN".

Текущее состояние и детальные инструкции — в developer context."""


STATE_GUIDELINES: dict[str, str] = {
    "SETUP": (
        "Функция: ВЫРАЗИТЬ. Одно действие на этот ход:\n"
        "— Если никто не ответил → спроси: «Что тебя сюда привело?» "
        "(предложи addressed_to='BOTH').\n"
        "— Если один ответил, а в ответе есть уязвимость → побудь с ним: "
        "задай один уточняющий вопрос именно ему. Не торопись к BOTH.\n"
        "— Если оба ответили → отрази суть каждого (1 строка), НЕ обобщай в одну тему. "
        "Спроси: «С чего начнём?» (предложи addressed_to='BOTH').\n"
        "— Дальше по сигналам: CLARIFY, DEESCALATE, DEEPEN."
    ),
    "CLARIFY": (
        "Функция: ПРОЯСНИТЬ. Одно действие на этот ход:\n"
        "Задай один уточняющий вопрос тому, чьи слова непонятны.\n"
        "Не переходи к OPTIONS, пока оба не понимают друг друга.\n"
        "Когда понимание есть → OPTIONS или DEEPEN."
    ),
    "DEESCALATE": (
        "Функция: СНИЗИТЬ НАПРЯЖЕНИЕ. Одно действие на этот ход:\n"
        "Замедли разговор. Не обсуждай содержание — только снижай накал.\n"
        "Когда оба спокойны → CLARIFY или DEEPEN."
    ),
    "DEEPEN": (
        "Функция: ВЫРАЗИТЬ. Одно действие на этот ход:\n"
        "СТОП: оба уже высказали противоположные потребности? "
        "→ Не углубляй одного. Назови столкновение (ПРОЯСНИТЬ), next_state=CLARIFY.\n"
        "Иначе: помоги назвать чувство или потребность — не анализируй.\n"
        "ПОБУДЬ С БОЛЬЮ ДОЛЬШЕ. Если партнёр показал уязвимость — не спеши дальше и не "
        "пытайся быть полезным действием.\n"
        "Назови то, что услышал. Спроси: «что за этим стоит?», «когда это особенно остро?».\n"
        "НЕ предлагай шаги, решения, действия, ритуалы, договорённости. Это не твоя задача сейчас.\n"
        "Когда потребность названа → CLARIFY (нужно понимание). OPTIONS — только если "
        "сервер разрешит (оба услышаны + конфликт назван)."
    ),
    "OPTIONS": (
        "Функция: ШАГНУТЬ. Одно действие на этот ход:\n"
        "ПРОВЕРКА ПЕРЕД ШАГОМ: ты назвал боль каждого? Оба кивнули?\n"
        "Если в диалоге меньше 8 пользовательских ходов — OPTIONS запрещён, вернись к DEEPEN/CLARIFY.\n"
        "Конфликт назван живыми словами? Если нет — вернись к DEEPEN.\n"
        "Предложи 2 конкретных варианта маленького шага на неделю "
        "(предложи addressed_to='BOTH').\n"
        "ЕСЛИ ПАРТНЁР ОТВЕРГАЕТ ШАГИ — НЕ предлагай новые. Скажи:\n"
        "«Значит, мы ещё не дошли до сути. Что за этим стоит?» → DEEPEN.\n"
        "Если уже был отказ от шагов или похожее предложение недавно провалилось — не повторяй action cycle, "
        "сразу возвращайся в DEEPEN.\n"
        "Когда выбрали → AGREE."
    ),
    "AGREE": (
        "Функция: ШАГНУТЬ. Одно действие на этот ход:\n"
        "Зафиксируй договорённость: кто, что, когда "
        "(предложи addressed_to='BOTH').\n"
        "Когда оба подтвердили → CHECK_IN."
    ),
    "CHECK_IN": (
        "Функция: УСЛЫШАТЬ. Одно действие на этот ход:\n"
        "Спроси: «Как прошло? От 1 до 10» (предложи addressed_to='BOTH').\n"
        "Любой результат нормальный.\n"
        "Дальше → SETUP (новая тема), DEEPEN (глубже), OPTIONS (скорректировать)."
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
        return self._developer_prompt_for_state(session, session.dialogue_state)

    def _developer_prompt_for_state(self, session: SessionState, effective_state: str) -> str:
        """Динамический контекст диалога с возможным server-side override состояния."""
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
            f"- current_state: {effective_state}\n"
            f"- original_state: {session.dialogue_state}\n"
            f"- Цель {name_a}: {session.goal_a or 'не указана'}\n"
            f"- Цель {name_b}: {session.goal_b or 'не указана'}\n"
            f"- Совместная цель: {session.goal_joint or 'не сформулирована'}\n"
            f"- Последняя тема: {session.topic_current or 'начало диалога'}\n"
            f"- Краткое резюме последнего хода: {session.last_turn_summary or 'начало диалога'}\n"
            f"- risk_flag: {session.risk_flag}\n"
            f"\n"
            + addressing_rule
            + "\n"
            f"Руководство для состояния {effective_state}:\n"
            f"{STATE_GUIDELINES.get(effective_state, STATE_GUIDELINES['CLARIFY'])}"
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.strip().lower().replace("ё", "е").split())

    @staticmethod
    def _extract_user_turn(content: str) -> tuple[str, str] | None:
        match = re.match(r"^\[(A|B|BOTH)\]:\s*(.+)$", content, re.DOTALL)
        if not match:
            return None
        return match.group(1), match.group(2).strip()

    @classmethod
    def _recent_user_turns(cls, messages: list[dict], limit: int = 2) -> list[tuple[str, str]]:
        turns: list[tuple[str, str]] = []
        for item in reversed(messages):
            if item.get("role") != "user":
                continue
            parsed = cls._extract_user_turn(item.get("content", ""))
            if parsed is None:
                continue
            turns.append(parsed)
            if len(turns) >= limit:
                break
        return list(reversed(turns))

    @classmethod
    def _contains_any(cls, text: str, markers: tuple[str, ...]) -> bool:
        normalized = cls._normalize_text(text)
        return any(marker in normalized for marker in markers)

    @classmethod
    def _should_force_clarify(cls, messages: list[dict]) -> bool:
        turns = cls._recent_user_turns(messages)
        if len(turns) < 2:
            return False

        (sender_a, text_a), (sender_b, text_b) = turns
        if sender_a == sender_b or sender_a == "BOTH" or sender_b == "BOTH":
            return False

        need_markers = ("хочу", "нужно", "нужна", "нужен", "важно", "чувств", "боюсь", "не хватает")
        space_markers = ("пространств", "свобод", "задыха", "зажат", "давит", "в своем")
        closeness_markers = ("близост", "отдаля", "не нужна", "не нужен", "вместе", "связ", "одиноко")

        if not cls._contains_any(text_a, need_markers) or not cls._contains_any(text_b, need_markers):
            return False

        a_space = cls._contains_any(text_a, space_markers)
        b_space = cls._contains_any(text_b, space_markers)
        a_closeness = cls._contains_any(text_a, closeness_markers)
        b_closeness = cls._contains_any(text_b, closeness_markers)

        return (a_space and b_closeness) or (b_space and a_closeness)

    @classmethod
    def _count_user_turns(cls, messages: list[dict]) -> int:
        """Count total user turns in dialogue history."""
        count = 0
        for item in messages:
            if item.get("role") == "user":
                parsed = cls._extract_user_turn(item.get("content", ""))
                if parsed is not None:
                    count += 1
        return count

    _ACTION_REJECTION_MARKERS: tuple[str, ...] = (
        "мы пробовали", "это не поможет", "не то", "не подходит",
        "уже пытались", "не работает", "бесполезно", "не хочу",
        "это не про то", "мимо", "не в этом дело", "ерунда",
        "банально", "шаблонно", "некомпетент",
    )
    _ACTION_PROPOSAL_MARKERS: tuple[str, ...] = (
        "маленький шаг", "на этой неделе", "готовы попробовать", "договор",
        "договоренность", "попробуйте", "предлагаю", "варианта",
        "что одно маленькое", "что вы готовы", "ритуал", "шагом",
    )

    @classmethod
    def _detect_action_rejection(cls, messages: list[dict], current_state: str) -> bool:
        """Detect if user rejected an action proposal (while in OPTIONS/AGREE)."""
        if current_state not in ("OPTIONS", "AGREE"):
            return False
        turns = cls._recent_user_turns(messages, limit=1)
        if not turns:
            return False
        _, text = turns[0]
        return cls._contains_any(text, cls._ACTION_REJECTION_MARKERS)

    @classmethod
    def _assistant_looks_like_action_proposal(cls, text: str) -> bool:
        return cls._contains_any(text, cls._ACTION_PROPOSAL_MARKERS)

    @classmethod
    def _recent_action_loop_detected(cls, messages: list[dict]) -> bool:
        proposal_count = 0
        for item in reversed(messages):
            role = item.get("role")
            content = item.get("content", "")
            if role == "assistant" and cls._assistant_looks_like_action_proposal(content):
                proposal_count += 1
                if proposal_count >= 2:
                    return True
            elif role == "user":
                parsed = cls._extract_user_turn(content)
                if parsed is None:
                    continue
                _, text = parsed
                if not cls._contains_any(text, cls._ACTION_REJECTION_MARKERS):
                    break
        return False

    MIN_USER_TURNS_FOR_OPTIONS = 8

    @classmethod
    def _fallback_state_from_messages(cls, messages: list[dict]) -> str:
        return "CLARIFY" if cls._should_force_clarify(messages) else "DEEPEN"

    def _resolve_effective_state(self, session: SessionState, messages: list[dict]) -> str:
        if self._should_force_clarify(messages):
            log.info(
                "forced_clarify_two_sided_conflict",
                session_id=session.session_id,
                original_state=session.dialogue_state,
                effective_state="CLARIFY",
            )
            return "CLARIFY"

        # Block premature OPTIONS/AGREE if not enough user turns
        if session.dialogue_state in ("OPTIONS", "AGREE"):
            user_turn_count = self._count_user_turns(messages)
            if user_turn_count < self.MIN_USER_TURNS_FOR_OPTIONS:
                fallback_state = self._fallback_state_from_messages(messages)
                log.info(
                    "blocked_premature_options",
                    session_id=session.session_id,
                    original_state=session.dialogue_state,
                    user_turns=user_turn_count,
                    min_required=self.MIN_USER_TURNS_FOR_OPTIONS,
                    effective_state=fallback_state,
                )
                return fallback_state

        # Detect action rejection → force back to DEEPEN
        if self._detect_action_rejection(messages, session.dialogue_state):
            log.info(
                "action_rejection_detected",
                session_id=session.session_id,
                original_state=session.dialogue_state,
                effective_state="DEEPEN",
            )
            return "DEEPEN"

        if session.dialogue_state in ("OPTIONS", "AGREE") and self._recent_action_loop_detected(messages):
            log.info(
                "anti_loop_guard_options",
                session_id=session.session_id,
                original_state=session.dialogue_state,
                effective_state="DEEPEN",
            )
            return "DEEPEN"

        log.info(
            "state_kept_original",
            session_id=session.session_id,
            original_state=session.dialogue_state,
        )
        return session.dialogue_state

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
    ) -> tuple[str, bool, str, dict[str, str | bool]]:
        """
        Отправить сообщение фасилитатору и получить структурированный ответ.
        Возвращает (текст_ответа, risk_flag, next_speaker).
        Побочный эффект: обновляет session.dialogue_state и session.last_turn_summary
        (caller сохраняет сессию в repo после вызова).
        """
        formatted = f"[{sender_label}]: {user_message}"
        dialogue_state_before = session.dialogue_state
        waiting_for_before = session.waiting_for
        await self._add_message(session.session_id, "user", formatted, repo)

        messages = await self._get_history(session.session_id, repo)
        effective_state = self._resolve_effective_state(session, messages)
        system_content = SYSTEM_PROMPT + "\n\n" + self._developer_prompt_for_state(session, effective_state)

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
            effective_state=effective_state,
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

        # Post-response guard: block CLARIFY→DEEPEN when forced CLARIFY
        if effective_state == "CLARIFY" and next_state == "DEEPEN":
            log.info(
                "post_guard_forced_clarify",
                session_id=session.session_id,
                original_state=next_state,
                effective_state="CLARIFY",
            )
            next_state = "CLARIFY"

        # Post-response guard: block premature jump to OPTIONS/AGREE
        if next_state in ("OPTIONS", "AGREE"):
            user_turn_count = self._count_user_turns(messages)
            if user_turn_count < self.MIN_USER_TURNS_FOR_OPTIONS:
                fallback_state = self._fallback_state_from_messages(messages)
                log.info(
                    "post_guard_blocked_premature_options",
                    session_id=session.session_id,
                    model_wanted=next_state,
                    user_turns=user_turn_count,
                    forced_state=fallback_state,
                )
                next_state = fallback_state

        if next_state in ("OPTIONS", "AGREE") and self._detect_action_rejection(messages, dialogue_state_before):
            log.info(
                "action_rejection_detected",
                session_id=session.session_id,
                original_state=dialogue_state_before,
                effective_state="DEEPEN",
            )
            next_state = "DEEPEN"

        if next_state in ("OPTIONS", "AGREE") and self._recent_action_loop_detected(messages):
            log.info(
                "anti_loop_guard_options",
                session_id=session.session_id,
                original_state=dialogue_state_before,
                forced_state="DEEPEN",
            )
            next_state = "DEEPEN"

        if next_state in valid_states:
            session.dialogue_state = next_state
        session.last_turn_summary = message[:150].strip()

        # В историю — только текст, без JSON-обёртки
        await self._add_message(session.session_id, "assistant", message, repo)
        response_meta: dict[str, str | bool] = {
            "addressed_to": addressed_to,
            "next_speaker": next_speaker,
            "next_state": next_state,
            "dialogue_state_before": dialogue_state_before,
            "dialogue_state_after": session.dialogue_state,
            "waiting_for_before": waiting_for_before,
            "risk_flag": risk_flag,
        }

        return message, risk_flag, next_speaker, response_meta

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
