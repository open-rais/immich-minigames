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
# Postgres instance (Immich's). Both databases below live on it.
DB_HOST=your-immich-db-host
DB_PORT=5432

# Immich's own database - this app only ever reads from it.
DB_DATABASE_NAME=immich

# Immich's admin credentials. Only the one-shot `db-init` step ever sees these;
# the long-running backend never does.
DB_USERNAME=postgres
DB_PASSWORD=your_postgres_password

# The scoped role the backend actually runs as. Created for you by `db-init`.
DB_APP_USERNAME=minigames_app
DB_APP_PASSWORD=your_minigames_app_password

# This app's own database, also created by `db-init`. Deliberately NOT a schema inside
# Immich's database: Immich's backup dumps its own database, so anything kept in there
# ends up in Immich's dumps and breaks its restore. Leave unset to accept the default.
DB_APP_DATABASE_NAME=minigames

# Immich API access (image bytes only - metadata comes from Postgres above). The key only ever
# needs read access to asset/person thumbnails - in Immich's API key permission picker, that's
# Asset (View/Download) and Person (Read); pick the read-only preset if you're unsure, this app
# never writes anything back to Immich.
IMMICH_SERVER_URL=http://your-immich-server:2283
IMMICH_API_KEY=your-immich-api-key

# Public URL the *browser* opens for the "Ver en Immich" links on the post-game rounds review
# (e.g. https://photos.example.com). Distinct from IMMICH_SERVER_URL above, which is how the
# *backend* reaches Immich and is often an address only reachable from inside your Docker network
# (like host.docker.internal) - not something a browser can open. Leave unset to fall back to
# IMMICH_SERVER_URL, which works fine if that's already a browser-reachable address; set it
# explicitly to an empty string instead (IMMICH_EXTERNAL_URL=) if you'd rather hide the "Ver en
# Immich" links entirely than have them point at an internal-only address.
IMMICH_EXTERNAL_URL=https://your-public-immich-url

# Backend configuration. JWT_SECRET is this app's real security perimeter - every route requires
# a valid session now (there is no anonymous/guest mode), so a weak or leaked secret is a full
# account-takeover risk, not just a convenience setting.
BACKEND_PORT=8000
JWT_SECRET=your-random-secret-key-32-chars
JWT_EXPIRE_DAYS=7

# Login is mandatory and registration is invite-only (see "Creating the first account" below) -
# this is what lets that very first account register without an invite from anyone. Set it to a
# random value and use it as that account's invite code on /signup; leave unset for a fully open
# first registration (fine for local/trusted dev, not recommended for anything internet-facing).
# Either way, this only ever matters until the first account exists.
INITIAL_INVITE_TOKEN=your-random-bootstrap-token

