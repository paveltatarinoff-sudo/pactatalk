import dataclasses
import json
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker
import structlog

from bot.models.session_event import SessionEvent
from bot.models.session import SessionState
from bot.models.session_record import SessionSnapshot
from bot.models.pair_resume import PairResume, make_pair_key

SESSION_TTL = 60 * 60 * 24 * 7  # 7 дней
INVITE_TTL = 60 * 60 * 24       # 24 часа (инвайт-коды — короткоживущие)
HISTORY_TTL = 60 * 60 * 24 * 7  # 7 дней
ACTIVE_SESSIONS_KEY = "sessions:active"

log = structlog.get_logger()


def _serialize(session: SessionState) -> str:
    data = asdict(session)
    data["started_at"] = session.started_at.isoformat()
    data["paused_at"] = session.paused_at.isoformat() if session.paused_at else None
    data["waiting_since"] = session.waiting_since.isoformat()
    return json.dumps(data)


def _deserialize(raw: str) -> SessionState:
    data = json.loads(raw)
    data["started_at"] = datetime.fromisoformat(data["started_at"])
    if data["paused_at"]:
        data["paused_at"] = datetime.fromisoformat(data["paused_at"])
    if data.get("waiting_since"):
        data["waiting_since"] = datetime.fromisoformat(data["waiting_since"])
    known = {f.name for f in dataclasses.fields(SessionState)}
    return SessionState(**{k: v for k, v in data.items() if k in known})


