# Docker Setup Guide

This guide explains how to run the entire Immich Minigames application using Docker and Docker Compose.

## Prerequisites

- Docker (20.10+)
- Docker Compose (2.0+)
- Git

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/immich-minigames.git
cd immich-minigames
```

### 2. Prepare environment variables

Copy the Docker environment file:

```bash
cp .env.docker .env.docker.local
```

Edit `.env.docker.local` if needed (optional - defaults are fine for local development):

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=immich_minigames
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Backend
DEBUG=true
BACKEND_PORT=8000

# Frontend
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Build and start services

```bash
# Using .env.docker.local file:
docker compose --env-file .env.docker.local up -d

# Or using default .env.docker:
docker compose up -d
```

### 4. Wait for services to be ready

The application uses health checks. Wait for all services to be healthy:

```bash
docker compose ps
```

You should see:
- `postgres` - healthy
- `redis` - healthy  
- `backend` - healthy/running
- `frontend` - healthy/running

### 5. Access the application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs (Swagger UI)
- **Database**: localhost:5432 (PostgreSQL)
- **Cache**: localhost:6379 (Redis)

## Configuration

### Environment Variables

Create a `.env.docker.local` file with your settings:

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=immich_minigames

# Backend
DEBUG=false  # Set to false in production
BACKEND_PORT=8000

# Frontend
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8000  # API URL for frontend
```

For production deployments, update `NEXT_PUBLIC_API_URL` to your actual backend URL.

## Common Commands

### Start all services

```bash
docker compose up -d
```

### Stop all services

```bash
docker compose down
```

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres

# Last 100 lines
docker compose logs --tail=100
```

### Rebuild images

```bash
docker compose build --no-cache
```

### Access database

```bash
docker compose exec postgres psql -U postgres -d immich_minigames
```

### Access Redis

```bash
docker compose exec redis redis-cli
```

## Development Mode

For development with hot-reload on the frontend:

### Option 1: Using development override

Create a `docker-compose.dev.yml`:

```yaml
version: "3.8"
services:
  frontend:
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    command: npm run dev
```

Run with:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Option 2: Run frontend locally

```bash
# Terminal 1: Run Docker services (without frontend)
docker compose up -d postgres redis backend

# Terminal 2: Run frontend locally
cd frontend
npm install
npm run dev
```

Then edit `.env.local` to point to the backend:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Troubleshooting

### Services won't start

Check logs for specific errors:

```bash
docker compose logs backend
docker compose logs frontend
docker compose logs postgres
```

### Database connection error

Wait a moment for PostgreSQL to fully initialize:

```bash
docker compose logs postgres
```

Ensure the DATABASE_URL is correct in the backend environment.

### Frontend can't connect to backend

Verify the API URL in the frontend environment:

```bash
docker compose logs frontend | grep "API_URL"
```

If using the override method, ensure `NEXT_PUBLIC_API_URL=http://localhost:8000` points to the backend.

### Port already in use

Change the ports in `.env.docker.local`:

```env
POSTGRES_PORT=5433        # Instead of 5432
REDIS_PORT=6380           # Instead of 6379
BACKEND_PORT=8001         # Instead of 8000
FRONTEND_PORT=3001        # Instead of 3000
```

Then update `NEXT_PUBLIC_API_URL` accordingly.

### Container disk space

Clean up unused Docker resources:

```bash
docker system prune -a
```

## Production Deployment

### 1. Build for production

```bash
docker compose build --no-cache
```

### 2. Use production env file

```bash
docker compose --env-file .env.production up -d
```

### 3. Use reverse proxy (nginx, Caddy, etc)

Example nginx configuration:

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name immich-minigames.example.com;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 4. Database backups

Backup PostgreSQL:

```bash
docker compose exec postgres pg_dump -U postgres immich_minigames > backup.sql
```

Restore from backup:

```bash
docker compose exec -T postgres psql -U postgres immich_minigames < backup.sql
```

## Architecture

```
┌─────────────────────────────────────────────┐
│          Docker Network (bridge)            │
├─────────────────────────────────────────────┤
│                                             │
│  Frontend (Next.js)     Backend (FastAPI)   │
│  Port: 3000             Port: 8000          │
│                         │                   │
│  ↓ (HTTP requests)      ↓ (HTTP)            │
│  ┌──────────────────────┴──────────────────┐│
│  │      PostgreSQL (5432)  Redis (6379)    ││
│  │      (Database)          (Cache)        ││
│  └─────────────────────────────────────────┘│
│                                             │
└─────────────────────────────────────────────┘
```

## Performance Tips

1. **Use volume mounts strategically** - Only mount source files, not node_modules
2. **Use .dockerignore** - Exclude unnecessary files from build context
3. **Multi-stage builds** - Frontend uses multi-stage for smaller images
4. **Health checks** - Services wait for dependencies to be ready
5. **Resource limits** - Consider adding memory/CPU limits in production

## References

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Next.js Docker Guide](https://nextjs.org/docs/deployment/docker)
- [FastAPI Docker Guide](https://fastapi.tiangolo.com/deployment/docker/)

## Support

For issues related to Docker setup, check:

1. Docker Compose logs: `docker compose logs`
2. Service health: `docker compose ps`
3. Network connectivity: `docker compose exec [service] ping [other-service]`