# Promotes an already-registered account to admin on every backend startup (this app's own users
# table, not Immich's) - register normally first, then set this and restart. Leave unset to not
# manage an admin.
ADMIN_EMAIL=you@example.com
```

**Tip:** Generate secure `JWT_SECRET`/`INITIAL_INVITE_TOKEN` values with:
```bash
openssl rand -hex 32
```

### 3. Set Up the Database Role and Database

Before running the app, provision the scoped Postgres role and this app's own database:

```bash
docker compose -f docker-compose.app.yml run --rm db-init
```

That one step creates (or refreshes) the `DB_APP_USERNAME` role, creates the
`DB_APP_DATABASE_NAME` database, applies this app's migrations, and — if you are upgrading from a
version that stored its tables inside Immich's database — copies that data across and cleans up
behind itself. It is safe to re-run at any time.

It also runs automatically before `backend` on `docker compose -f docker-compose.app.yml up`, so
you only need it standalone when changing `DB_APP_PASSWORD`, or after restoring an Immich backup
taken before the database split.

### 4. Run the Stack

```bash
docker compose -f docker-compose.app.yml up -d
```

The application will be available at:
- **Frontend:** http://localhost:3000 (or your configured `FRONTEND_PORT`)
- **Backend API:** http://localhost:8000/api/v1

### 5. Verify Installation

The backend requires a valid login session for almost everything (there is no anonymous/guest
mode) - a bare, unauthenticated request should get a 401, not a connection error:
```bash
curl -i http://localhost:8000/api/v1/config
```
`HTTP/1.1 401 Unauthorized` means the backend is up and reachable. Open the frontend URL above in
a browser and continue with "Creating the first account" below to actually log in.

### 6. Creating the First Account

Registration is invite-only (an admin generates further invites from the app's own Admin panel
once logged in) - except the very first account, which authenticates with `INITIAL_INVITE_TOKEN`
instead (see step 2 above). On the frontend's signup page, register using that value as the
"invite code" (if you left `INITIAL_INVITE_TOKEN` unset, the first registration needs no code at
all). This only ever matters for the very first account - the door closes itself the moment any
account exists, regardless of that setting.

To make that account an admin (so it can generate invites for everyone else, manage users, and
tune per-game settings), set `ADMIN_EMAIL` in `.env` to its email and restart the backend:
```bash
docker compose -f docker-compose.app.yml up -d --force-recreate backend
```

**Invites control *who* can log in - not *what* they can see once they're in.** Every account with
a session can see every asset/person Immich itself would show on the main timeline: content
curation is entirely Immich's own `visibility` field (an asset marked archived, in the locked
folder, or trashed in Immich is automatically excluded from every game, the same way it's excluded
from Immich's own timeline). If you're sharing this with people you don't want seeing your whole
library, curate *in Immich* (archive/lock what shouldn't be shared) before inviting them here - the
invite system has no separate, finer-grained permission of its own.

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
docker compose -f docker-compose.app.yml run --rm db-init
```

This provisions the scoped role, creates this app's own database, and applies its migrations. Doing
it by hand is not recommended — the script also handles migrating installs that predate the
separate database, and refuses to proceed in states where guessing could lose data.

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

## Upgrading

```bash
docker compose -f docker-compose.app.yml pull
docker compose -f docker-compose.app.yml up -d
```

`db-init` runs automatically before the backend on every `up`, and applies any pending database
migrations. Nothing else is normally required.

### Upgrading from a version without accounts/login

Versions before login became mandatory let anyone play anonymously, scoped to a random browser id
(`localStorage`, sent as a header). That's gone now — every route requires a real, logged-in
account, and every game/record/leaderboard entry belongs to one. Two things to know before you
pull:

- **You need at least one account before you can do anything.** Since registration is invite-only
  except the very first account, set `INITIAL_INVITE_TOKEN` in `.env` *before* upgrading (or leave
  it unset for a fully open first registration) — see "Creating the First Account" above. Without
  it, you'd have a running backend with no way to log into it.
- **Anonymous games from before this upgrade are deleted, not migrated — there's no account to
  attach them to.** This happens automatically the first time you upgrade through this point (an
  Alembic migration deletes them from this app's own database if you'd already done the database-
  split upgrade below; `db-init`'s legacy-schema copy does the same if you're upgrading from
  further back, before that split). If you want to keep a record of those scores, back up this
  app's database first:
  ```bash
  pg_dump -h <DB_HOST> -U <DB_USERNAME> -d <DB_APP_DATABASE_NAME> > minigames-backup.sql
  ```
  There is no way to recover them afterwards — they were never tied to anything that could prove
  who played them.

### Upgrading from a version that stored its tables inside Immich's database

Versions before the database split kept this app's tables in a `minigames` **schema inside Immich's
own database**. That broke Immich's backup restore (see
[ARCHITECTURE/BACKEND.md](ARCHITECTURE/BACKEND.md) § *Por qué una base de datos separada*), so they
now live in a separate database.

**The upgrade is automatic — the two commands above are all you need.** On its first run after the
upgrade, `db-init`:

1. creates this app's own database (`DB_APP_DATABASE_NAME`, default `minigames`),
2. applies the migrations to it,
3. copies every row across from the old schema,
4. verifies the row counts match,
5. and only then removes the old schema from Immich's database.