class SessionRepository:
    def __init__(self, redis: Redis, session_factory: Optional[async_sessionmaker] = None) -> None:
        self._redis = redis
        self._session_factory = session_factory

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def _user_key(self, user_id: int) -> str:
        return f"user_session:{user_id}"

    def _invite_key(self, code: str) -> str:
        return f"invite:{code}"

    async def save(self, session: SessionState) -> None:
        key = self._key(session.session_id)
        await self._redis.set(key, _serialize(session), ex=SESSION_TTL)
        await self._redis.sadd(ACTIVE_SESSIONS_KEY, session.session_id)
        # Индекс user → session_id для быстрого поиска
        if session.user_a_id:
            await self._redis.set(self._user_key(session.user_a_id), session.session_id, ex=SESSION_TTL)
        if session.user_b_id:
            await self._redis.set(self._user_key(session.user_b_id), session.session_id, ex=SESSION_TTL)
        await self._save_snapshot(session)

    async def get(self, session_id: str) -> Optional[SessionState]:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            session = await self._load_snapshot(session_id)
            if session is None:
                return None
            await self._redis.set(self._key(session.session_id), _serialize(session), ex=SESSION_TTL)
            if session.user_a_id:
                await self._redis.set(self._user_key(session.user_a_id), session.session_id, ex=SESSION_TTL)
            if session.user_b_id:
                await self._redis.set(self._user_key(session.user_b_id), session.session_id, ex=SESSION_TTL)
            await self._redis.sadd(ACTIVE_SESSIONS_KEY, session.session_id)
            return session
        return _deserialize(raw)

    async def get_by_user(self, user_id: int) -> Optional[SessionState]:
        session_id = await self._redis.get(self._user_key(user_id))
        if session_id is None:
            return None
        return await self.get(session_id)

    async def delete(self, session: SessionState) -> None:
        await self._redis.delete(self._key(session.session_id))
        await self._redis.srem(ACTIVE_SESSIONS_KEY, session.session_id)
        if session.user_a_id:
            await self._redis.delete(self._user_key(session.user_a_id))
        if session.user_b_id:
            await self._redis.delete(self._user_key(session.user_b_id))
        await self._delete_snapshot(session.session_id)

    async def save_invite(self, code: str, session_id: str) -> None:
        await self._redis.set(self._invite_key(code), session_id, ex=INVITE_TTL)

    async def get_by_invite(self, code: str) -> Optional[SessionState]:
        session_id = await self._redis.get(self._invite_key(code))
        if session_id is None:
            return None
        return await self.get(session_id)

    async def delete_invite(self, code: str) -> None:
        await self._redis.delete(self._invite_key(code))

    # ── История диалога (для ClaudeService) ───────────────────────────────────

    def _history_key(self, session_id: str) -> str:
        return f"history:{session_id}"

    async def get_history(self, session_id: str) -> list[dict]:
        raw = await self._redis.get(self._history_key(session_id))
        if raw is None:
            return []
        return json.loads(raw)

    async def save_history(self, session_id: str, history: list[dict]) -> None:
        await self._redis.set(self._history_key(session_id), json.dumps(history), ex=HISTORY_TTL)

    async def delete_history(self, session_id: str) -> None:
        await self._redis.delete(self._history_key(session_id))

    async def _find_session_for_cleanup(self, session_id: str) -> Optional[SessionState]:
        raw = await self._redis.get(self._key(session_id))
        if raw is not None:
            return _deserialize(raw)
        return await self._load_snapshot(session_id)

    async def append_event(
        self,
        *,
        session_id: str,
        role: str,
        speaker_label: Optional[str],
        content: str,
        dialogue_state_before: Optional[str] = None,
        dialogue_state_after: Optional[str] = None,
        waiting_for_before: Optional[str] = None,
        waiting_for_after: Optional[str] = None,
        next_speaker: Optional[str] = None,
        addressed_to: Optional[str] = None,
        risk_flag: Optional[bool] = None,
    ) -> None:
        if self._session_factory is None:
            return

        async with self._session_factory() as db:
            db.add(
                SessionEvent(
                    session_id=session_id,
                    role=role,
                    speaker_label=speaker_label,
                    content=content,
                    dialogue_state_before=dialogue_state_before,
                    dialogue_state_after=dialogue_state_after,
                    waiting_for_before=waiting_for_before,
                    waiting_for_after=waiting_for_after,
                    next_speaker=next_speaker,
                    addressed_to=addressed_to,
                    risk_flag=risk_flag,
                )
            )
            await db.commit()

    async def list_session_ids_for_user(self, user_id: int) -> list[str]:
        session_ids: set[str] = set()

        active = await self.get_by_user(user_id)
        if active is not None:
            session_ids.add(active.session_id)

        if self._session_factory is None:
            return sorted(session_ids)

        async with self._session_factory() as db:
            result = await db.execute(
                select(SessionSnapshot.session_id).where(
                    or_(
                        SessionSnapshot.user_a_id == user_id,
                        SessionSnapshot.user_b_id == user_id,
                    )
                )
            )
            session_ids.update(result.scalars().all())

        return sorted(session_ids)

    async def delete_session_artifacts(self, session_id: str) -> None:
        session = await self._find_session_for_cleanup(session_id)

        await self._redis.delete(self._key(session_id))
        await self._redis.delete(self._history_key(session_id))
        await self._redis.srem(ACTIVE_SESSIONS_KEY, session_id)

        if session is not None:
            if session.user_a_id:
                await self._redis.delete(self._user_key(session.user_a_id))
            if session.user_b_id:
                await self._redis.delete(self._user_key(session.user_b_id))
            if session.invite_code:
                await self._redis.delete(self._invite_key(session.invite_code))

        if self._session_factory is None:
            return

        async with self._session_factory() as db:
            await db.execute(delete(SessionEvent).where(SessionEvent.session_id == session_id))
            await db.execute(delete(SessionSnapshot).where(SessionSnapshot.session_id == session_id))
            await db.commit()

    async def list_pair_keys_for_user(self, user_id: int) -> list[str]:
        if self._session_factory is None:
            return []

        pair_keys: set[str] = set()
        lo_pattern = f"{user_id}:%"
        hi_pattern = f"%:{user_id}"

        async with self._session_factory() as db:
            result = await db.execute(
                select(PairResume.pair_key).where(
                    or_(
                        PairResume.pair_key.like(lo_pattern),
                        PairResume.pair_key.like(hi_pattern),
                    )
                )
            )
            pair_keys.update(result.scalars().all())

        return sorted(pair_keys)

    async def delete_pair_resumes_for_user(self, user_id: int) -> int:
        pair_keys = await self.list_pair_keys_for_user(user_id)
        if not pair_keys or self._session_factory is None:
            return 0

        async with self._session_factory() as db:
            await db.execute(delete(PairResume).where(PairResume.pair_key.in_(pair_keys)))
            await db.commit()

        return len(pair_keys)

    async def delete_user_redis_aux(self, user_id: int) -> None:
        await self._redis.delete(
            f"summary:{user_id}",
            f"first_msg:{user_id}",
            self._user_key(user_id),
        )

    async def delete_all_user_session_data(self, user_id: int) -> dict[str, int]:
        session_ids = await self.list_session_ids_for_user(user_id)
        pair_keys = await self.list_pair_keys_for_user(user_id)

        for session_id in session_ids:
            await self.delete_session_artifacts(session_id)

        deleted_pair_resumes = await self.delete_pair_resumes_for_user(user_id)
        await self.delete_user_redis_aux(user_id)

        return {
            "session_ids_found": len(session_ids),
            "session_artifacts_deleted": len(session_ids),
            "pair_keys_found": len(pair_keys),
            "pair_resumes_deleted": deleted_pair_resumes,
        }

    async def list_active_sessions(self) -> list[SessionState]:
        session_ids = await self._redis.smembers(ACTIVE_SESSIONS_KEY)
        sessions: list[SessionState] = []
        for session_id in session_ids:
            session = await self.get(session_id)
            if session is not None:
                sessions.append(session)
            else:
                await self._redis.srem(ACTIVE_SESSIONS_KEY, session_id)
        return sessions

    async def _save_snapshot(self, session: SessionState) -> None:
        if self._session_factory is None:
            return

        payload = _serialize(session)
        async with self._session_factory() as db:
            existing = await db.get(SessionSnapshot, session.session_id)
            if existing is None:
                existing = SessionSnapshot(
                    session_id=session.session_id,
                    user_a_id=session.user_a_id,
                    user_b_id=session.user_b_id,
                    dialogue_state=session.dialogue_state,
                    waiting_for=session.waiting_for,
                    phase=session.phase,
                    mode=session.mode,
                    payload=payload,
                )
                db.add(existing)
            else:
                existing.user_a_id = session.user_a_id
                existing.user_b_id = session.user_b_id
                existing.dialogue_state = session.dialogue_state
                existing.waiting_for = session.waiting_for
                existing.phase = session.phase
                existing.mode = session.mode
                existing.payload = payload
                existing.updated_at = datetime.utcnow()
            await db.commit()

    async def _load_snapshot(self, session_id: str) -> Optional[SessionState]:
        if self._session_factory is None:
            return None

        async with self._session_factory() as db:
            snapshot = await db.get(SessionSnapshot, session_id)
            if snapshot is None:
                return None
            log.info("session_restored_from_snapshot", session_id=session_id)
            return _deserialize(snapshot.payload)

    async def _delete_snapshot(self, session_id: str) -> None:
        if self._session_factory is None:
            return

        async with self._session_factory() as db:
            await db.execute(delete(SessionSnapshot).where(SessionSnapshot.session_id == session_id))
            await db.commit()

    # ── Pair resume (for session continuity) ─────────────────────────────────

    async def save_pair_resume(
        self,
        session: SessionState,
        resume_context: str,
    ) -> None:
        """Save or update the resume context for a pair."""
        if self._session_factory is None:
            return
        if not session.user_a_id or not session.user_b_id:
            return

        pair_key = make_pair_key(session.user_a_id, session.user_b_id)
        async with self._session_factory() as db:
            existing = await db.get(PairResume, pair_key)
            if existing is None:
                db.add(PairResume(
                    pair_key=pair_key,
                    session_id=session.session_id,
                    name_a=session.name_a or "",
                    name_b=session.name_b or "",
                    resume_context=resume_context,
                    dialogue_state=session.dialogue_state,
                ))
            else:
                existing.session_id = session.session_id
                existing.name_a = session.name_a or ""
                existing.name_b = session.name_b or ""
                existing.resume_context = resume_context
                existing.dialogue_state = session.dialogue_state
                existing.updated_at = datetime.utcnow()
            await db.commit()

    async def get_pair_resume(self, user_a_id: int, user_b_id: int) -> Optional[PairResume]:
        """Load the PairResume for a pair. Returns None if not found."""
        if self._session_factory is None:
            return None
        if not user_a_id or not user_b_id:
            return None

        pair_key = make_pair_key(user_a_id, user_b_id)
        async with self._session_factory() as db:
            resume = await db.get(PairResume, pair_key)
            if resume is None:
                return None
            return resume

    async def delete_pair_resume(self, user_a_id: int, user_b_id: int) -> None:
        """Delete the resume context for a pair."""
        if self._session_factory is None:
            return
        if not user_a_id or not user_b_id:
            return

        pair_key = make_pair_key(user_a_id, user_b_id)
        async with self._session_factory() as db:
            await db.execute(delete(PairResume).where(PairResume.pair_key == pair_key))
            await db.commit()
