from abc import ABC, abstractmethod

from src.domain.entities.session import Session


class SessionRepository(ABC):
    """Repository interface for managing game sessions."""

    @abstractmethod
    async def create(self, session: Session) -> Session:
        """Create a new session.
        
        Args:
            session: Session object to create
            
        Returns:
            Created session
        """
        pass

    @abstractmethod
    async def get(self, session_id: str) -> Session | None:
        """Retrieve a session by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            Session if found, None otherwise
        """
        pass

    @abstractmethod
    async def update(self, session: Session) -> Session:
        """Update an existing session.
        
        Args:
            session: Updated session object
            
        Returns:
            Updated session
        """
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session.
        
        Args:
            session_id: The session ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def list_active(self) -> list[Session]:
        """List all active sessions.
        
        Returns:
            List of active sessions
        """
        pass
