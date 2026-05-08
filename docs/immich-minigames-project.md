# immich-minigames

## Overview

**immich-minigames** is an unofficial project built on top of the API of immich.

Its goal is to transform a personal photo library into a collection of interactive minigames using the metadata and ML capabilities provided by Immich.

This project does **not** aim to:

- replace Immich
- store photos
- modify photo libraries
- improve Immich itself

It is a standalone game platform.

---

# Vision

Turn self-hosted photo libraries into interactive experiences.

The project aims to create fun, replayable minigames using:

- people metadata
- album metadata
- timestamps
- geolocation
- face detection
- face similarity

This also indirectly motivates users to improve their metadata quality.

---

# Target Audience

- self-hosters
- families
- friend groups
- Immich enthusiasts
- metadata perfectionists

---

# Core Product Philosophy

## Simple deployment

Must be deployable with Docker.

---

## No user accounts

No internal authentication.

Uses only:

- Immich URL
- Immich API key

---

## Local-first

Designed for self-hosted environments.

---

## Plugin-based architecture

Each game is isolated and pluggable.

---

## SOLID-first

Architecture must follow SOLID principles.

---

## Open-source ready

Codebase should be contribution-friendly.

---

# Initial Games

---

## MoreOrLess

Inspired by “Higher or Lower”.

Player guesses if the next entity has more or less of something.

### Modes

- person-items
- album-items
- timeline

Examples:

- Does Person B have more or less items than Person A?
- Does Album B have more or less items than Album A?
- Is Item B newer or older than Item A?

---

## Geoguessr

Player sees photos from the same location and must guess the location on a map.

Scoring is based on distance.

---

## Dateguessr

Player sees photos from the same date and must guess the date on a timeline.

Scoring is based on time difference.

---

## WhoIsThere

Player sees a photo with hidden faces.

Must identify who is behind each face.

Scoring based on correct identifications.

---

## Immichdle

Guess a hidden person using hints.

Hints:

- age
- item count
- face similarity
- shared appearances

---

# MVP Scope

Initial MVP:

Only implement:

- Settings
- Immich connection
- MoreOrLess
- person-items mode
- high score

Everything else comes later.

---

# Architecture Decision Record (ADR)

## Decision: Monolith Modular Architecture

Chosen architecture:

Modular monolith.

---

## Why modular monolith?

Benefits:

- easier deployment
- simpler development
- plugin-ready
- scalable enough
- can evolve later

---

# System Architecture

```
immich-minigames/
├── backend/
├── frontend/
├── docker/
└── docs/
```

---

# Backend Architecture

Clean Architecture.

```
backend/
├── src/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   ├── presentation/
│   ├── games/
│   └── core/
```

---

# Layer Responsibilities

---

## Domain

Contains business logic.

Responsibilities:

- entities
- value objects
- interfaces

---

## Application

Contains use cases.

Responsibilities:

- game lifecycle
- orchestration

---

## Infrastructure

Contains integrations.

Responsibilities:

- Immich API
- database
- cache

---

## Presentation

Contains API.

Responsibilities:

- REST endpoints
- schemas

---

## Games

Contains plugins.

Responsibilities:

- game logic
- scoring
- rounds

---

# Frontend Architecture

Built with :contentReference[oaicite:1]{index=1}.

Uses App Router.

```
frontend/
├── app/
│   ├── settings/
│   ├── games/
│   ├── more-or-less/
│   ├── geoguessr/
│   ├── dateguessr/
│   ├── who-is-there/
│   └── immichdle/
```

---

# Routing Structure

```
/
├── /settings
├── /games
├── /more-or-less
│   ├── /person-items
│   ├── /album-items
│   └── /timeline
├── /geoguessr
├── /dateguessr
├── /who-is-there
└── /immichdle
```

---

# Technology Stack

---

## Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

---

## Frontend

- Next.JS
- Typescript
- Tailwind

---

## Database

- PostgreSQL

Used for:

- settings
- game stats

---

## Cache

- Redis

Used for:

- active sessions
- Immich cache

---

## Deployment

- Docker
- Docker Compose

---

## Testing

- Pytest
- Playwright

---

# Domain Model

---

## Settings

Persistent.

```
Settings
- key
- value
- updated_at
```

---

## GameStats

Persistent.

```
GameStats
- game_slug
- mode_slug
- best_score
- times_played
```

---

## GameSession

Ephemeral.

Stored in Redis.

```
GameSession
- id
- game_slug
- mode_slug
- score
- round_number
- state
```

---

## GameRound

Ephemeral.

```
GameRound
- id
- prompt
- metadata
```

---

## RoundResult

Ephemeral.

```
RoundResult
- correct
- points_awarded
- current_score
- game_over
- feedback
```

---

## GameResult

Ephemeral.

```
GameResult
- final_score
- best_score
- summary
```

---

# Plugin System

Every game implements GamePlugin.

```
GamePlugin
- start()
- generate_round()
- submit_answer()
- is_finished()
- finalize()
```

---

# Game Lifecycle

```
Start
↓
Generate Round
↓
Receive Answer
↓
Validate
↓
Score
↓
Next Round
↓
Finish
```

---

# Game Registry

Responsible for plugin registration.

```
GameRegistry
- register()
- get()
```

Purpose:

Dynamic plugin loading.

---