If any step doesn't add up, it stops **without deleting anything** and prints what to do. The old
data is never removed before its copy is committed and verified, so a failed upgrade always leaves
both copies intact.

Two things worth knowing afterwards:

- **Your scores and accounts are no longer in Immich's backups.** That's the point of the change,
  but it means you should back up this app's database separately if you care about them:
  ```bash
  pg_dump -h <DB_HOST> -U <DB_USERNAME> -d <DB_APP_DATABASE_NAME> > minigames-backup.sql
  ```
- **If you later restore an Immich backup taken before the split**, it will put the old schema back
  into Immich's database. It's inert, but re-run `db-init` to clean it up:
  ```bash
  docker compose -f docker-compose.app.yml run --rm db-init
  ```

You do **not** need to add `DB_APP_DATABASE_NAME` to your `.env`; leaving it unset uses `minigames`.

## Viewing the audit logs

Every account/security event (registrations, logins, password changes/resets, admin edits, rate
limiting) and every request (method, path, status, who made it) is logged as one JSON line per
event to the backend container's stdout - `docker logs` plus [`jq`](https://jqlang.org/) is enough
to query them, no separate log aggregator required (see `docs/ARCHITECTURE/BACKEND.md` § Logging
for the full design):

```bash
# Every audit event (account/security), newest last
docker logs immich-minigames-app-backend-1 | jq -c 'select(.logger == "audit")'

# Just one kind of event
docker logs immich-minigames-app-backend-1 | jq -c 'select(.logger == "audit" and .event == "login_failed")'

# Every audit event for one email
docker logs immich-minigames-app-backend-1 | jq -c 'select(.logger == "audit" and .email == "someone@example.com")'

# The full access log (one line per request) for a specific status
docker logs immich-minigames-app-backend-1 | jq -c 'select(.logger == "access" and .status == 429)'

# Everything that happened during one request, by its X-Request-Id (also returned as a response
# header - useful for correlating a user's bug report with what actually happened server-side)
docker logs immich-minigames-app-backend-1 | jq -c 'select(.request_id == "<id-from-the-header>")'
```

For the manual dev setup (`uv run uvicorn`), logs go to the terminal in a human-readable format by
default instead of JSON - set `LOG_FORMAT=json` in `.env` if you want the same `jq` recipes to work
there too.

## Common Issues & Solutions

### Issue: "Database connection refused"

**Problem:** Backend can't connect to Immich database.

**Solutions:**
- Verify `DB_HOST`, `DB_PORT`, `DB_DATABASE_NAME`, `DB_APP_DATABASE_NAME`, `DB_APP_USERNAME`,
  `DB_APP_PASSWORD` in `.env`
- Ensure Immich's Postgres container is running: `docker ps | grep postgres`
- Test connection directly:
  ```bash
  # Immich's database (read-only) and this app's own - both must answer
  psql -h <DB_HOST> -p <DB_PORT> -U <DB_APP_USERNAME> -d <DB_DATABASE_NAME> -c "SELECT 1"
  psql -h <DB_HOST> -p <DB_PORT> -U <DB_APP_USERNAME> -d <DB_APP_DATABASE_NAME> -c "SELECT 1"
  ```

### Issue: "Permission denied" on Postgres

**Problem:** The `DB_APP_USERNAME` role doesn't have permission to access Immich tables.

**Solution:** Re-run the provisioning step, which is idempotent:
```bash
docker compose -f docker-compose.app.yml run --rm db-init
```

### Issue: `db-init` fails with "Refusing to migrate ... no completed-migration marker"

**Problem:** You are upgrading from a version that stored this app's tables inside Immich's
database, but the new database already contains data and carries no record of a completed
migration. The script cannot tell a half-finished migration from an install that wrote its own
data, and either guess could destroy something — so it stops and changes nothing.

Note that while it stops, the backend will not start: it waits for `db-init` to succeed.

**Solution:** Decide which copy is authoritative. The error message prints the row counts of both.
Then either drop the old schema from Immich's database:
```bash
psql -h <DB_HOST> -U <DB_USERNAME> -d <DB_DATABASE_NAME> -c "DROP SCHEMA minigames CASCADE"
```
or empty the new database so the copy can proceed, and re-run `db-init`.

