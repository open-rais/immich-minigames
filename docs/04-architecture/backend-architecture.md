# Backend Architecture

## Clean Architecture Layers

The backend follows Clean Architecture principles with the following layer structure:

```
backend/
├── src/
│   ├── domain/           # Business logic (frameworks independent)
│   ├── application/      # Use cases and orchestration
│   ├── infrastructure/   # External integrations (DB, APIs)
│   ├── presentation/     # REST API endpoints
│   ├── games/            # Game plugins
│   └── core/             # Shared constants and utilities
```

---

## Layer Responsibilities

### Domain

Contains pure business logic independent of any framework or technology.

**Responsibilities:**
- Entities (Settings, GameStats, etc.)
- Value Objects
- Interfaces and abstract classes
- Business rules

**Key principle:** No imports from other layers

---

### Application

Orchestrates the domain logic to implement use cases.

**Responsibilities:**
- Game lifecycle management
- Session orchestration
- Use case implementations
- Service layer

**Dependencies:** Domain layer only

---

### Infrastructure

Implements external integrations and data persistence.

**Responsibilities:**
- Database operations (SQLAlchemy)
- Immich API client
- Redis cache
- Repository implementations
- External service adapters

**Dependencies:** Domain, uses implementation details

---

### Presentation

Exposes the application through REST API.

**Responsibilities:**
- REST endpoints
- Request/response schemas
- HTTP middleware
- Validation

**Dependencies:** Application, Domain

---

### Games

Plugin system for game implementations.

**Responsibilities:**
- Game logic
- Scoring algorithms
- Round generation
- Answer validation

**Dependencies:** Domain, Application, Infrastructure

**Key principle:** Each game is independently pluggable