# Immich Integration Layer

Uses Adapter Pattern.

Structure:

```
integrations/
└── immich/
    ├── client.py
    ├── provider.py
    ├── mapper.py
    └── schemas.py
```

---

# ImmichProvider Contract

Abstracted interface.

---

## Health

```
healthcheck()
```

---

## People

```
get_people()
get_random_person()
get_person_asset_count()
```

---

## Albums

```
get_albums()
get_random_album()
get_album_asset_count()
```

---

## Assets

```
get_assets()
get_random_asset()
```

---

## Location

```
get_random_asset_with_location()
get_random_assets_same_location()
```

---

## Dates

```
get_random_assets_same_day()
```

---

## Faces

```
get_random_asset_with_faces()
get_asset_people()
```

---

## Similarity

```
get_face_similarity()
```

---

# API Design

---

## Settings

```
GET /api/settings
PUT /api/settings
POST /api/settings/test-connection
```

---

## Games

```
GET /api/games
GET /api/games/{game}
GET /api/games/{game}/{mode}
```

---

## Sessions

```
POST /api/sessions/start
GET /api/sessions/{id}
GET /api/sessions/{id}/round
POST /api/sessions/{id}/answer
POST /api/sessions/{id}/finish
```

---

## Stats

```
GET /api/stats
GET /api/stats/{game}
```

---

# Design Patterns

---

## Strategy Pattern

Used for scoring.

---

## Factory Pattern

Used for game creation.

---

## Adapter Pattern

Used for Immich integration.

---

## Repository Pattern

Used for persistence.

---

## Template Method

Used for game lifecycle.

---

## Dependency Injection

Used for infrastructure decoupling.

---

# SOLID Principles

---

## Single Responsibility Principle

Each module has one responsibility.

---

## Open/Closed Principle

New games added without modifying core.

---

## Liskov Substitution Principle

All plugins interchangeable.

---

## Interface Segregation Principle

Small focused interfaces.

---

## Dependency Inversion Principle

Core depends on abstractions.

---

# Repository Standards

Branching:

```
main
develop
feature/*
fix/*
docs/*
refactor/*
```

---

Commit convention:

```
feat:
fix:
docs:
refactor:
test:
chore:
ci:
```

---

Required files:

```
README.md
CONTRIBUTING.md
LICENSE
CHANGELOG.md
CODE_OF_CONDUCT.md
SECURITY.md
```

---

# Development Standards

---

## Formatting

Python:

- black
- isort

TS:

- prettier

---

## Linting

Python:

- ruff

TS:

- eslint

---

## Type checking

Python:

- mypy

TS:

- typescript strict mode

---

## Testing

Minimum:

- unit tests
- integration tests

Optional:

- e2e

---

# Backlog

---

# Phase 0 — Foundation

Priority: P0

---

## Repository Setup

- initialize repository
- configure backend
- configure frontend
- configure docker compose
- configure environment management

---

## Tooling

- configure linting
- configure formatting
- configure pre-commit hooks
- configure CI pipeline

---

## Documentation

- README
- CONTRIBUTING
- architecture docs

---

# Phase 1 — Core Engine

Priority: P0

---

## Settings System

- settings model
- settings API
- settings UI
- test connection endpoint

---

## Game Registry

- registry class
- plugin registration

---

## Session Engine

- session creation
- session retrieval
- session cleanup

---

## Stats Engine

- high score tracking
- games played tracking

---

# Phase 2 — Immich Integration

Priority: P0

---

## Base API Client

- auth handling
- health endpoint
- error handling

---

## People API

- list people
- random person
- item count

---

## Albums API

- list albums
- random album
- asset count

---

## Assets API

- list assets
- random asset

---

# Phase 3 — MoreOrLess MVP

Priority: P0

---

## Plugin Creation

- plugin implementation
- mode registration

---

## person-items mode

- round generation
- answer validation
- scoring

---

## UI

- game page
- round page
- result page

---

# Phase 4 — MoreOrLess Expansion

Priority: P1

---

## album-items mode

- implementation

---

## timeline mode

- implementation

---

# Phase 5 — Geoguessr

Priority: P1

---

## Location retrieval

- location grouping

---

## Map integration

- map UI

---

## Distance scoring

- score algorithm

---

# Phase 6 — Dateguessr

Priority: P1

---

## Date grouping

- same-day grouping

---

## Timeline UI

- timeline selector

---

## Date scoring

- score algorithm

---

# Phase 7 — WhoIsThere

Priority: P2

---

## Face detection retrieval

- face boxes

---

## Blur overlay

- face masking

---

## Answer validation

- person matching

---

# Phase 8 — Immichdle

Priority: P2

---

## Person selection

- random target

---

## Hint engine

- age
- count
- similarity
- shared appearances

---

# Future Ideas

- daily challenges
- multiplayer
- global leaderboards
- custom game settings
- difficulty modes
- community-made games

---

# Non-Goals

- replacing Immich
- modifying Immich
- storing media
- syncing media
- *editing metadata (Can be used to mark metadata as incorrect in a future with a report system)

---

# Deployment Goal

Single command deployment.

```
docker compose up -d
```

---

# Success Criteria

MVP success means:

- user can connect to Immich
- user can play MoreOrLess
- score is tracked
- architecture supports new games
- codebase is contributor-ready