# immich-minigames

Transform your self-hosted photo library into interactive minigames.

**immich-minigames** is an unofficial project that leverages the Immich API to create a collection of fun, replayable games using your photo library's metadata.

## 🎮 Games

- **MoreOrLess** — Guess if the next person/album has more or less items
- **Geoguessr** — Place photos on a map based on location metadata
- **Dateguessr** — Timeline dating game using photo timestamps
- **WhoIsThere** — Identify people hidden in photos (face detection)
- **Immichdle** — Guess a person using hints (age, count, similarity)
- More...?

## ✨ Features

- [X] One-command deployment with Docker
- [X] No user accounts — uses only Immich URL + API key
- [X] Self-hosted — all data stays local
- [X] Plugin architecture — easily add new games
- [X] High score tracking
- [X] Modular, SOLID design

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- An active Immich instance with photos and metadata

### Deploy with Docker (Recommended)

```bash
git clone https://github.com/yourusername/immich-minigames.git
cd immich-minigames

# Start all services (PostgreSQL, Redis, Backend, Frontend)
docker compose up -d

# Or use the startup script for easier management
chmod +x docker-startup.sh
./docker-startup.sh start
```

Then visit **`http://localhost:3000`** and connect to your Immich instance.

**Full Docker guide:** See [DOCKER.md](DOCKER.md) for detailed Docker setup, configuration, troubleshooting, and production deployment.

### Local Development

For local development without Docker:

```bash
# Terminal 1: Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn src.main:app --reload

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` and configure your Immich connection.

## 📚 Documentation

- **[Vision & Philosophy](docs/01-vision.md)** — Project goals and principles
- **[Games Overview](docs/02-games.md)** — Game descriptions and mechanics
- **[Architecture](docs/04-architecture/)** — System design and patterns
- **[Development Setup](backend/README.md)** — Local development guide
- **[Contributing](CONTRIBUTING.md)** — How to contribute
- **[Full Documentation](docs/)** — Complete documentation index

## 🛠️ Tech Stack

### Backend
- Python 3.12+
- FastAPI
- SQLAlchemy (async)
- Alembic (migrations)
- Pydantic (validation)

### Frontend
- Next.js (App Router)
- TypeScript
- Tailwind CSS

### Infrastructure
- PostgreSQL (persistent data)
- Redis (sessions/cache)
- Docker & Docker Compose (deployment)

## 💾 Non-Goals

This project **does NOT**:
- Replace or modify Immich
- Store or sync photos
- Handle authentication
- Work without Immich

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📋 Roadmap

See [Development Roadmap](docs/06-roadmap.md) for phases and priorities.

**MVP Status:** Phase 0 (Foundation) — In Progress

## 📝 License

[See LICENSE file](LICENSE)

## 🙏 Acknowledgments

- [Immich](https://immich.app/) — Amazing self-hosted photo management
- Contributors and community members

---

**Questions?** Open an issue or check the [documentation](docs/).