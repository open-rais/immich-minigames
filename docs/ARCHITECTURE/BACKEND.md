# Backend

FastAPI app in `backend/src/`. Run: `cd backend && uv run uvicorn main:app --app-dir src --port 8000`
(needs `alembic upgrade head` once first). Tests: `cd backend && uv run pytest` (401 passing as of
2026-07-29).

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
| `GameNotFoundError`, `DailyNotEnabledError` | 404 |
| `RoundNotPendingError`, `DailyAlreadyPlayedError` | 409 |
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
| Timeline | — | Not implemented; `games/timeline/game.py` is a design stub |

**Geoguessr and Dateguessr each own their whole loop** (`games/geoguessr/game.py` /
`games/dateguessr/game.py`) — fixed N rounds, one asset per round, decay scoring, spread-out
candidate picking. They used to share a `games/asset_rounds.py` base class; that base class is
gone (see `docs/TODO/DECOUPLING.md`) precisely so a bug in one game's loop never requires touching
the other's file — the two implementations are near-identical by construction, not by import. The
only genuinely shared code is `games/shared/`'s pure functions (`exp_decay_score`,
`pick_spread_asset`) and `games/base.py`'s contract. Each still differs only in the metric
(great-circle km vs calendar days), the snapshot type, and asset eligibility (Geoguessr requires
GPS) — plus, since the daily-games work, in a `<Name>Content` protocol (`LiveContent` for normal
play, `ScriptedContent` for the daily replay, see below) that factors out *which* asset a round
gets from the loop that plays it.

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
| `daily_configs` | Roadmap #G. `(game_type, mode)` PK, `enabled` bool, `values` JSONB - whether a mode is in the daily rotation plus its daily-only setting overrides. |
| `daily_challenges` | Roadmap #G. `id` PK, unique `(challenge_date, game_type, mode)`, `spec` JSONB (the pre-generated shared content), `settings` JSONB (frozen effective settings for that day). `games.daily_challenge_id` (nullable FK, two partial unique indexes for "one attempt per player") points into this. |

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

`GAME_SETTING_SPECS` (`services/game_settings.py`) is the registry of what is configurable, but it
only *assembles* it - each game declares its own knobs in its own `games/<name>/settings.py`
(`SETTING_SPECS: dict[mode, list[SettingSpec]]`), and `game_settings.py` flattens all of them into
one `(game_type, mode)`-keyed dict. `SettingSpec`/`ValueType` themselves live in
`games/settings_spec.py` (contract-only, no logic) so a game's `settings.py` doesn't have to depend
on `services/` to declare its specs. Each `SettingSpec` has a key, the module constant as its
default, a value type (`int`/`float`) and a `min_value`. Only knobs that affect *visible
scoring/difficulty* are exposed — internal sampling parameters like `_CANDIDATE_SAMPLE_SIZE` stay
private module constants. Geoguessr and Dateguessr get independent entries and, since the
`asset_rounds.py` split, independent copies of the underlying constants too - they're no longer
"sharing a default", just happening to default to the same numbers. MoreOrLess has an explicit
empty list so it still appears in `GET /admin/games/settings`.

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
never in a round's output at all — it surfaces only via `GameOut.target_person_id/name` (plus
`target_asset_count`/`target_birth_date`/`target_first_asset_date`, added for the rounds review
below), and only once the game is finished. `HiddenFaceOut.guess_person_id/guess_person_name` (what
the player guessed, frozen at guess time in `WhosThatPersonRound.guess_names` — roadmap #10) follow
the same `answered`-gated redaction as `person_id`/`person_name`.

This layer is well-disciplined. Note that it is defeated for Who'sThatPerson by the unauthenticated
thumbnail proxy (finding #4): the faces are hidden by a DOM overlay, not by altering the image.

## Rounds review (roadmap #10)

`GET /api/v1/games/{game_id}` already returns every round of a finished game, redacted exactly as
above — the post-game "Ver rondas"/"Ver juego" review is a pure GET + render, no new endpoint per
game. `GamesService._load_game`'s existing ownership check (`owner`/`user_id` match, else
`GameOwnershipError`/`GameNotFoundError`) is inherited for free.

The one new endpoint is `GET /api/v1/config` (`api/api.py`, public, unauthenticated, no rate limit —
static config, touches neither the DB nor Immich): returns `{"immich_external_url": ...}`, the
frontend's only way to build a "Ver en Immich" deep link. It's `Settings.immich_public_url`
(`IMMICH_EXTERNAL_URL`, falling back to `IMMICH_SERVER_URL` if unset — see the Configuration table
below), never `IMMICH_SERVER_URL` directly: that variable is how the *backend* reaches Immich (often
an internal Docker host in `docker-compose.app.yml`), not a URL a browser can open.

## Daily games (roadmap #G)

Wordle-style: the same content for every player each day, one attempt, its own leaderboard. Full
design in `docs/TODO/DAILY-GAMES.md`; summary here.

Each game implements the daily side of itself as its own `games/<name>/daily.py`, conforming to
`games/daily.py`'s `DailySupport` contract (a Protocol three top-level functions satisfy structurally -
the module itself is the "instance", not a class): `build_spec(mode, immich_service, settings)`,
`exclusion_ids(spec)`, `game_kwargs(mode, spec, settings, *, rounds_played, immich_service,
ml_service)`. `services/game_registry.py`'s `GAMES` registry maps `(game_type, mode)` to a
`GameSpec` with a `daily` field pointing at that game's `daily.py` module - the single dispatch
point both `services/games_service.py` and `services/daily_service.py` read (it can't live inside
either of those two modules, since `games_service.py` already depends on `daily_service.py` to
delegate challenge generation, and the reverse import would cycle).

