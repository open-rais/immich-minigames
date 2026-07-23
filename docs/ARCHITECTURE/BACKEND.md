# Backend

FastAPI app in `backend/src/`. Run: `cd backend && uv run uvicorn main:app --app-dir src --port 8000`
(needs `alembic upgrade head` once first). Tests: `cd backend && uv run pytest` (234 passing as of
2026-07-20).

## Layering

```
api/        HTTP only: routing, DTO validation, dependency wiring. No business rules.
services/   Business logic. Knows about the DB and about Immich. Raises domain exceptions.
games/      Pure game rules. No persistence, no HTTP. Depends on services only for data lookup.
domain/     Frozen dataclasses mirroring Immich concepts. No behavior.
persistence/ SQLAlchemy models (own database) + Core Tables (Immich's database, read-only).
scripts/    One-shot operational tooling. Not imported by the app, run by the `db-init` service.
```

`scripts/` is the only part of the codebase that ever holds Immich's admin credentials:

| File | Purpose |
|---|---|
| `bootstrap_db_role.py` | Entry point of the `db-init` compose service. Provisions the scoped role, creates this app's database, applies migrations to it, and triggers the legacy migration below. Idempotent. |
| `migrate_legacy_schema.py` | One-time move of this app's tables out of Immich's database. Copy → verify row counts → drop, in that order, refusing to drop anything it can't account for. |

The dependency direction is strictly downward. `games/` never imports `api/`; `domain/` imports
nothing from the app.

### Error handling is centralized

Routes **do not** try/except their own domain exceptions. Each service raises a typed exception, and
`main.py` is the single place mapping exception class → HTTP status:

| Exception | Status |
|---|---|
| `UnsupportedGameError`, `DuplicateGuessError`, `InvalidGuessError`, `UnknownGameSettingError`, `InvalidGameSettingValueError` | 400 |
| `InvalidCredentialsError`, `UnauthorizedError` | 401 |
| `GameOwnershipError` | 403 |
| `GameNotFoundError` | 404 |
| `RoundNotPendingError` | 409 |
| `IncompleteGuessError` | 422 |
| `RateLimitExceeded` (slowapi) | 429 |

Adding a game exception means adding one line in `main.py`, not a try/except in a route.

> The handler serializes `str(exc)` straight into `{"detail": ...}`, and the frontend renders that
> string to the user verbatim. See findings #11 and #12.

## The game abstraction

`games/base.py` defines the contract every minigame implements.

**`BaseRound`** — holds `id`, `game_id`, `round_index`, `shown_entities` (ids already used, so
later rounds don't repeat them), `guess`, `score_delta`. Implements:
- `calculate_score(settings)` → the score delta for this round's guess
- `to_payload()` / `from_payload(...)` → the JSONB round trip

**`BaseGame`** — holds `id`, `owner`, `score`, `rounds`, `finished`, `_settings`. `current_round` is
`rounds[-1]`. The shared loop is `play_round(guess)`:

```
if finished: error
current.guess = guess
current.score_delta = current.calculate_score(settings)
score += score_delta
if has_next_round(): rounds.append(create_next_round())
else:                finished = True
```

Concrete games fill in `has_next_round()` (when does it end) and `create_next_round()` (pick the
next question, avoiding what's been shown).

Two games override `play_round` itself, because their guess needs resolving before it can be
scored: **Immichdle** (the guess is a person id that must be validated and turned into clues) and
**Who'sThatPerson** (validates the guess covers exactly the round's hidden faces).

### Per-game rules

| Game | Ends when | Score |
|---|---|---|
| MoreOrLess | First wrong guess | +1 per correct round (a tie counts as correct) |
| Geoguessr | 5 rounds | `exp_decay_score(km)`, max 5000, flat within 1km, decay 1500km |
| Dateguessr | 5 rounds | Same curve on days: flat 0, decay 500 days |
| Immichdle | Correct guess, or score hits 0 | Starts at 100, −5 per wrong guess |
| Who'sThatPerson | 15 people asked (across variable-size rounds) | Combo streak by person; any miss in a round zeroes the incoming streak *before* scoring |
| Timeline | — | Not implemented; `games/timeline.py` is a design stub |

**Geoguessr and Dateguessr share `games/asset_rounds.py`** — fixed N rounds, one asset per round,
decay scoring, spread-out candidate picking. They differ only in the metric (great-circle km vs
calendar days), the snapshot type, and asset eligibility (Geoguessr requires GPS).

### Snapshots, not live lookups

Every game freezes what it needs into the round's JSONB payload at creation time (`PersonSnapshot`,
`AssetSnapshot`, `HiddenFace`). A round's correct answer must not change because someone renamed a
person or fixed a date in Immich mid-game. This is why the payload duplicates data that also exists
in Immich.

