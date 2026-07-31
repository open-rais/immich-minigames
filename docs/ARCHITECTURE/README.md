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
> across the repo had been citing `ADMIN-FEATURE.md` and `AUDIT_TODO.md` for a long time without
> either file existing. Neither exists now either; their content is folded into BACKEND.md's
> "Admin feature" section here instead.

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

## Identity

Every game belongs to a logged-in account — there is no anonymous play. Login is a stateless JWT
(HS256) in an httpOnly cookie, issued by `POST /auth/register`/`POST /auth/login`; a default-deny
session middleware requires a valid cookie on every route except the small allow-list of public
ones (login/register/reset-password/health). `GameModel.user_id` is a real FK to the account and
every ownership check (`GET /games/{id}`, `POST /games/{id}/rounds/{id}`) compares against it,
raising `GameOwnershipError` on a mismatch. See BACKEND.md § Auth for the full request lifecycle.

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
