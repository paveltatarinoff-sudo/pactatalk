from __future__ import annotations

import asyncio

from bot.handlers import privacy
from bot.models.session import SessionState
from bot.repositories.session_repo import SessionRepository


class FakeRedis:
    def __init__(self) -> None:
        self.kv: dict[str, object] = {}
        self.sets: dict[str, set[str]] = {}

    async def set(self, key: str, value, ex=None, nx: bool = False):
        if nx and key in self.kv:
            return False
        self.kv[key] = value
        return True

    async def get(self, key: str):
        return self.kv.get(key)

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.kv:
                del self.kv[key]
                deleted += 1
            if key in self.sets:
                del self.sets[key]
                deleted += 1
        return deleted

    async def sadd(self, key: str, *values: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(values)
        return len(bucket) - before

    async def srem(self, key: str, *values: str) -> int:
        bucket = self.sets.setdefault(key, set())
        removed = 0
        for value in values:
            if value in bucket:
                bucket.remove(value)
                removed += 1
        return removed

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))


class FakeResult:
    def __init__(self, values: list[str]) -> None:
        self._values = values

    def scalars(self):
        return self

    def all(self) -> list[str]:
        return list(self._values)


class FakeDb:
    def __init__(self, select_values: list[str] | None = None) -> None:
        self.select_values = select_values or []
        self.executed: list[str] = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def execute(self, statement):
        self.executed.append(str(statement))
        if "SELECT pair_resumes.pair_key" in str(statement):
            return FakeResult(self.select_values)
        return FakeResult([])

    async def commit(self) -> None:
        self.commits += 1


class FakeSessionFactory:
    def __init__(self, db: FakeDb) -> None:
        self._db = db

    def __call__(self):
        return self._db


class MessageStub:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append(text)


class CallbackStub:
    def __init__(self, user_id: int) -> None:
        self.from_user = type("User", (), {"id": user_id})()
        self.message = MessageStub()
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class StateStub:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def test_delete_session_artifacts_cleans_redis_and_db_rows() -> None:
    async def scenario() -> None:
        redis = FakeRedis()
        db = FakeDb()
        repo = SessionRepository(redis, FakeSessionFactory(db))

        session = SessionState(
            session_id="sess-1",
            user_a_id=111,
            user_b_id=222,
            invite_code="ABC123",
        )
        await redis.set("session:sess-1", "{}")
        await redis.set("history:sess-1", "[]")
        await redis.set("user_session:111", "sess-1")
        await redis.set("user_session:222", "sess-1")
        await redis.set("invite:ABC123", "sess-1")
        await redis.sadd("sessions:active", "sess-1")

        repo._find_session_for_cleanup = lambda session_id: asyncio.sleep(0, result=session)  # type: ignore[method-assign]
        await repo.delete_session_artifacts("sess-1")

        assert await redis.get("session:sess-1") is None
        assert await redis.get("history:sess-1") is None
        assert await redis.get("user_session:111") is None
        assert await redis.get("user_session:222") is None
        assert await redis.get("invite:ABC123") is None
        assert "DELETE FROM session_events" in "\n".join(db.executed)
        assert "DELETE FROM session_snapshots" in "\n".join(db.executed)

    asyncio.run(scenario())


def test_delete_pair_resumes_for_user_deletes_found_pair_keys() -> None:
    async def scenario() -> None:
        redis = FakeRedis()
        db = FakeDb(select_values=["111:222", "111:333"])
        repo = SessionRepository(redis, FakeSessionFactory(db))

        deleted = await repo.delete_pair_resumes_for_user(111)

        assert deleted == 2
        assert "SELECT pair_resumes.pair_key" in "\n".join(db.executed)
        assert "DELETE FROM pair_resumes" in "\n".join(db.executed)

    asyncio.run(scenario())


def test_delete_all_user_session_data_orchestrates_and_is_idempotent() -> None:
    async def scenario() -> None:
        redis = FakeRedis()
        repo = SessionRepository(redis, None)

        state = {"calls": 0, "deleted_sessions": [], "aux_deleted": []}

        async def fake_list_session_ids_for_user(user_id: int) -> list[str]:
            state["calls"] += 1
            return ["s1", "s2"] if state["calls"] == 1 else []

        async def fake_list_pair_keys_for_user(user_id: int) -> list[str]:
            return ["111:222"] if state["calls"] == 1 else []

        async def fake_delete_session_artifacts(session_id: str) -> None:
            state["deleted_sessions"].append(session_id)

        async def fake_delete_pair_resumes_for_user(user_id: int) -> int:
            return 1 if state["calls"] == 1 else 0

        async def fake_delete_user_redis_aux(user_id: int) -> None:
            state["aux_deleted"].append(user_id)

        repo.list_session_ids_for_user = fake_list_session_ids_for_user  # type: ignore[method-assign]
        repo.list_pair_keys_for_user = fake_list_pair_keys_for_user  # type: ignore[method-assign]
        repo.delete_session_artifacts = fake_delete_session_artifacts  # type: ignore[method-assign]
        repo.delete_pair_resumes_for_user = fake_delete_pair_resumes_for_user  # type: ignore[method-assign]
        repo.delete_user_redis_aux = fake_delete_user_redis_aux  # type: ignore[method-assign]

        first = await repo.delete_all_user_session_data(111)
        second = await repo.delete_all_user_session_data(111)

        assert first["session_ids_found"] == 2
        assert first["session_artifacts_deleted"] == 2
        assert first["pair_resumes_deleted"] == 1
        assert second["session_ids_found"] == 0
        assert second["session_artifacts_deleted"] == 0
        assert second["pair_resumes_deleted"] == 0
        assert state["deleted_sessions"] == ["s1", "s2"]
        assert state["aux_deleted"] == [111, 111]

    asyncio.run(scenario())


def test_cb_confirm_delete_runs_full_wipe_and_user_delete(monkeypatch) -> None:
    called: dict[str, object] = {}

    class RepoStub:
        def __init__(self, redis, session_factory) -> None:
            called["repo_init"] = session_factory

        async def delete_all_user_session_data(self, user_id: int) -> dict[str, int]:
            called["wipe_user_id"] = user_id
            return {
                "session_ids_found": 1,
                "session_artifacts_deleted": 1,
                "pair_keys_found": 1,
                "pair_resumes_deleted": 1,
            }

    class UserRepoStub:
        def __init__(self, db) -> None:
            called["user_repo_init"] = True

        async def delete_user_data(self, user_id: int) -> None:
            called["user_delete_user_id"] = user_id

    class DbSessionStub:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class SessionFactoryStub:
        def __call__(self):
            return DbSessionStub()

    monkeypatch.setattr(privacy, "SessionRepository", RepoStub)
    monkeypatch.setattr(privacy, "UserRepository", UserRepoStub)

    callback = CallbackStub(111)
    state = StateStub()

    asyncio.run(
        privacy.cb_confirm_delete(
            callback,
            SessionFactoryStub(),
            FakeRedis(),
            state,
        )
    )

    assert called["wipe_user_id"] == 111
    assert called["user_delete_user_id"] == 111
    assert state.cleared is True
    assert callback.answered is True
    assert callback.message.answers
