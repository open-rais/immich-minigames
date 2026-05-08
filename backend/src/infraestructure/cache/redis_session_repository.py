import json
from datetime import datetime

import redis.asyncio as redis

from src.domain.entities.session import Session
from src.domain.repositories.session_repository import SessionRepository


class RedisSessionRepository(SessionRepository):
    """Redis implementation of SessionRepository.
    
    Uses Redis for fast, ephemeral session storage with TTL.
    """

    SESSION_KEY_PREFIX = "session:"
    SESSION_INDEX_KEY = "sessions:active"
    DEFAULT_TTL = 3600  # 1 hour in seconds

    def __init__(self, redis_client: redis.Redis) -> None:
        """Initialize Redis session repository.
        
        Args:
            redis_client: Async Redis client
        """
        self.redis = redis_client

    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"{self.SESSION_KEY_PREFIX}{session_id}"

    def _serialize_session(self, session: Session) -> str:
        """Serialize session to JSON string."""
        data = {
            "session_id": session.session_id,
            "game_slug": session.game_slug,
            "mode_slug": session.mode_slug,
            "score": session.score,
            "rounds_played": session.rounds_played,
            "current_round_id": session.current_round_id,
            "started_at": session.started_at.isoformat(),
            "last_activity_at": session.last_activity_at.isoformat(),
            "is_active": session.is_active,
            "metadata": session.metadata,
        }
        return json.dumps(data)

    def _deserialize_session(self, data: str) -> Session:
        """Deserialize session from JSON string."""
        obj = json.loads(data)
        return Session(
            session_id=obj["session_id"],
            game_slug=obj["game_slug"],
            mode_slug=obj["mode_slug"],
            score=obj["score"],
            rounds_played=obj["rounds_played"],
            current_round_id=obj["current_round_id"],
            started_at=datetime.fromisoformat(obj["started_at"]),
            last_activity_at=datetime.fromisoformat(obj["last_activity_at"]),
            is_active=obj["is_active"],
            metadata=obj["metadata"],
        )

    async def create(self, session: Session) -> Session:
        """Create a new session with TTL."""
        key = self._session_key(session.session_id)
        serialized = self._serialize_session(session)
        
        # Set in Redis with TTL
        await self.redis.setex(
            key,
            self.DEFAULT_TTL,
            serialized,
        )
        
        # Add to active sessions index
        await self.redis.sadd(self.SESSION_INDEX_KEY, session.session_id)
        
        return session

    async def get(self, session_id: str) -> Session | None:
        """Retrieve a session from Redis."""
        key = self._session_key(session_id)
        data = await self.redis.get(key)
        
        if not data:
            return None
        
        return self._deserialize_session(data.decode() if isinstance(data, bytes) else data)

    async def update(self, session: Session) -> Session:
        """Update an existing session, extending TTL."""
        key = self._session_key(session.session_id)
        serialized = self._serialize_session(session)
        
        # Update in Redis with TTL
        await self.redis.setex(
            key,
            self.DEFAULT_TTL,
            serialized,
        )
        
        return session

    async def delete(self, session_id: str) -> bool:
        """Delete a session from Redis."""
        key = self._session_key(session_id)
        
        # Delete from sessions
        deleted = await self.redis.delete(key)
        
        # Remove from active index
        await self.redis.srem(self.SESSION_INDEX_KEY, session_id)
        
        return deleted > 0

    async def list_active(self) -> list[Session]:
        """List all active sessions."""
        session_ids = await self.redis.smembers(self.SESSION_INDEX_KEY)
        
        sessions = []
        for session_id in session_ids:
            session_id_str = (
                session_id.decode() if isinstance(session_id, bytes) else session_id
            )
            session = await self.get(session_id_str)
            if session:
                sessions.append(session)
        
        return sessions
