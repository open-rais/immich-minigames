# Deployment Strategy

## Deployment Goal

Single command deployment.

```bash
docker compose up -d
```

Users should be able to deploy immich-minigames with minimal configuration.

---

## Deployment Architecture

### Components

```
Client Browser
    ↓
Frontend (Next.js)
    ↓ HTTP
API Gateway / Reverse Proxy
    ↓
Backend (FastAPI)
    ↓
PostgreSQL Database
Cache (Redis)
Immich (External)
```

### Docker Services

```yaml
services:
  frontend:        # Next.js app
  backend:         # FastAPI server
  postgres:        # Database
  redis:           # Cache
```

---

## Configuration

### Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `APP_DEBUG` - Debug mode (true/false)
- `APP_HOST` - Server host (0.0.0.0)
- `APP_PORT` - Server port (8000)

User-provided (via UI):
- `IMMICH_URL` - Immich instance URL
- `IMMICH_API_KEY` - Immich API token

### Docker Compose Defaults

- Backend: `localhost:8000`
- Frontend: `localhost:3000`
- Database: PostgreSQL 15
- Cache: Redis latest

---

## Success Criteria

MVP deployment is successful when:

✅ User can start services with `docker compose up -d`  
✅ Frontend loads at `localhost:3000`  
✅ User can connect to their Immich instance  
✅ User can play MoreOrLess game  
✅ Scores are tracked and persisted  
✅ Architecture supports adding new games  
✅ Codebase is ready for community contributions

---

## Database Initialization

### Migrations

Alembic handles schema creation:

```bash
alembic upgrade head
```

**Automatic on startup** (if configured):
- Check pending migrations
- Run migrations
- Log results

### Initial Data

- No seed data required
- Settings created on first Immich connection
- GameStats created on first game completion

---

## Non-Goals

The project explicitly does **not**:

- Replace Immich
- Modify Immich or its data
- Store or copy photos
- Sync photos
- *Edit metadata* (Can be marked incorrect via future report system)

---

## Self-Hosted First

The deployment is designed for self-hosted environments:

✅ Local network deployment  
✅ No external dependencies (except PostgreSQL/Redis/Immich)  
✅ No cloud services required  
✅ Data stays local  
✅ Works offline after initialization  
✅ One server setup (no scaling complexity)  

---

## Future Scaling (Not in Scope)

If the project grows:

- Separate frontend and backend services
- Kubernetes support
- Load balancing
- Session clustering
- Database replication
- CDN for static assets

For now: **single machine, modular monolith**.
