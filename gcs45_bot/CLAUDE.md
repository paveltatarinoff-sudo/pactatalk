# PactaTalk Bot

Telegram-бот для фасилитации диалога между партнёрами.

Этот файл нужен как короткий operational context для coding agent.
Источник истины по runtime-поведению бота:
- `bot/services/claude_service.py`
- server-side guards в `bot/services/claude_service.py` и `bot/handlers/facilitator.py`
- session start / end flow в `bot/handlers/session.py`
- storage logic в `bot/repositories/session_repo.py`

## Что важно помнить

- Не опирайся на старые продуктовые документы как на источник текущей логики.
- Если поведение бота и этот файл расходятся, верить нужно коду.
- Любые изменения в фасилитации должны сохранять текущий production baseline:
  - не уходить рано в решения
  - не повторять шаблонные action suggestions
  - держать адресацию и handoff согласованными
  - поддерживать continuity через resume
- Ветка P1 handoff/BOTH не считается текущим production baseline. Она экспериментальная, пока не закреплена в проде.

## Текущий behavioral baseline

### 1. Dialogue states

Бот работает через состояния:
- `SETUP`
- `CLARIFY`
- `DEESCALATE`
- `DEEPEN`
- `OPTIONS`
- `AGREE`
- `CHECK_IN`

State selection и prompt rules живут в `bot/services/claude_service.py`.

### 2. Addressing / handoff

Источник истины для handoff: `addressed_to`.

Актуальный path такой:
- модель возвращает `message`, `addressed_to`, `next_speaker`, `next_state`
- сервер приводит handoff к инвариантам только в `ClaudeService.resolve_handoff_invariants()`
- после этого `next_speaker` считается derived field от `addressed_to`
- `session.waiting_for` получает уже финальное значение после `resolve_handoff_invariants()`

Что делает сервер на handoff-слое:
- валидирует `addressed_to`
- форсит `BOTH` в `OPTIONS/AGREE/CHECK_IN`
- блокирует `BOTH` в `DEEPEN/DEESCALATE/CLARIFY`
- ограничивает затяжной `BOTH`
- удерживает фокус на уязвимом спикере
- делает принудительный switch после 3+ ходов одного партнёра подряд

Что больше не является authority-layer:
- `facilitator` не переписывает handoff по тексту ответа, только может логировать observed mismatch
- feedback о неверной адресации влияет только через prompt signal, без server-side override

Текущая очередь хранится в `session.waiting_for`.
Подпись `теперь твой ход` строится из `session.waiting_for`, поэтому handoff надо проверять до `_apply_next_speaker(...)`.

### 3. Policy for BOTH

Production baseline не опирается на экспериментальную P1-ветку с расширенным handoff/BOTH behavior.

Нормальный baseline:
- `BOTH` допустим в начале сессии
- в режиме `BOTH` первый ответ не показывается сразу второму партнёру
- когда оба ответа получены, бот показывает обоим оба ответа и только потом даёт общий ответ фасилитатора
- не нужно добавлять новые правила handoff/BOTH, если они не закреплены в текущем production коде

### 4. Premature solutions (P0)

Бот не должен слишком быстро переходить к решениям, ритуалам, маленьким шагам и договорённостям.

Текущий baseline:
- ранний `OPTIONS/AGREE` блокируется
- rejection action suggestions возвращает разговор в `DEEPEN`
- repeated action cycles блокируются
- шаблонные шаги и canned phrasing считаются дефектом, а не нормой

Если пользователь говорит:
- `мы пробовали`
- `не помогает`
- `мимо`
- `не то`
- `шаблонно`

это не повод предложить новый похожий шаг.
Это сигнал вернуться к боли, конфликту и смыслу.

### 5. Anti-repeat / anti-template (P2.1)

В `claude_service.py` есть защита от повторяющихся intervention patterns и canned phrasing.

При изменениях prompt behavior нужно проверять:
- не повторяет ли бот один и тот же тип action suggestions
- не переупаковывает ли один и тот же совет разными словами
- умеет ли после rejection возвращаться к чувствам

### 6. Session continuity (P3.1)

Поддержка продолжения прошлой сессии уже есть.

Ключевые элементы:
- таблица `pair_resumes`
- `resume_context` в `SessionState`
- `generate_resume_context()` в `ClaudeService`
- загрузка resume при старте новой сессии
- resume-aware `SETUP` prompt

Resume-start не должен звучать как новый onboarding.
Нормальное начало:
- коротко напомнить контекст
- спросить, хотят ли продолжить прошлую тему или начать новую

### 7. Storage model

Runtime context:
- `SessionState` хранится в Redis
- prompt history хранится в Redis как `history:{session_id}`

Durable storage:
- `session_snapshots` в Postgres
- `session_events` в Postgres для transcript / post-mortem
- `pair_resumes` в Postgres для continuity между сессиями

Если задача связана с product analysis, research или post-mortem, надо учитывать именно `session_events`, а не только Redis history.

### 8. Schema path

Alembic теперь считается основным schema path.

Нормальный local/dev flow:
- `alembic upgrade head`
- потом запуск приложения

`Base.metadata.create_all(...)` больше не является baseline runtime bootstrap path.
Флаг `ENABLE_DEV_SCHEMA_BOOTSTRAP` существует только как временный dev fallback и не должен использоваться в production.

## Основные файлы

- `bot/services/claude_service.py`
  Главный слой prompt logic, state rules, anti-repeat logic, resume generation.

- `bot/handlers/facilitator.py`
  Приём сообщений, `BOTH` flow, применение `next_speaker`, relay и server-side addressing guardrail.

- `bot/handlers/session.py`
  Start / join / end session flow, загрузка и сохранение pair resume.

- `bot/repositories/session_repo.py`
  Redis session/history + Postgres snapshots/events/pair resumes.

- `bot/models/session.py`
  `SessionState`, включая `resume_context`, `waiting_for`, `pending_a_message`, `pending_b_message`.

## Как работать с изменениями

Если меняешь поведение фасилитатора:
1. Сначала найди фактическую server-side логику в коде.
2. Вноси минимальные изменения.
3. Проверяй синтаксис, если менялся код.
4. Прогоняй релевантные unit tests.
5. Если меняется prompt behavior, прогони сценарии через `scripts/prompt_harness.py`.

Не вводи новые продуктовые правила в `CLAUDE.md`, если они ещё не закреплены в коде.
Этот файл должен описывать текущее состояние production baseline, а не желаемое будущее.

## Стиль общения

- Пользователь русскоязычный. Объяснения, анализ и разговор — на русском. Код, комментарии и переменные — на английском.
- На быстрые вопросы — сначала прямой ответ, потом предложение раскрыть детали. Не надо лезть в кодовую базу ради простого вопроса.
- Не пересказывай что ты сделал в конце ответа — пользователь видит diff.

## Работа с задачами для Codex

Когда просят сформулировать задачу для Codex (или другого AI-агента):
1. **Не читай весь кодовой базы.** Спроси, какие файлы релевантны, или используй минимальную разведку.
2. Фокус — на готовом промпте, а не на решении проблемы самостоятельно.
3. Формат задачи: Title, Context (3 предложения макс), Root Cause Hypothesis, Acceptance Criteria (чекбоксы), Files to Modify.
4. Укладывайся в 500 слов.

## Деплой

Перед тем как предлагать шаги деплоя — проверь, есть ли deploy-скрипт, git remote или CI pipeline. Если ничего нет — спроси, как пользователь деплоит, не угадывай.