### Issue: I restored an Immich backup and the old schema is back

**Problem:** A backup taken before the database split still contains this app's old `minigames`
schema, so restoring it puts that schema back into Immich's database. It's inert — the app reads
and writes only its own database — but it will ride along in future Immich backups and can break a
future restore.

**Solution:** Re-run `db-init`. It recognises the resurrected schema, does **not** re-import its
(stale) rows, and cleans it up:
```bash
docker compose -f docker-compose.app.yml run --rm db-init
```

### Issue: "401 Unauthorized" when fetching thumbnails

**Problem:** Immich API key is missing or incorrect.

**Solutions:**
- Verify `IMMICH_API_KEY` in `.env` matches what you copied from Immich
- Generate a new API key in Immich (Account Settings → API Keys)
- Ensure `IMMICH_SERVER_URL` is reachable from your container
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
- Test from inside the frontend container (a 401 is fine here — it means the backend answered;
  a connection error/timeout is the actual problem):
  ```bash
  docker exec <frontend-container> curl -i http://backend:8000/api/v1/config
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
- Every game/menu route requires being logged in - if you're not seeing games, first make sure
  you're actually logged in (not stuck on a login/signup screen), then check the browser's Network
  tab (F12) for the actual failing request/response instead of curling game endpoints directly
  (they all need the session cookie a browser carries automatically, which a bare `curl` won't
  have)
- Check frontend console for errors (F12 → Console tab)

### Issue: "Immich-ML not reachable"

**Problem:** Backend can't connect to Immich-ML service.

**Context:** Immichdle and Who'sThatPerson rely on face embeddings from Immich-ML. Other games don't use it.

**Solutions:**
- Face embeddings are read from Immich's Postgres (`face_search`), not by calling Immich-ML
  directly, so there is no ML URL to configure - check that Immich has actually run face
  recognition on your library:
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
IMMICH_SERVER_URL=https://immich.example.com
IMMICH_API_KEY=<your-api-key>
```

**Note:** The ML URL might vary depending on your Immich setup. Check your Immich instance's documentation.

If `IMMICH_SERVER_URL` above is itself a browser-reachable address (as in this example), the "Ver en
Immich" links on the rounds review screen work with no further configuration. If instead your backend
reaches Immich through an address a browser can't open (e.g. `host.docker.internal` when both stacks
run on the same machine, as in the default `docker-compose.app.yml` setup), set `IMMICH_EXTERNAL_URL`
to the public URL separately - see the `.env` example above.

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
2. Set `COOKIE_SECURE=true` in `.env` (requires HTTPS - marks the session cookie `Secure`-only, so
   it stops going out over plain HTTP)
3. Update `IMMICH_SERVER_URL` to use `https://`
4. Use proper certificate management (Let's Encrypt, etc.)
5. If you run more than one backend container/process behind that proxy, point
   `RATE_LIMIT_STORAGE_URI` at a shared Redis instance (`redis://host:port`) instead of the
   default `memory://` - otherwise each process enforces its own separate rate limit budget

## Verification Checklist

After installation, verify:

- [ ] Backend is running: `curl -i http://localhost:8000/api/v1/config` returns `401` (not a
      connection error - every route requires a session, so `401` means it's up and reachable)
- [ ] Frontend loads: open `http://localhost:${FRONTEND_PORT:-3000}` (Docker) or
      `http://localhost:5173` (manual dev)
- [ ] Database role exists: run a test query
- [ ] Can register the first account (see "Creating the First Account") and log in
- [ ] Immich API key works: at least one game shows real photos/people, not broken thumbnails
- [ ] Can create a game and play a round

## Getting Help

- Check `docs/TODO/DEV_NOTES.md` for development tips
- Review `docs/ARCHITECTURE/` for technical details
- Check the GitHub issues: https://github.com/open-rais/immich-minigames/issues
- Review the main `README.md` for project overview
