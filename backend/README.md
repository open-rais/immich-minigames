# Backend Development Guide

This directory contains the FastAPI backend for immich-minigames.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [API Documentation](#api-documentation)

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis
- Make (optional)

### Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (with dev tools)
pip install -e ".[dev]"
# OR with uv (faster):
uv sync
```

### Configure Environment

```bash
# Copy example environment
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required variables:**
- `DATABASE_URL` — PostgreSQL connection (default: `postgresql://postgres:postgres@localhost:5432/immich_minigames`)
- `REDIS_URL` — Redis connection (default: `redis://localhost:6379/0`)
- `DEBUG` — Enable debug mode (default: `true`)

### Initialize Database

```bash
# Run migrations
alembic upgrade head
```

### Run Development Server

```bash
# Server starts at http://localhost:8000
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs (Swagger UI)

---

## Project Structure

```
src/
├── domain/                   # Business logic (pure, framework-independent)
│   ├── entities/            # Data classes and value objects
│   └── repositories/        # Repository interfaces
├── application/             # Use cases and orchestration
├── infrastructure/          # External integrations
│   ├── db/                 # Database setup and models
│   │   ├── database.py     # SQLAlchemy engine/session
│   │   ├── models/         # ORM models
│   │   └── repositories/   # Repository implementations
│   └── immich/             # Immich API integration
├── presentation/            # REST API
│   └── api/                # Endpoint routers
├── games/                   # Game plugins
├── core/                    # Shared constants and utilities
├── config.py               # Settings management
└── main.py                 # FastAPI application

tests/
├── unit/                    # Unit tests
└── integration/             # Integration tests

alembic/                      # Database migrations
└── versions/                # Migration files
```

### Layer Responsibilities

**Domain:** Pure business logic, no framework dependencies
- Entities (Settings, GameStats)
- Interfaces and abstract classes

**Application:** Use cases, orchestration
- Service classes
- Game lifecycle management

**Infrastructure:** External integrations
- Database access (SQLAlchemy)
- Immich API client
- Repository implementations

**Presentation:** REST API
- Route handlers
- Request/response schemas
- Input validation

**Games:** Plugin system
- GamePlugin interface implementations
- Game-specific logic

---

## Development Workflow

### Code Quality

All code must pass quality checks before commit:

```bash
# Format code
black src/

# Organize imports
python -m isort src/

# Lint
ruff check src/

# Type check
mypy src/

# Run all checks
black src/ && python -m isort src/ && ruff check src/ && mypy src/
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/unit/test_settings.py

# With coverage report
pytest --cov=src tests/

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Debugging

```bash
# Run with debugging
python -m pdb -c continue src/main.py
```

---

## Database Migrations

### Creating a Migration

1. **Modify models** in `src/infrastructure/db/models/`
2. **Generate migration**:

```bash
alembic revision --autogenerate -m "descriptive message"
```

3. **Review generated migration** in `alembic/versions/`
4. **Test locally**:

```bash
alembic upgrade head
# Test your changes
alembic downgrade -1
```

### Running Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade 001_initial

# Check current version
alembic current

# Show migration history
alembic history
```

### Writing Migrations Manually

If auto-generation doesn't work:

```python
# alembic/versions/XXX_description.py

def upgrade() -> None:
    op.create_table(
        'my_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

def downgrade() -> None:
    op.drop_table('my_table')
```

---

## Testing

### Writing Tests

**Unit tests** — Test functions in isolation:

```python
# tests/unit/test_settings_repository.py
import pytest
from src.infrastructure.repositories.settings_repository import SettingsRepositoryImpl

@pytest.mark.asyncio
async def test_get_setting():
    repo = SettingsRepositoryImpl(session)
    value = await repo.get("immich_url")
    assert value is not None
```

**Integration tests** — Test across layers:

```python
# tests/integration/test_settings_api.py
@pytest.mark.asyncio
async def test_settings_endpoint():
    client = TestClient(app)
    response = client.get("/api/settings")
    assert response.status_code == 200
    assert "immich_url" in response.json()
```

### Test Fixtures

Common fixtures in `tests/conftest.py`:

```python
@pytest.fixture
async def db_session():
    # Provide test database session
    pass

@pytest.fixture
def test_client():
    # Provide FastAPI test client
    pass
```

### Coverage Requirements

- Minimum **80%** coverage for new code
- Run: `pytest --cov=src tests/`

---

## Configuration

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBUG` | `true` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |
| `DATABASE_URL` | - | PostgreSQL connection string |
| `REDIS_URL` | - | Redis connection string |

### Config File

Settings are loaded from `.env` using Pydantic:

```python
from src.config import settings

url = settings.database_url
debug = settings.debug
```

---

## API Documentation

### Automatic Docs

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### API Routes

See [API Design Documentation](../docs/05-technical/api-design.md) for complete endpoint reference.

**Key endpoints:**
- `GET /api/settings` — Get current settings
- `PUT /api/settings` — Update settings
- `POST /api/settings/test-connection` — Test Immich connection
- `GET /api/games` — List available games
- `POST /api/sessions/start` — Start a game

---

## Common Tasks

### Run Linting

```bash
ruff check src/ --fix
```

### Format Code

```bash
black src/
python -m isort src/
```

### Type Check

```bash
mypy src/
```

### Full Quality Check

```bash
black src/ && python -m isort src/ && ruff check src/ && mypy src/
```

### Run All Tests

```bash
pytest --cov=src tests/
```

### Start Fresh

```bash
# Drop all tables
alembic downgrade base

# Recreate schema
alembic upgrade head

# Run tests
pytest
```

---

## Troubleshooting

### Database Connection Failed

```
postgresql://postgres:postgres@localhost:5432/immich_minigames
```

Make sure PostgreSQL is running:
```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql

# Docker
docker run -d -e POSTGRES_PASSWORD=postgres postgres:15
```

### Redis Connection Failed

```
redis://localhost:6379/0
```

Make sure Redis is running:
```bash
# macOS
brew services start redis

# Linux
sudo systemctl start redis-server

# Docker
docker run -d redis:latest
```

### Port Already in Use

```bash
# Change port in command
uvicorn src.main:app --reload --port 8001
```

### Import Errors

```bash
# Reinstall dependencies
pip install -e ".[dev]" --force-reinstall
```

---

## Architecture References

- [Backend Architecture](../docs/04-architecture/backend-architecture.md) — Layer design
- [Domain Model](../docs/04-architecture/domain-model.md) — Data structures
- [Design Patterns](../docs/04-architecture/design-patterns.md) — Implementation patterns
- [Development Standards](../docs/05-technical/development-standards.md) — Code quality

---

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

---

Need help? Check the [main documentation](../docs/) or open an issue.
