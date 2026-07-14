<p align="center"><img src="frontend/public/logo.svg" alt="" width="140" height="140" /></p>

# Immich Minigames

Memory minigames powered by the metadata already in your [Immich](https://immich.app) library.

No generic questions: every game is about your people, your travels, your photos.
How many photos does that person have? Where was this taken? Whose face is hidden?

> Unofficial project, unaffiliated with the Immich team. Runs alongside an existing Immich instance,
> reusing its database and Immich-ML service—no separate copy of your photos is stored.

## Why?

Just why not? It's entertaining, and it rewards keeping your metadata organized. The better
labeled your library is (names, birthdays, locations), the better and more varied the games. A nice incentive
to keep your photo metadata up to date.

## The Games

| Game | Inspired by | The idea |
|---|---|---|
| **MoreOrLess** | The classic [More Or Less](https://moreorless.io/) | Does person B have more or fewer photos than person A? |
| **Geoguessr** | [GeoGuessr](https://www.geoguessr.com/) | Guess on a map where a photo was taken |
| **Dateguessr** | Geoguessr, but with dates | Guess on a timeline when a photo was taken |
| **Immichdle** | Wordle-style games ([Wordle](https://www.nytimes.com/games/wordle/)) | Guess the mystery person with comparative clues |
| **Timeline** | The board game [Timeline](https://www.zygomatic-games.com/en/game/timeline-classic/) | Place photos in chronological order |
| **Who'sThatPerson** | ["Who's That Pokémon?"](https://pokemon.fandom.com/wiki/Who's_That_Pok%C3%A9mon%3F) | Guess who the person is when their face is hidden |

Detailed gameplay for each game, including modes and scoring rules, can be found in
[`docs/GAMES/`](./docs/GAMES/OVERVIEW.md).

## Current Status

**Three games are fully playable:**
- **MoreOrLess** ✅ (PC and mobile layouts, both English and Spanish)
- **Geoguessr** ✅ (MapLibre-powered, 5-round game mode)
- **Dateguessr** ✅ (Timeline-based, 5-round game mode)

**Other games are design stubs only** (Immichdle, Timeline, Who'sThatPerson).

**Features:**
- ✅ User login (email/username/password, profile page, logout)
- ✅ Dark theme (consistent with Immich's color palette)
- ✅ Full Spanish translation (i18n-ready codebase)
- ✅ Docker support (GHCR images for easy deployment)
- ✅ Direct Postgres access for game data, Immich REST API for images
- ❌ Daily challenges (planned)
- ❌ Leaderboards (planned)
- ❌ Report incorrect metadata (planned)

Full implementation roadmap is in [`docs/TODO/ROADMAP.md`](./docs/TODO/ROADMAP.md).

## Installation & Usage

### Prerequisites

- An existing [Immich](https://immich.app) instance (v1.90.0+) running with Postgres and Immich-ML
- Docker and Docker Compose (recommended)

### Quick Start with Docker Compose

1. Clone this repository:
   ```bash
   git clone https://github.com/open-rais/immich-minigames
   cd immich-minigames
   ```

2. Create a `.env` file with your Immich database credentials:
   ```env
   # Immich database
   DB_HOST=your-immich-db-host
   DB_PORT=5432
   DB_NAME=immich
   DB_APP_USERNAME=immich_app
   DB_APP_PASSWORD=your_immich_app_password
   
   # Immich API
   IMMICH_API_URL=http://your-immich-server/api
   IMMICH_ML_URL=http://your-immich-ml-service:3003
   
   # Backend
   BACKEND_PORT=8000
   ```

3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

   The frontend will be available at `http://localhost:5173` (dev) or the configured port in production.

### Development Setup

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

Both require the Immich instance and database to be running. See `docs/ARCHITECTURE/IMMICH.md` for
database schema details.

## Architecture

The backend (FastAPI) is organized in layers:
- **API** (`api/api.py`): REST endpoints, mounted routes
- **Services** (`services/`): business logic for games, Immich integration, ML
- **Domain** (`domain/`): models (Asset, Person, Album)
- **Persistence** (`persistence/games.py`): app-specific database models
- **Games** (`games/`): one module per minigame (shared contract in `base.py`)

The frontend (React + Vite + Tailwind) is organized per game under `frontend/src/games/<Game>/` with
shared components and design tokens in `index.css`.

## Database Access & Security

This app accesses the Immich Postgres database directly (read-only for Immich's `public` schema) to
fetch game data efficiently. It uses a dedicated `DB_APP_USERNAME` role and never modifies Immich's
own tables. Images are always fetched through Immich's REST API, never directly from disk.

**Use this at your own risk.** While access is read-only and images are never touched, you run this
code alongside your personal photo database. Review the source code if you have concerns.

## FAQs

**Q: Is this official?**  
A: No, this is an unofficial community project unaffiliated with the Immich team.

**Q: Will my photos be copied or modified?**  
A: No. This app only reads metadata from Immich's database and fetches image thumbnails via Immich's
API. It never stores, modifies, or copies photos.

**Q: Why not just use Immich's public API?**  
A: The API doesn't expose all metadata needed for games (e.g., face similarity scores, precise location
data). Direct read-only database access allows us to query efficiently without duplicating data.

More FAQs in [`docs/FAQS.md`](./docs/FAQS.md).
