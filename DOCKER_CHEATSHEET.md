# Docker Development Cheatsheet

## Initial Setup

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f postgres
```

## Database Migrations

```bash
# Run migrations
docker-compose exec backend python -m alembic upgrade head

# Create a new migration
docker-compose exec backend python -m alembic revision --autogenerate -m "Description"

# Downgrade one step
docker-compose exec backend python -m alembic downgrade -1

# Check current migration version
docker-compose exec backend python -m alembic current
```

## Backend Development

```bash
# Run bash in backend container
docker-compose exec backend bash

# Run tests
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov=src tests/

# Format code
docker-compose exec backend black src/

# Lint code
docker-compose exec backend ruff check src/

# Type check
docker-compose exec backend mypy src/

# Run everything
docker-compose exec backend bash -c "black src/ && ruff check src/ && mypy src/ && pytest"
```

## Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d immich_minigames

# Useful psql commands:
# \dt                - List tables
# \d table_name      - Describe table
# SELECT * FROM settings; - Query data
```

## Debugging

```bash
# View all running containers
docker-compose ps

# Inspect container
docker-compose exec backend sh

# View container logs
docker-compose logs backend

# Check health status
docker-compose exec postgres pg_isready -U postgres
docker-compose exec redis redis-cli ping
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes database)
docker-compose down -v

# Rebuild images
docker-compose build --no-cache

# Full rebuild and restart
docker-compose down && docker-compose up -d --build
```

## Ports

- Backend: http://localhost:8000 (docs: http://localhost:8000/docs)
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Environment Variables

Create `.env` file in root (or use `.env.docker`):

```
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=immich_minigames
POSTGRES_PORT=5432
REDIS_PORT=6379
DEBUG=true
BACKEND_PORT=8000
FRONTEND_PORT=3000
```
