# Installation Guide

This guide covers different ways to install and run Immich Minigames.

## Prerequisites

Before you start, make sure you have:

1. **An existing Immich instance** running (v1.90.0+) with:
   - Postgres database
   - Immich-ML service
   - An API key (created in Immich's Account Settings → API Keys)

2. For **Docker deployment**:
   - Docker and Docker Compose installed

3. For **manual development setup**:
   - Python 3.12+
   - Node.js 18+ and npm
   - `uv` package manager for Python
   - Git

## Option 1: Docker Compose (Recommended for Production/Testing)

The easiest way to deploy Immich Minigames alongside an existing Immich instance.

### 1. Clone the Repository

```bash
git clone https://github.com/open-rais/immich-minigames
cd immich-minigames
```

### 2. Configure Environment Variables

Create a `.env` file in the repository root with your Immich credentials:

```env
# Immich database connection
DB_HOST=your-immich-db-host
DB_PORT=5432
DB_NAME=immich
DB_APP_USERNAME=immich_app
DB_APP_PASSWORD=your_immich_app_password

# Immich API access
IMMICH_API_URL=http://your-immich-server/api
IMMICH_API_KEY=your-immich-api-key
IMMICH_ML_URL=http://your-immich-ml-service:3003

# Backend configuration
BACKEND_PORT=8000
JWT_SECRET=your-random-secret-key-32-chars
JWT_EXPIRE_DAYS=7
```

**Tip:** Generate a secure `JWT_SECRET` with:
```bash
openssl rand -hex 32
```

### 3. Set Up the Database Role

Before running the app, create the Immich app role with proper permissions:

```bash
# Start the Immich database (if not already running)
docker compose -f docker-compose.yml up -d

# Create the minigames app role
docker exec <immich-postgres-container-name> bash /docker-entrypoint-initdb.d/create_minigames_app_role.sh
```

**Find the container name:**
```bash
docker ps | grep postgres
```

### 4. Run the Stack

```bash
docker compose -f docker-compose.app.yml up -d
```

The application will be available at:
- **Frontend:** http://localhost:5173 (or configured FRONTEND_PORT)
- **Backend API:** http://localhost:8000/api/v1

### 5. Verify Installation

Test the connection:
```bash
curl http://localhost:8000/api/v1/games
```

You should get an empty JSON response or a list of games if any exist.

## Option 2: Development Setup (Manual)

For local development or custom deployments.

### 1. Clone the Repository

```bash
git clone https://github.com/open-rais/immich-minigames
cd immich-minigames
```

### 2. Create `.env` File

Same as above (Option 1, step 2).

### 3. Start Immich (if not already running)

```bash
docker compose up -d
```

This starts Immich locally with a test database and Immich-ML service.

### 4. Set Up the Database Role

```bash
docker exec immich-minigames-postgres-1 bash -c "psql -U postgres -d immich -f /docker-entrypoint-initdb.d/create_minigames_app_role.sh"
```

Or create the role manually:
```bash
docker exec -it immich-minigames-postgres-1 psql -U postgres -d immich -c "
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO immich_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO immich_app;
CREATE SCHEMA IF NOT EXISTS minigames AUTHORIZATION immich_app;
"
```

### 5. Start the Backend

```bash
cd backend
uv sync  # Install dependencies
uv run alembic upgrade head  # Apply database migrations
uv run uvicorn main:app --app-dir src --port 8000 --reload
```

The backend will be available at `http://localhost:8000/api/v1`.

### 6. Start the Frontend (in another terminal)

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

### 7. Access the App

Open http://localhost:5173 in your browser. The frontend's dev server proxies API calls to the backend automatically.

## Common Issues & Solutions

### Issue: "Database connection refused"

**Problem:** Backend can't connect to Immich database.

**Solutions:**
- Verify `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_APP_USERNAME`, `DB_APP_PASSWORD` in `.env`
- Ensure Immich's Postgres container is running: `docker ps | grep postgres`
- Test connection directly:
  ```bash
  psql -h <DB_HOST> -p <DB_PORT> -U <DB_APP_USERNAME> -d <DB_NAME> -c "SELECT 1"
  ```

### Issue: "Permission denied" on Postgres

**Problem:** The `immich_app` role doesn't have permission to access Immich tables.

**Solution:** Re-run the role setup script:
```bash
docker exec immich-minigames-postgres-1 bash /docker-entrypoint-initdb.d/create_minigames_app_role.sh
```

### Issue: "401 Unauthorized" when fetching thumbnails

**Problem:** Immich API key is missing or incorrect.

**Solutions:**
- Verify `IMMICH_API_KEY` in `.env` matches what you copied from Immich
- Generate a new API key in Immich (Account Settings → API Keys)
- Ensure `IMMICH_API_URL` is reachable from your container
- For Docker: if using `host.docker.internal`, ensure it's accessible

### Issue: Frontend shows 404 for API calls

**Problem:** Frontend can't reach the backend API.

**Solutions for development:**
- Verify backend is running on the correct port (default 8000)
- Check that Vite's proxy config points to the right address in `vite.config.ts`
- In browser console, check what URL is being requested (should be relative `/api/v1/...`)

**Solutions for Docker:**
- Ensure nginx proxy is configured correctly
- Check backend and frontend are on the same Docker network
- Test from inside the frontend container:
  ```bash
  docker exec <frontend-container> curl http://backend:8000/api/v1/games
  ```

### Issue: Backend crashes on startup with "table already exists"

**Problem:** Database migration conflicts (usually after Alembic was added).

**Solution:** The baseline migration is designed to be idempotent. Try:
```bash
cd backend
uv run alembic upgrade head
```

If the issue persists:
```bash
cd backend
uv run alembic downgrade -1
uv run alembic upgrade head
```

### Issue: No games appear in the menu

**Problem:** Likely a code issue or misconfiguration.

**Solutions:**
- Check backend logs for errors
- Verify database migrations ran: `uv run alembic current`
- Test the API directly:
  ```bash
  curl http://localhost:8000/api/v1/games
  ```
- Check frontend console for errors (F12 → Console tab)

### Issue: "Immich-ML not reachable"

**Problem:** Backend can't connect to Immich-ML service.

**Context:** Immichdle and Who'sThatPerson rely on face embeddings from Immich-ML. Other games don't use it.

**Solutions:**
- Verify `IMMICH_ML_URL` in `.env`
- For Docker: use the service name (e.g., `http://immich-ml:3003`)
- For local Immich stack: check that the ML service is running:
  ```bash
  docker ps | grep immich-ml
  ```
- This doesn't block other games, only Immichdle/Who'sThatPerson

### Issue: "Language selector not working" or only showing one language

**Problem:** Stale browser cache.

**Solution:**
- Clear browser cache and reload: `Ctrl+Shift+Delete` (or `Cmd+Shift+Delete` on Mac)
- Or do a hard refresh: `Ctrl+F5`

### Issue: Docker image pull fails or image not found

**Problem:** GitHub Container Registry image isn't available or credentials are wrong.

**Solutions:**
- Check your GitHub token has `read:packages` permission
- Verify the image name in `docker-compose.app.yml`
- Try pulling manually:
  ```bash
  docker pull ghcr.io/open-rais/immich-minigames-backend:latest
  ```
- If pulling fails, build locally instead:
  ```bash
  docker build -t immich-minigames-backend:local backend/
  ```

## Advanced Configuration

### Using a Remote Immich Instance

Point to an existing Immich instance on another machine:

```env
DB_HOST=immich.example.com
DB_PORT=5432
IMMICH_API_URL=https://immich.example.com/api
IMMICH_API_KEY=<your-api-key>
IMMICH_ML_URL=https://immich.example.com/api/ml
```

**Note:** The ML URL might vary depending on your Immich setup. Check your Immich instance's documentation.

### Custom Ports

Change ports in `.env`:

```env
BACKEND_PORT=3000  # Use port 3000 for backend
FRONTEND_PORT=3001 # Use port 3001 for frontend
```

Then update `docker-compose.app.yml` or run commands accordingly.

### SSL/TLS in Production

For production deployments:

1. Use a reverse proxy (nginx, Traefik)
2. Set `Secure=True` in the JWT cookie config (requires HTTPS)
3. Update `IMMICH_API_URL` to use `https://`
4. Use proper certificate management (Let's Encrypt, etc.)

## Verification Checklist

After installation, verify:

- [ ] Backend is running: `curl http://localhost:8000/api/v1/games`
- [ ] Frontend loads: open http://localhost:5173
- [ ] Database role exists: run a test query
- [ ] Immich API key works: try logging in
- [ ] At least one game loads without errors
- [ ] Can create a game and play a round

## Getting Help

- Check `docs/TODO/DEV_NOTES.md` for development tips
- Review `docs/ARCHITECTURE/` for technical details
- Check the GitHub issues: https://github.com/open-rais/immich-minigames/issues
- Review the main `README.md` for project overview
