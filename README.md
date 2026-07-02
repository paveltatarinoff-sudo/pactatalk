# PactaTalk — AI-фасилитатор сложных разговоров в паре

**Live:** [pactatalk.app](https://pactatalk.app) · Telegram: [@PactaTalkBot](https://t.me/PactaTalkBot)

Telegram-бот, который ведёт структурированную фасилитацию диалога между двумя партнёрами: держит очередность реплик, не даёт разговору свалиться в эскалацию, доводит до договорённости. Не «чат с ботом», а трёхсторонняя сессия: два человека + AI-фасилитатор с собственной state machine.

> **English TL;DR.** A production Telegram bot that facilitates structured two-person dialogue sessions for couples. Python / aiogram webhook on Fly.io, 7-state finite state machine with server-side handoff invariants, OpenAI structured outputs (strict JSON schema), Redis session state + Postgres snapshots (Alembic), Next.js 16 landing on Vercel, PostHog analytics. 147 tests. The repo also contains a **10-agent parallel AI audit** of the entire system ([`docs/audit/2026-06-24/`](docs/audit/2026-06-24/)) and three source files **restored from orphaned bytecode** with opcode-level verification — see the case story below.

---

## Кейс: жизненный цикл проекта, честно

| Период | Что происходило |
|---|---|
| янв–март 2026 | Спроектировал и построил систему через AI-coding (Claude Code + Codex): бот, лендинг, аналитика, деплой. 83 релиза на Fly.io |
| март 2026 | Валидационная волна: UTM-toolchain, воронки в PostHog, реальные сессии в проде |
| март–июнь 2026 | Пауза по личным обстоятельствам. Проект продолжал работать в проде без присмотра |
| июнь 2026 | **Реанимация:** параллельный аудит из 10 AI-агентов → карта состояния системы → стабилизация → эта публикация |

Пауза и возвращение — часть кейса. Вернуться в заброшенный проект, за день построить полную карту его состояния и довести до публикуемого вида — ровно та задача, которую AI-инструменты решают лучше всего, если уметь их оркестрировать.

## Архитектура

```
Telegram ⇄ aiogram webhook (Fly.io, fra) + secret-token verification
              │
              ├─ FSM: 7 состояний диалога (SETUP · CHECK_IN · CLARIFY · DEEPEN
              │        · DEESCALATE · OPTIONS · AGREE), сервер-сайд инварианты
              ├─ LLM-слой: OpenAI gpt-4o, strict structured outputs
              │        (RESPONSE_SCHEMA: message / next_speaker / risk_flag /
              │         addressed_to / next_state)
              ├─ Redis: живое состояние сессии, resume-голосование двух партнёров
              └─ Postgres (+Alembic): snapshots, insights, privacy-delete cascade

pactatalk.app: Next.js 16 / React 19 / Tailwind 4 → Vercel
Аналитика: PostHog (server-side события бота + landing)
```

## Ключевые инженерные решения

- **`addressed_to` как единственный источник правды для handoff.** LLM возвращает, кому адресована реплика; `next_speaker` выводится из этого поля, а не запрашивается отдельно ([refactor f0586d9](../../commit/f0586d9)). До этого бот страдал классической болезнью multi-party диалога — фасилитатор «терял» очередность.
- **Все пост-гарды — в одном резолвере.** `resolve_handoff_invariants` консолидирует 6 проверок целостности handoff в одну точку ([407e904](../../commit/407e904)); ~30 тестов покрывают именно этот контракт (`tests/test_handoff.py`).
- **Circuit breaker на зацикливание.** Если собеседник отвечает низкоэнергетично на рефлексивные вопросы несколько ходов подряд — канned-фолбэк в обход LLM (`bot/services/loop_guard.py`).
- **Resume-голосование через Redis.** Возобновление прошлой сессии требует согласия обоих партнёров: `waiting / matched / mismatch / duplicate / resolved`, идемпотентно, race-protected.
- **Строгая схема ответа LLM.** Structured outputs со strict JSON schema — ни одного «сырого» текста от модели в проде; при отказе схемы — управляемая деградация.
- **Privacy by design.** Диалоги пользователей не попадают в репозиторий и логи аналитики; каскадное удаление по запросу покрыто тестами (`tests/test_privacy_delete.py`). Секреты — только в Fly secrets, история git проверена на утечки перед публикацией.

## Цифры

- **147 тестов**, все зелёные (2.2 с)
- **7 состояний** FSM, **~30 тестов** только на handoff-контракт
- **149 срабатываний** handoff-сигнатуры в реальных прод-диалогах
- **~14.5 КБ** системный промт + per-state guidelines + динамическая сборка dev-промта (anti-repeat, MI-cooldown, grounding-хинты)
- **83 релиза** на Fly.io
- **12 отчётов аудита**, ~21 000 слов, каждый факт с evidence `file:line`

## Аудит десятью параллельными AI-агентами

Главный мета-артефакт репозитория. Оркестрация — один воркфлоу-скрипт ([`docs/audit/audit-workflow.js`](docs/audit/audit-workflow.js)): фаза Discover пиннит commit SHA, затем **10 специалистов параллельно** (LLM/промты, диалоговая логика, бэкенд, фронтенд, PostHog, evals, деплой, продуктовый путь, UX, дистрибуция) — каждый со своей «линзой», единой 7-секционной схемой отчёта и жёсткими правилами (только инвентаризация, каждый факт с пруфом, запрет на выдумывание). Фаза Synthesize собирает [`STATE_OF_PACTTALK.md`](docs/audit/2026-06-24/STATE_OF_PACTTALK.md) — без права вводить новые факты, с обязательными цитатами `[#N]` и секцией противоречий между специалистами.

Аудит честно нашёл и то, что работает (state machine, structured outputs, privacy-каскад), и то, что было сломано: три файла, потерянные из git, расхождение прод-деплоя с репозиторием, мёртвые фильтры воронок. Спецификация процесса: [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Реставрация исходников из байткода

Аудит показал: `bot/main.py` импортирует три файла, которых нет ни на диске, ни в git — HEAD не собирался с марта. Выжили только `.pyc` в `__pycache__`. Файлы восстановлены дизассемблированием (`marshal` + `dis`, CPython 3.14) с верификацией: перекомпилированная реконструкция совпадает с оригинальным байткодом **опкод-в-опкод и константа-в-константу** по всем 30 code objects, включая номера строк ([3482499](../../commit/3482499)). После восстановления: `import bot.main` — OK, 147 тестов — зелёные.

## Структура репозитория

```
gcs45_bot/          Telegram-бот: aiogram, FSM, LLM-слой, Redis/Postgres, 147 тестов
gcs-landing-v2/     Лендинг: Next.js 16, validation-wave toolchain (UTM-генератор, runbook)
docs/audit/         Аудит: workflow-скрипт, 10 отчётов специалистов, STATE_OF_PACTTALK.md
docs/superpowers/   Спецификация и план аудита (design-first процесс)
```

## Стек

Python 3.11 · aiogram 3 · OpenAI API (gpt-4o, structured outputs) · Redis · PostgreSQL + Alembic · Fly.io · Next.js 16 / React 19 / Tailwind 4 · Vercel · PostHog · pytest

Историческая справка: LLM-модуль называется `claude_service.py` — проект начинался на Claude API, затем был переведён на OpenAI; имя файла сохранено, чтобы не ломать историю коммитов.

---

**Автор:** Pavel Tatarinov — [GitHub](https://github.com/paveltatarinoff-sudo) · paveltatarinoff@gmail.com
Проект спроектирован и построен одним человеком с оркестрацией AI-агентов (Claude Code, Codex) на всех этапах: разработка, аудит, реставрация, публикация.
