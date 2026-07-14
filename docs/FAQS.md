# Frequently Asked Questions

## General

### Is this an official Immich project?

No, this is an unofficial community project with no affiliation with the Immich team. It's a standalone
companion app designed to work alongside your Immich instance.

### Will this modify or copy my photos?

No. This app:
- Reads metadata from Immich's database (people, albums, locations, dates)
- Fetches image thumbnails only through Immich's REST API (never directly from disk)
- Never modifies, copies, or stores photos
- Never creates a separate copy of your photo library

### Why does this app need direct database access? Why not just use the Immich REST API?

Immich's public REST API doesn't expose all the metadata needed for games:
- Face similarity scores (computed by Immich-ML) aren't available via the API
- Precise location coordinates aren't exposed through the API
- Efficient queries for comparative metadata (e.g., "people with more assets than X") require direct database access
- The API lacks batch query capabilities needed for game performance

Direct read-only access lets us query this data efficiently without duplicating it.

### Is it safe to run this alongside Immich?

**Use at your own risk.** Safety measures in place:
- The database user (`DB_APP_USERNAME`) is read-only on Immich's `public` schema
- Only the app's own `minigames` schema (owned by that role) can be modified
- Image files are never touched—thumbnails come only via the REST API
- All direct database access is read-only except for the app's own game tables

That said, you're running code with direct access to your personal photo database. Review the source code
if you have concerns. The author takes no responsibility for any issues that arise.

## Installation & Deployment

### What are the system requirements?

- **Immich instance:** v1.90.0 or later with Postgres and Immich-ML running
- **For Docker:** Docker and Docker Compose
- **For local development:** Python 3.11+ (backend), Node.js 18+ (frontend), uv package manager

### How do I set this up?

See the Installation & Usage section in the README.md for:
- Docker Compose setup (recommended)
- Development setup (running backend + frontend locally)

### Can I run this on a different machine from Immich?

Yes. You need:
- Network access to your Immich database (Postgres on the network)
- Network access to your Immich API server (HTTP/HTTPS)
- Network access to Immich-ML service (if using clues that depend on face similarity)

Set `DB_HOST`, `IMMICH_API_URL`, and `IMMICH_ML_URL` in your `.env` accordingly.

### How do I configure environment variables?

Create a `.env` file in the project root. Required variables:
```env
DB_HOST=<postgres-host>
DB_PORT=5432
DB_NAME=immich
DB_APP_USERNAME=immich_app
DB_APP_PASSWORD=<password-from-immich-docker-compose>
IMMICH_API_URL=http://<immich-server>/api
IMMICH_ML_URL=http://<immich-ml-service>:3003
BACKEND_PORT=8000
```

## Games & Features

### Which games are playable right now?

✓ **Fully playable:**
- **MoreOrLess:** Guess if person B has more/fewer photos than person A
- **Geoguessr:** Guess where on a map a photo was taken
- **Dateguessr:** Guess when on a timeline a photo was taken

✗ **Design stubs (not yet implemented):**
- **Immichdle:** Guess a mystery person with comparative clues
- **Timeline:** Place photos in correct chronological order
- **Who'sThatPerson:** Guess who the person is when their face is hidden

### What features are available?

✓ User login (register, sign in, logout, profile page)
✓ Dark theme (consistent with Immich colors)
✓ Full Spanish translation (i18n-ready, English + Spanish)
✓ Docker images (GHCR registry)

✗ **Planned features:**
- Daily challenges (same seed per user, play once per day)
- Leaderboards (global and user-specific)
- Report incorrect metadata
- Metadata repair tools
- Additional game modes (for example: MoreOrLess comparing album counts)

### How do I contribute a new game?

Games are modules in `backend/src/games/` that inherit from `BaseGame` and `BaseRound`. Each game
defines:
- `has_next_round()`: when does the game end?
- `calculate_score()`: how many points is a guess worth?

See `games/base.py` for the contract and `games/more_or_less.py` for a complete example. The design
for each planned game is in `docs/GAMES/<Game>.md`.

