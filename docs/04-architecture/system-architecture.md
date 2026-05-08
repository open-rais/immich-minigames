# System Architecture

## High-Level Structure

```
immich-minigames/
├── backend/
├── frontend/
├── docker/
└── docs/
```

## Architecture Pattern

The project uses a **modular monolith** architecture with **Clean Architecture** principles applied to the backend.

This allows:
- Independent backend and frontend development
- Plugin-based game system
- Clear separation of concerns
- Single Docker Compose deployment

## Key Architectural Decisions

1. **Modular Monolith** - Balanced between simplicity and extensibility
2. **Clean Architecture** - Backend layers independent of frameworks
3. **Plugin System** - Games as isolated, pluggable modules
4. **No User Accounts** - Connection via Immich API key only
5. **Async-First** - Python async/await throughout
6. **Dependency Injection** - Loose coupling between layers
