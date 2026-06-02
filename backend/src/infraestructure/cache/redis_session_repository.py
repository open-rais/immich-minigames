import json
from datetime import datetime

import redis.asyncio as redis

from src.domain.entities.session import Session
from src.domain.repositories.session_repository import SessionRepository


class RedisSessionRepository(SessionRepository):
    """Redis implementation of SessionRepository."""

    SESSION_KEY_PREFIX = "session:"
    SESSION_INDEX_KEY = "sessions:active"
    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    def _session_key(self, session_id: str) -> str:
        return f"{self.SESSION_KEY_PREFIX}{session_id}"

    def _serialize_session(self, session: Session) -> str:
        data = {
            "session_id": session.session_id,
            "game_slug": session.game_slug,
            "mode_slug": session.mode_slug,

            "score": session.score,
            "streak": session.streak,
            "rounds_played": session.rounds_played,

            "is_active": session.is_active,
            "is_game_over": session.is_game_over,

            "started_at": session.started_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),

            "game_state": session.game_state,
        }

        return json.dumps(data)

    def _deserialize_session(self, data: str) -> Session:
        obj = json.loads(data)

        session = Session(
            session_id=obj["session_id"],
            game_slug=obj["game_slug"],
            mode_slug=obj["mode_slug"],
            score=obj["score"],
            streak=obj["streak"],
            rounds_played=obj["rounds_played"],
            is_active=obj["is_active"],
            is_game_over=obj["is_game_over"],
            started_at=datetime.fromisoformat(obj["started_at"]),
            last_activity_at=datetime.fromisoformat(obj["last_activity_at"]),
            game_state=obj.get("game_state", {}),
        )

        return session

    async def create(self, session: Session) -> Session:
        key = self._session_key(session.session_id)
        serialized = self._serialize_session(session)

        await self.redis.setex(
            key,
            self.DEFAULT_TTL,
            serialized,
        )

        await self.redis.sadd(self.SESSION_INDEX_KEY, session.session_id)

        return session

    async def get(self, session_id: str) -> Session | None:
        key = self._session_key(session_id)
        data = await self.redis.get(key)

        if not data:
            return None

        if isinstance(data, bytes):
            data = data.decode()

        return self._deserialize_session(data)

    async def update(self, session: Session) -> Session:
        key = self._session_key(session.session_id)
        serialized = self._serialize_session(session)

        await self.redis.setex(
            key,
            self.DEFAULT_TTL,
            serialized,
        )

        return session

    async def delete(self, session_id: str) -> bool:
        key = self._session_key(session_id)

        deleted = await self.redis.delete(key)
        await self.redis.srem(self.SESSION_INDEX_KEY, session_id)

        return deleted > 0

    async def list_active(self) -> list[Session]:
        session_ids = await self.redis.smembers(self.SESSION_INDEX_KEY)

        sessions = []

        for session_id in session_ids:
            if isinstance(session_id, bytes):
                session_id = session_id.decode()

            session = await self.get(session_id)
            if session:
                sessions.append(session)

        return sessions
    