## Data & Metadata

### How much metadata do I need for games to work well?

Games work with whatever metadata you have, but quality depends on completeness:
- **Names:** MoreOrLess, Immichdle, Who'sThatPerson work best with named people
- **Locations:** Geoguessr needs photo locations; if missing, those photos won't be picked
- **Dates:** Dateguessr and Timeline need photo dates
- **Birthdays:** Future MoreOrLess mode (person-birth-date) needs birthday data

The better your Immich library is organized, the better the games.

### Will bad metadata break the games?

No. The app gracefully handles missing data:
- Missing locations? Geoguessr skips those photos
- Unnamed people? They're excluded from person-focused games
- No birthdays? Birthday-based modes will fail gracefully when implemented

You can also exclude people or assets from games in future versions (planned feature).

### Can I report metadata errors?

Not yet. This is a planned feature (roadmap item). For now, report errors in Immich itself.

## Development

### How do I run the dev servers?

**Backend:**
```bash
cd backend
uv run uvicorn main:app --app-dir src --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Both need Immich running with the database accessible.

### How do I run tests?

**Backend:**
```bash
cd backend
uv run pytest
```

### What stack does this use?

**Backend:**
- FastAPI (REST API)
- SQLAlchemy (ORM)
- Pytest (testing)
- httpx (HTTP client for Immich API)
- Managed with `uv`

**Frontend:**
- React 19
- Vite (bundler)
- TypeScript
- Tailwind 4 (CSS)
- react-i18next (translations)
- Managed with `npm`

**Infrastructure:**
- Postgres (Immich's database)
- Immich-ML (face similarity scores)
- Docker & Docker Compose

### Where should I look to understand the architecture?

- **Architecture overview:** `docs/ARCHITECTURE/IMMICH.md` (database schema, Immich integration)
- **Game design:** `docs/GAMES/OVERVIEW.md` (shared game contract)
- **Backend structure:** `backend/src/` (layered architecture: API, services, domain, persistence, games)
- **Frontend structure:** `frontend/src/` (per-game components, shared utilities)
- **Build order:** `docs/TODO/ROADMAP.md` (planned implementation sequence)

### Can I use this as a reference for my own Immich project?

Yes. The codebase demonstrates:
- Direct Postgres access patterns for Immich data
- Integration with Immich's REST API
- Face similarity queries via Immich-ML
- React patterns for games/interactive apps
- Tailwind + TypeScript best practices
- FastAPI with SQLAlchemy

Feel free to reference or adapt patterns for your own projects.

## Troubleshooting

### The app can't connect to the database

Check:
- `DB_HOST`, `DB_PORT`, `DB_NAME` are correct
- `DB_APP_USERNAME` and `DB_APP_PASSWORD` match your Immich setup
- Network connectivity to the database
- Firewall isn't blocking the connection

The database user must have read access to Immich's `public` schema.

### Games say "no photos available"

Likely causes:
- No photos with the required metadata (e.g., location for Geoguessr)
- The library is very small (< 10 people or photos)
- Metadata is incomplete (people unnamed, locations missing, etc.)

Check your Immich library for the required metadata for each game.

### The frontend shows "Unable to connect to API"

Check:
- `IMMICH_API_URL` is correct and the Immich server is running
- Backend is running and listening on the correct port
- Network connectivity between frontend and backend
- Frontend is making requests to the correct backend URL

### Face similarity queries are slow

Immich-ML computations can be expensive. If Immichdle feels slow:
- This is expected the first time each query runs
- Immich caches face embeddings, so subsequent queries are faster
- Consider running Immich-ML on a separate machine for performance

## Support & Community

### Where do I report bugs?

Open an issue on the [GitHub repository](https://github.com/open-rais/immich-minigames).

### Can I contribute?

Yes. The codebase is open source. For significant features, consider opening an issue first to discuss
your idea. See the ROADMAP for the intended build order.

### Is there a roadmap?

Yes, in `docs/TODO/ROADMAP.md`. It covers planned games, features, and approximate priority order.
