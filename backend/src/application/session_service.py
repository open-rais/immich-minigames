from src.domain.entities.session import Session
from src.domain.repositories.session_repository import SessionRepository
from src.application.game_registry import get_game_registry


class SessionService:
    """Service for orchestrating game sessions.
    
    Handles session lifecycle: creation, retrieval, updates, cleanup.
    """

    def __init__(self, session_repository: SessionRepository) -> None:
        """Initialize session service.
        
        Args:
            session_repository: Repository for session persistence
        """
        self.repository = session_repository

    async def create_session(
        self,
        game_slug: str,
        mode_slug: str,
    ) -> Session:
        """Create a new game session.
        
        Args:
            game_slug: The game to play
            mode_slug: The mode of the game
            
        Returns:
            Created session
            
        Raises:
            ValueError: If game or mode is invalid
        """
        registry = get_game_registry()
        
        # Validate game exists
        if not registry.is_registered(game_slug):
            raise ValueError(f"Game '{game_slug}' is not registered")
        
        # Validate mode exists
        plugin = registry.create_instance(game_slug)
        game_info = await plugin.get_game_info()
        valid_modes = [mode.slug for mode in game_info.modes]
        
        if mode_slug not in valid_modes:
            raise ValueError(
                f"Mode '{mode_slug}' is not valid for game '{game_slug}'. "
                f"Valid modes: {', '.join(valid_modes)}"
            )
        
        # Create session
        session = Session(
            game_slug=game_slug,
            mode_slug=mode_slug,
        )
        
        return await self.repository.create(session)

    async def get_session(self, session_id: str) -> Session | None:
        """Get an existing session.
        
        Args:
            session_id: The session ID
            
        Returns:
            Session if found and active, None otherwise
        """
        session = await self.repository.get(session_id)
        
        if not session:
            return None
        
        # Check if session is still active
        if not session.is_active:
            return None
        
        return session

    async def update_session(self, session: Session) -> Session:
        """Update session (e.g., after answering a round).
        
        Args:
            session: Updated session object
            
        Returns:
            Updated session
        """
        return await self.repository.update(session)

    async def end_session(self, session_id: str) -> bool:
        """End a session.
        
        Args:
            session_id: The session ID
            
        Returns:
            True if ended, False if not found
        """
        return await self.repository.delete(session_id)