A **challenge** (`daily_challenges`) is content, shared and immutable - generated lazily by
`DailyService.get_or_create_challenge` on the first "Jugar daily" of the day for a mode, via
`INSERT ... ON CONFLICT DO NOTHING` + re-`SELECT` (no locking - whichever request's insert lands
first wins, the other just reads it back). Each game's `build_spec()` drives a real, throwaway
instance of that mode's own game class through its own `start()`/`create_next_round()` - the same
picking logic a normal game uses - rather than reimplementing it; only the content
(`EntitySnapshot`/`AssetSnapshot`/`PersonSnapshot`/`HiddenFace`) is kept. A `no_repeat_days` window
(every mode except MoreOrLess) excludes ids from recent challenges' specs - each game's own
`exclusion_ids()` decides which ids from a spec count, and `DailyService` unions them across the
window via a small `_ExcludingImmichService` wrapper; if exclusion leaves nothing, generation
retries once without it. MoreOrLess's `exclusion_ids()` always returns an empty set - it
deliberately never gets cross-day exclusion (decision [F] in `docs/TODO/DAILY-GAMES.md`), which
this makes automatic rather than a special case in `DailyService` itself.

A **daily game** (`games.daily_challenge_id` set) is state, per player, instantiated from a
challenge by `GamesService.create_daily_game` - checked against `daily_configs.enabled`
(`DailyNotEnabledError`) and the caller's existing game for that challenge
(`DailyAlreadyPlayedError`, backed by two partial unique indexes on `games` since Postgres never
treats two NULLs as equal). A daily game is the *exact same game class* a normal game uses (no
`Daily*Game` subclasses - that used to be `games/daily_scripted.py`, since deleted) - only its
content source differs, via each game's own `game_kwargs()`: MoreOrLess's `ScriptedCandidateProvider`
replays a pre-generated chain (mirroring its normal `CandidateProvider` seam); Geoguessr/Dateguessr/
WhosThatPerson each get a `ScriptedContent` implementing that game's own `<Name>Content` protocol
(mirroring their normal `LiveContent`); `ImmichdleGame.start()` takes an optional `target` (no
content protocol needed - Immichdle's only precomputed content *is* the target, guesses stay live
either way). Everything else - scoring, streaks, `play_round`, persistence - is the exact same
machinery every game already uses; `GamesService._row_to_game` just branches on
`daily_challenge_id` and, if set, resolves that game's `daily.py::game_kwargs()` through the
`game_registry.GAMES` lookup instead of the normal live-settings path.

**World separation**: daily games are filtered out of `get_personal_records`, `get_leaderboard`,
`get_current_game`, and `_abandon_active_games` (`daily_challenge_id IS NULL` on each) - a daily
never competes with normal play and never abandons/is abandoned by a normal game of the same mode.
`get_recent_games` is the one exception (personal history, not a comparison) - it flags daily rows
with `is_daily` instead of filtering them.

Endpoints (`api/daily_api.py`, mounted at `/daily`): `GET /daily` (status per enabled mode, never
generates a challenge), `POST /daily/{type}/{mode}/games` (create/consume today's attempt),
`GET /daily/{type}/{mode}/leaderboard?date=` (one specific day, not a rolling window - see
`GamesService.get_daily_leaderboard`). Admin config (`api/admin_daily_api.py`, mounted at
`/admin/daily`): per-mode `enabled` + daily-only settings (`services/daily_settings.py`'s
`DAILY_SETTING_SPECS` - the normal `GAME_SETTING_SPECS` plus `no_repeat_days`, or `chain_length` for
MoreOrLess). `reset` clears only the value overrides; `enabled` is untouched.

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
| `IMMICH_EXTERNAL_URL` | Public URL the *browser* opens for "Ver en Immich" (roadmap #10) — served via `GET /config`. Optional; falls back to `IMMICH_SERVER_URL` if unset. |
| `JWT_SECRET` / `JWT_EXPIRE_DAYS` | This app's own sessions. |
| `ADMIN_EMAIL` | Account to promote to admin on startup. |
