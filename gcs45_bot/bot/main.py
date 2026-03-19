import asyncio
import html
import logging

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker

from bot.config import settings
from bot.handlers import start, session, facilitator, privacy, admin
from bot.models.user import Base
from bot.repositories.session_repo import SessionRepository
from bot.services.session_service import SessionService
from bot.models.session_record import SessionSnapshot  # noqa: F401
from bot.models.session_event import SessionEvent  # noqa: F401
from bot.models.pair_resume import PairResume  # noqa: F401

logger = structlog.get_logger()
MAX_TIMEOUT_REMINDERS = 3


def setup_logging() -> None:
    logging.basicConfig(level=settings.log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if not settings.is_production
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


async def create_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def maybe_bootstrap_schema(engine: AsyncEngine) -> None:
    if not settings.enable_dev_schema_bootstrap:
        return
    if settings.is_production:
        logger.warning("dev_schema_bootstrap_ignored_in_production")
        return

    logger.warning("dev_schema_bootstrap_enabled_using_create_all")
    await create_db(engine)


async def health_check(redis: Redis, engine: AsyncEngine) -> tuple[bool, dict[str, str]]:
    checks: dict[str, str] = {}

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "error"

    healthy = all(status == "ok" for status in checks.values())
    return healthy, checks


async def timeout_watcher(bot: Bot, redis: Redis, session_factory: async_sessionmaker) -> None:
    repo = SessionRepository(redis, session_factory)
    svc = SessionService(repo, bot)

    while True:
        try:
            sessions = await repo.list_active_sessions()
            logger.info("timeout_watcher_heartbeat", active_session_count=len(sessions))
            for current in sessions:
                if current.mode == "closing" or current.user_b_id == 0:
                    continue
                if current.timeout_reminders_sent >= MAX_TIMEOUT_REMINDERS:
                    continue
                if not current.response_deadline_exceeded(settings.user_response_timeout_seconds):
                    continue

                if current.waiting_for == "A":
                    target_ids = [current.user_a_id]
                    reminder = f"{html.escape(current.name_a or 'Партнёр A')}, я всё ещё жду твой ответ."
                elif current.waiting_for == "B":
                    target_ids = [current.user_b_id]
                    reminder = f"{html.escape(current.name_b or 'Партнёр B')}, я всё ещё жду твой ответ."
                else:
                    target_ids = [uid for uid in (current.user_a_id, current.user_b_id) if uid]
                    reminder = "Я всё ещё жду по одному ответу от каждого из вас, чтобы продолжить."

                for uid in target_ids:
                    await bot.send_message(uid, f"{reminder}\n\nЕсли хотите продолжить позже, просто напишите в этот чат.")

                current.timeout_reminders_sent += 1
                await repo.save(current)
                logger.info(
                    "session_timeout_reminder_sent",
                    session_id=current.session_id,
                    waiting_for=current.waiting_for,
                    target_count=len(target_ids),
                )
        except Exception:
            logger.exception("timeout_watcher_failed")

        await asyncio.sleep(settings.timeout_check_interval_seconds)


async def main() -> None:
    setup_logging()
    log = structlog.get_logger()

    # Подключения
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    # Neon PostgreSQL требует SSL; asyncpg не читает ssl= из URL — передаём через connect_args
    db_kwargs = {}
    if "neon.tech" in settings.database_url or "ssl=require" in settings.database_url:
        db_kwargs["connect_args"] = {"ssl": "require"}
    # Убираем параметр ssl= из URL — asyncpg его не понимает в строке подключения
    db_url = settings.database_url.split("?")[0]
    engine = create_async_engine(db_url, echo=not settings.is_production, **db_kwargs)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    await maybe_bootstrap_schema(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Передаём зависимости через workflow_data
    dp["redis"] = redis
    dp["engine"] = engine
    dp["session_factory"] = session_factory

    # Регистрация роутеров
    # Порядок важен: команды и кнопки — первыми, фасилитатор — последним
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(session.router)
    dp.include_router(privacy.router)
    dp.include_router(facilitator.router)  # перехватывает всё остальное

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не задан в .env — бот не может запуститься без ключа.")

    log.info("Starting PactaTalk Bot", env=settings.env)
    timeout_task = asyncio.create_task(timeout_watcher(bot, redis, session_factory))

    if settings.use_webhook:
        # Продакшн: webhook
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web

        async def health_handler(_: web.Request) -> web.Response:
            healthy, checks = await health_check(redis, engine)
            status = 200 if healthy else 503
            body = {
                "status": "ok" if healthy else "unhealthy",
                "checks": checks,
            }
            return web.json_response(body, status=status)

        app = web.Application()
        app.router.add_get("/health", health_handler)
        webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret)
        webhook_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)

        await bot.set_webhook(settings.webhook_url, secret_token=settings.webhook_secret)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8080)
        await site.start()
        try:
            await asyncio.Event().wait()
        finally:
            timeout_task.cancel()
            await runner.cleanup()
            await redis.aclose()
            await engine.dispose()
            await bot.session.close()
    else:
        # Разработка: polling
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot)
        finally:
            timeout_task.cancel()
            await redis.aclose()
            await engine.dispose()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
