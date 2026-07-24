# Architecture

Index of the architecture docs. These describe **how the system is put together**, as opposed to
`docs/GAMES/` (what each game does for the player) and `docs/TODO/ROADMAP.md` (what gets built
next).

| Doc | Covers |
|---|---|
| [IMMICH.md](IMMICH.md) | How this app talks to Immich: the two channels (Postgres vs REST), which Immich tables are read, and the face-embedding queries. |
| [BACKEND.md](BACKEND.md) | FastAPI layering, the game abstraction, persistence, auth, admin settings, request lifecycle. |
| [FRONTEND.md](FRONTEND.md) | React structure, the per-game state machines, the design-token system, responsive conventions. |

> **Note:** these three files were written during the code review of 2026-07-20. Code comments
> across the repo had been citing them (plus `ADMIN-FEATURE.md` and `AUDIT_TODO.md`) for a long
> time without them existing — see finding #1 in `docs/TODO/CODE-REVIEW.md`. `ADMIN-FEATURE.md`
> and `AUDIT_TODO.md` still do not exist; their content is folded into BACKEND.md's "Admin
> feature" section here instead.

## System at a glance

Three processes, one database.

```
┌────────────┐   HTTP (same origin)   ┌──────────────┐
│  Browser   │ ─────────────────────► │  frontend    │  nginx: serves the SPA,
│  (React)   │                        │  (nginx)     │  reverse-proxies /api/ ──┐
└────────────┘                        └──────────────┘                          │
                                                                                ▼
                                                                        ┌──────────────┐
                                                                        │   backend    │
                                                                        │  (FastAPI)   │
                                                                        └──────┬───────┘
                                                     ┌─────────────────────────┴──────┐
                                       SQL (read-only on public,                REST (image bytes,
                                        read/write on minigames)                 x-api-key)
                                                     ▼                                ▼
                                          ┌────────────────────┐            ┌──────────────────┐
                                          │  Postgres instance │            │  Immich server   │
                                          │  immich | minigames│            │   (:2283)        │
                                          │  (2 databases)     │            │                  │
                                          └────────────────────┘            └──────────────────┘
```

Key structural decisions, and where each is justified:

- **This app owns its own database, on Immich's Postgres instance.** Never a schema inside Immich's
  own database — that broke Immich's backup/restore. See BACKEND.md § Persistence.
- **Two channels to Immich, never mixed.** Metadata comes from Postgres directly; image bytes come
  from Immich's REST API. See IMMICH.md § Two ways to talk to Immich.
- **Immich is read-only from this app's perspective.** Enforced at the DB-role level, not just by
  convention. See IMMICH.md § The scoped DB role.
- **The browser only ever talks to one origin.** nginx (prod) / Vite (dev) proxy `/api/` to the
  backend, so there is no CORS configuration anywhere. See FRONTEND.md § API layer.

## Two identity systems

This trips people up, so it is stated once here and referenced from both other docs.

| | `X-Owner-Id` | User account |
|---|---|---|
| What | Random UUID in `localStorage`, sent as a request header | Row in `minigames.users` |
| Set by | The browser itself (`frontend/src/api/ownerId.ts`) | Registration (`POST /auth/register`) |
| Carried as | Plain header, client-controlled, **not authenticated** | httpOnly JWT cookie (HS256) |
| Used for | Owning/replaying a game, anonymous personal records | Leaderboards, profile, skin, admin |
| Stored on `GameModel` | `owner` (always) | `user_id` (only if the creating request had a valid cookie) |

A game created while logged in has **both**. Ownership checks on `GET /games/{id}` and
`POST /games/{id}/rounds/{id}` currently key off `owner` only — see finding #3 in
`docs/TODO/CODE-REVIEW.md` for why that matters.

## Where the code lives

```
backend/src/
  main.py            app wiring + the single place domain exceptions → HTTP status codes
  config.py          pydantic-settings, reads repo-root .env
  api/               routes + DTOs (dto/ per game, auth_schemas.py, common.py)
  services/          business logic (games, immich, ml, auth, game_settings, admin_bootstrap)
  games/             one module per minigame + the shared BaseGame/BaseRound contract
  domain/            plain dataclasses mirroring Immich concepts (Asset/Person/Face/Album)
  persistence/       this app's own SQLAlchemy models + Immich's tables (read-only Core Tables)
  scripts/           bootstrap_db_role.py (one-shot DB provisioning)
frontend/src/
  api/               axios client, typed request fns, hand-mirrored types
  games/<Name>/      one folder per game; games/shared/ holds the reusable pieces
  menu/ auth/ admin/ theme/ i18n/
```