### The double-sample pattern

`has_next_round()` does a cheap `LIMIT 1` existence check; `create_next_round()` then samples
properly (10 candidates, picking one far enough from previous answers). Sampling twice is
deliberate — the existence check is consistent with the real pick because the real pick always
falls back to `candidates[0]`, so "pool is non-empty" is exactly the right precondition.

## Persistence

Own tables live in this app's **own Postgres database** (`DB_APP_DATABASE_NAME`, default
`minigames`), on the same instance as Immich but never inside Immich's database — see "Por qué una
base de datos separada" below. Inside it they sit in a `minigames` schema rather than `public`;
with the app owning the whole database that's cosmetic, but it keeps every already-applied
migration (which hardcodes `schema=`) valid and untouched.

Alembic owns the schema (`backend/alembic/versions/`, currently 0001–0006); `docker-entrypoint.sh`
runs `alembic upgrade head` on every container start, and `db-init` runs it too — as the app role,
so the tables end up owned by the role that later has to `ALTER` them. `init_db`/`reset_db` in
`persistence/base.py` exist only for tests.

| Table | Notes |
|---|---|
| `games` | `owner` (anonymous id), `user_id` (nullable FK → `users`), `game_type`, `mode`, `score`, `finished`, `created_at`. Indexed on `(owner, game_type, mode)` and `(user_id, game_type, mode)` — one per personal-records filter branch. |
| `rounds` | `game_id` FK, `round_index`, `score_delta` (null until answered), `payload` JSONB. Unique on `(game_id, round_index)`, which also provides the FK index Postgres doesn't create automatically. |
| `users` | `email`/`username` unique, `password_hash` (argon2), `skin_person_id` (deliberately **not** a FK — it points into Immich's database, which foreign keys cannot span), `is_admin`, `created_at`. |
| `game_settings` | `game_type` PK, `values` JSONB. One row per game type; a missing row or key falls back to the module constant. |
| `legacy_import` | Marker written by the one-time move out of Immich's database. Its presence means that copy committed — see below. |
| `person_face_embedding_cache` | `person_id` PK, `embedding vector(512)`, `face_count`, `computed_at`. Caches Immichdle's `MLSimilarity` clue's per-person representative embedding (average across that person's visible faces) - see `docs/ARCHITECTURE/IMMICH.md`'s "Face similarity" section. The only own table with a non-JSON/UUID/text column type, hence `persistence/ml_cache.py`'s hand-rolled `Vector` SQLAlchemy type instead of a plain `mapped_column`. |

**Generic rounds table + JSONB payload** is the core persistence decision: adding a game never
requires a migration, only a `to_payload`/`from_payload` pair.

Two engines, two pools, one login role: `get_app_engine` (`persistence/base.py`, read/write) and
`get_immich_engine` (`persistence/immich_db.py`, read-only). Both `lru_cache`d with
`pool_pre_ping=True`. No query ever spans them — Immich reads go through Core `engine.connect()`,
own-data access usually through the ORM `Session` (games/users/settings), and the two never meet
in one statement or transaction. `services/ml_service.py`'s embedding cache is the one exception to
"Session for own data": it holds plain `Engine`s on both sides (matching the raw-SQL style it
already used for Immich reads) rather than threading a `Session` through a service that's normally
constructed without one.

### Por qué una base de datos separada

Hasta la versión anterior las tablas propias vivían en un esquema `minigames` **dentro** de la base
de datos `immich`. Eso rompía la restauración de backups de Immich, y conviene dejar registrado el
mecanismo exacto porque no es obvio:

Immich respalda con `pg_dump --clean --if-exists` sobre su propia base de datos, así que el esquema
`minigames` quedaba **dentro de sus dumps**. Al restaurar, el dump ejecuta
`DROP SCHEMA IF EXISTS minigames`, que falla si la base viva tiene tablas creadas *después* de ese
backup (p.ej. `game_settings`, migración `0004`): no están en el dump, no se dropean primero, y
bloquean el drop. Como el restore corre con `--single-transaction --set ON_ERROR_STOP=on`, aborta
entero. Es decir: **cualquier migración posterior a un backup rompía la restauración de ese
backup.**

Dos problemas del mismo origen: Immich reescribe todo `OWNER TO` del dump a su propio usuario, así
que incluso un restore exitoso habría dejado las tablas con dueño equivocado; y los `GRANT` a
nuestro rol quedaban como ACLs dentro de la base de Immich, viajando en cada dump.

Una base de datos separada queda fuera del alcance de `pg_dump`. Por eso también la lectura de
Immich se otorga con `GRANT pg_read_all_data` en vez de `GRANT SELECT ON ALL TABLES`: la membresía
de rol vive en `pg_auth_members`, a nivel de clúster, así que la base de Immich no conserva ninguna
referencia a esta app — y de paso no queda obsoleta cuando un upgrade de Immich agrega tablas.

Las instalaciones anteriores se migran solas en el primer `db-init`
(`scripts/migrate_legacy_schema.py`): copia con `COPY ... FORMAT BINARY`, verifica row counts dentro
de la transacción destino, y solo entonces dropea el esquema viejo. Ante cualquier discrepancia no
dropea nada y falla ruidosamente. **Tras restaurar un backup de Immich anterior a la separación
(que resucita el esquema viejo), vuelve a correr `db-init`.**

## Auth

This app's own accounts, entirely separate from Immich's users.

- **Passwords**: argon2 (`argon2-cffi`'s `PasswordHasher`).
- **Session**: stateless JWT (HS256, `sub` = user id, `exp` = now + `JWT_EXPIRE_DAYS`), in an
  httpOnly `access_token` cookie, `SameSite=Lax`, `Secure=False`.
- **Logout** clears the cookie. There is no server-side session table, so a token copied before
  logout stays valid until it expires. Accepted tradeoff for "lo básico"; rotating `JWT_SECRET`
  invalidates everything.
- **Rate limiting**: slowapi, keyed by client IP, in-memory. Only `register` (3/min) and `login`
  (5/min) are limited.

Two dependencies read the cookie: `get_current_user` (raises `UnauthorizedError`) and
`get_current_user_optional` (returns `None`, used where a route serves both anonymous and logged-in
callers, e.g. `create_game`).

There is **no password-change or password-reset endpoint** — see finding #10.

## Admin feature

(This section replaces the never-written `ADMIN-FEATURE.md` that ~41 code comments cite.)

Four pieces, referenced in comments as points #1–#4:

1. **Promotion** (`services/admin_bootstrap.py`) — on every backend startup, if `ADMIN_EMAIL`
   matches an already-registered account, its `is_admin` flips to true. Promotion only: it never
   creates an account. Idempotent, so running it on every `--reload` is safe.
2. *(Frontend admin entry point — the `/admin` route and its UserMenu link.)*
3. **User admin** (`api/admin_api.py`) — an `is_admin` account can list all users and edit any
   user's full name / username / skin. Reuses `auth_schemas.py`'s DTOs applied to an arbitrary
   `user_id`.
4. **Game settings** (`api/admin_games_api.py`, `services/game_settings.py`) — per-`game_type`
   overrides of the scoring/difficulty constants each game module defines.

`GAME_SETTING_SPECS` is the registry of what is configurable: each `SettingSpec` has a key, the
module constant as its default, a value type (`int`/`float`) and a `min_value`. Only knobs that
affect *visible scoring/difficulty* are exposed — internal sampling parameters like
`_CANDIDATE_SAMPLE_SIZE` stay private module constants. Geoguessr and Dateguessr get independent
entries even though they share `asset_rounds.py` defaults. MoreOrLess has an explicit empty list so
it still appears in `GET /admin/games/settings`.

Effective values are read **live on every game start/load** (`GamesService._game_kwargs`), never
cached and never snapshotted onto a round, so an admin change takes effect on the very next round
played. Resetting deletes the row rather than writing defaults back.

> `update_settings` validates a lower bound but no upper bound, and `dict[str, float]` accepts
> `Infinity`/`NaN`. See finding #7.

## Request lifecycle: playing a round

`POST /api/v1/games/{game_id}/rounds/{round_id}` is the most involved path:

1. `get_owner_id` reads the `X-Owner-Id` header (required; no validation).
2. `games_service.get_game(game_id, owner)` → `_load_game`: fetch `GameModel`, compare `owner`
   (raise `GameOwnershipError` on mismatch), look up the `(game_type, mode)` spec, rebuild every
   round via `from_payload`, construct the game with live admin settings.
3. `parse_guess(existing_game.current_round, body)` picks the right pydantic schema from
   `_ROUND_SPECS` keyed on the round's concrete class, validates, and converts to a domain guess.
   The client never states its own `game_type` — `game_id` already fixes it, so there is nothing to
   disagree about.
4. `play_loaded_round` checks the round is genuinely the pending one (`RoundNotPendingError`),
   delegates to the game's `play_round`, then persists: update the game's score/finished, write the
   answered round's `score_delta` + `payload`, and insert the newly created round if there is one.
5. `PlayRoundOut.from_answered` serializes, redacting anything that would spoil an unanswered round.

> Step 4 is not concurrency-safe: two simultaneous requests for the same round can both pass the
> pending check. See finding #6.

### Redaction

DTOs are where secrets are stripped, not the domain layer. `MoreOrLessRoundOut.candidate_asset_count`,
`GeoguessrRoundOut.actual_latitude/longitude`, `DateguessrRoundOut.actual_date`,
`HiddenFaceOut.person_id/person_name` are all `None` until `round_.answered`. Immichdle's target is
never in a round's output at all — it surfaces only via `GameOut.target_person_id/name`, and only
once the game is finished.

This layer is well-disciplined. Note that it is defeated for Who'sThatPerson by the unauthenticated
thumbnail proxy (finding #4): the faces are hidden by a DOM overlay, not by altering the image.

## Configuration

`config.py`, pydantic-settings, reads the repo-root `.env`. `get_settings()` is `lru_cache`d
because constructing `Settings()` re-reads the file from disk.

| Var | Purpose |
|---|---|
| `DB_APP_USERNAME` / `DB_APP_PASSWORD` | The scoped role the backend runs as. **Never** `DB_USERNAME`/`DB_PASSWORD` (Immich's admin connection — only `db-init` sees those). |
| `DB_HOST` / `DB_PORT` | The Postgres instance both databases live on. |
| `DB_DATABASE_NAME` | Immich's own database — **read-only** for this app. |
| `DB_APP_DATABASE_NAME` | This app's own database (default `minigames`), created by `db-init`. Read/write. |
| `IMMICH_SERVER_URL` / `IMMICH_API_KEY` | Immich's REST API, for image bytes. |
| `JWT_SECRET` / `JWT_EXPIRE_DAYS` | This app's own sessions. |
| `ADMIN_EMAIL` | Account to promote to admin on startup. |
