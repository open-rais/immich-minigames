# Technology Stack

## Backend

- **Python** 3.12+
- **FastAPI** - REST framework
- **SQLAlchemy** - ORM for database operations
- **Alembic** - Database migrations
- **Pydantic** - Data validation and serialization
- **Asyncio** - Async runtime
- **Httpx** - Async HTTP client for Immich API

---

## Frontend

- **Next.js** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling

---

## Database

**PostgreSQL** - Persistent storage

Used for:
- Settings (Immich connection details)
- Game statistics (high scores)

---

## Cache

**Redis** - In-memory data store

Used for:
- Active game sessions
- Immich data cache (optional)

---

## Deployment

- **Docker** - Container runtime
- **Docker Compose** - Multi-container orchestration

---

## Testing

- **Pytest** - Python testing framework
- **pytest-asyncio** - Async test support
- **Playwright** - E2E testing (optional)

---

## Development Tools

### Code Quality

- **Black** - Code formatter
- **Ruff** - Linter
- **Mypy** - Static type checker
- **isort** - Import organizer

### Repository Standards

- **Git** - Version control
- **pre-commit** - Git hooks automation
- **Conventional Commits** - Commit message standards

---

## Stack Rationale

### Why Python + FastAPI?

- Modern async support
- Strong type hints with Pydantic
- Excellent REST framework
- Great for API-first development
- Easy to onboard contributors

### Why Next.js?

- Full-stack framework reduces complexity
- App Router for cleaner structure
- Built-in API routes
- Server components for performance
- TypeScript first-class support

### Why PostgreSQL + Redis?

- PostgreSQL: ACID compliance, proven at scale
- Redis: Fast session/cache storage
- Both easily Docker deployable
- Industry-standard for self-hosted solutions

### Why Docker?

- "Single command deployment" philosophy
- Consistent across environments
- Self-hosters expect containerized apps
- Easy integration with home labs
