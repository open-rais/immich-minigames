# Backend

FastAPI app in `backend/src/`. Run: `cd backend && uv run uvicorn main:app --app-dir src --port 8000`
(needs `alembic upgrade head` once first). Tests: `cd backend && uv run pytest` (691 passing, 13
skipped, as of 2026-08-20).

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
| `UnsupportedGameError`, `DuplicateGuessError`, `InvalidGuessError`, `UnknownGameSettingError`, `InvalidGameSettingValueError`, `InvalidInviteError`, `InvalidReportReasonError` | 400 |
| `InvalidCredentialsError`, `UnauthorizedError` | 401 |
| `GameOwnershipError` | 403 |
| `GameNotFoundError`, `DailyNotEnabledError`, `InviteNotFoundError`, `ReportNotFoundError` | 404 |
| `RoundNotPendingError`, `DailyAlreadyPlayedError`, `JobAlreadyRunningError`, `EmailAlreadyExistsError`, `UsernameAlreadyExistsError` | 409 |
| `IncompleteGuessError`, `NotEnoughContentError` | 422 |
| `RateLimitExceeded` (slowapi) | 429 |

Adding a game exception means adding one line in `main.py`, not a try/except in a route.

> The handler serializes `str(exc)` straight into `{"detail": ...}`, and the frontend renders that
> string to the user verbatim.

## The game abstraction

`games/base.py` defines the contract every minigame implements.

**`BaseRound`** — holds `id`, `game_id`, `round_index`, `shown_entities` (ids already used, so
later rounds don't repeat them), `guess`, `score_delta`. Implements:
- `calculate_score(settings)` → the score delta for this round's guess
- `to_payload()` / `from_payload(...)` → the JSONB round trip

**`BaseGame`** — holds `id`, `game_type`, `mode`, `score`, `rounds`, `finished`, `_settings`,
`daily_challenge_date`. `current_round` is `rounds[-1]`. The shared loop is `play_round(guess)`:

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
scored: **Immichdle** (the guess is a person or album id - depending on mode - that must be
validated and turned into clues; the override itself lives once in `games/immichdle/game.py`'s
shared `BaseImmichdleGame`, with `PersondleGame`/`AlbumdleGame` each only filling in *how* to
resolve a guess) and **Who'sThatPerson** (validates the guess covers exactly the round's hidden
faces).

### Per-game rules

| Game | Ends when | Score |
|---|---|---|
| MoreOrLess | First wrong guess | +1 per correct round (a tie counts as correct) |
| Geoguessr | 5 rounds | `exp_decay_score(km)`, max 5000, flat within 1km, decay 1500km |
| Dateguessr | 5 rounds | Same curve on days: flat 0, decay 500 days |
| Immichdle | Correct guess, or score hits 0 | Starts at 100, −5 per wrong guess |
| Who'sThatPerson | 15 people asked (across variable-size rounds) | Combo streak by person; any miss in a round zeroes the incoming streak *before* scoring |
| Timeline | First wrong guess (or `max_cards`/library exhausted, which end it as a win) | +1 per correctly inserted card (a within-tolerance slot counts as correct) |

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

Alembic owns the schema (`backend/alembic/versions/`, currently 0001–0014); `docker-entrypoint.sh`
runs `alembic upgrade head` on every container start, and `db-init` runs it too — as the app role,
so the tables end up owned by the role that later has to `ALTER` them. `init_db`/`reset_db` in
`persistence/base.py` exist only for tests.

| Table | Notes |
|---|---|
| `games` | `user_id` (**NOT NULL** FK → `users`, since roadmap #H, F4 — login is mandatory, so every game has an owning account; the earlier anonymous `owner` string column is gone), `game_type`, `mode`, `score`, `finished`, `abandoned`, `daily_challenge_id`, `created_at`. Indexed on `(user_id, game_type, mode)`. |
| `rounds` | `game_id` FK, `round_index`, `score_delta` (null until answered), `payload` JSONB. Unique on `(game_id, round_index)`, which also provides the FK index Postgres doesn't create automatically. |
| `users` | `email`/`username` unique, `password_hash` (argon2), `skin_person_id` (deliberately **not** a FK — it points into Immich's database, which foreign keys cannot span), `is_admin`, `password_changed_at` (session-revocation marker, see § Auth), `created_at`. |
| `invites` | Roadmap #H, F1. `token_hash` (SHA-256, never the raw token), `kind` (`'invite'` \| `'password_reset'`, one table for both), `used_at`, `expires_at`, `user_id` (nullable — set once consumed, or always for a password-reset invite). Consumed via a single atomic `UPDATE ... RETURNING`. |
| `game_settings` | `(game_type, mode)` PK, `values` JSONB. One row per (game type, mode); a missing row or key falls back to the module constant. |
| `legacy_import` | Marker written by the one-time move out of Immich's database. Its presence means that copy committed — see below. |
| `person_face_embedding_cache` | `person_id` PK, `embedding vector(512)`, `face_count`, `embedding_count`, `computed_at`. Caches Persondle's `MLSimilarity` clue's per-person representative embedding (average across that person's visible faces) - see `docs/ARCHITECTURE/IMMICH.md`'s "Face similarity" section. The only own table with a non-JSON/UUID/text column type, hence `persistence/ml_cache.py`'s hand-rolled `Vector` SQLAlchemy type instead of a plain `mapped_column`. `embedding_count` (migration `0013`, roadmap #15) is how many vectors actually went into `embedding` - equal to `face_count` for persons today, kept as its own column so the incremental update (`services/ml_service.py`) has a real denominator without assuming the two coincide. `computed_at` (also `0013`) is `timestamptz`, not "when written" - it's the watermark the average is valid *as of*, taken before reading any vector, compared against Immich's own `updatedAt` columns on a different Postgres instance. |
| `album_embedding_cache` | Roadmap #14. `album_id` PK, `embedding vector(512)`, `asset_count`, `embedding_count`, `computed_at`. Caches Albumdle's `Similarity` clue's per-album representative CLIP embedding (average across that album's assets, from Immich's `smart_search` table - not face-based) - see `docs/ARCHITECTURE/IMMICH.md`'s "Album similarity" section. Reuses `persistence/ml_cache.py`'s `Vector` type rather than a second hand-rolled one. `embedding_count` is nullable here (unlike the person table) - it genuinely differs from `asset_count` (the average only counts eligible assets with a `smart_search` row), and existing rows from before migration `0013` have no way to know their true value; `NULL` means exactly that, and forces a full recompute the next time the row is touched. |
| `daily_configs` | Roadmap #G. `(game_type, mode)` PK, `enabled` bool, `values` JSONB - whether a mode is in the daily rotation plus its daily-only setting overrides. |
| `daily_challenges` | Roadmap #G. `id` PK, unique `(challenge_date, game_type, mode)`, `spec` JSONB (the pre-generated shared content), `settings` JSONB (frozen effective settings for that day). `games.daily_challenge_id` (nullable FK, one partial unique index on `(daily_challenge_id, user_id)` for "one attempt per player") points into this. |
| `reports` | Roadmap #N (see § Metadata reporting below). `entity_type` (`'asset'`\|`'person'`\|`'album'`), `entity_id` (**not** a FK — points into Immich's database), `reason`, `note` (nullable, ≤200 chars), `user_id` FK, `solved`, `solved_at`. A resolved report is never deleted (`solved` just flips), so it doubles as history. Partial unique index on `(user_id, entity_type, entity_id, reason) WHERE NOT solved` makes a duplicate open report a no-op while still letting the same thing be reported again after a prior report was resolved. |

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

This app's own accounts, entirely separate from Immich's users. Login is mandatory (roadmap #H) —
there is no anonymous play; every game, record and leaderboard entry belongs to a real account.

- **Passwords**: argon2 (`argon2-cffi`'s `PasswordHasher`).
- **Session**: stateless JWT (HS256, `sub` = user id, `iat`/`exp` = now / now + `JWT_EXPIRE_DAYS`),
  in an httpOnly `access_token` cookie, `SameSite=Lax`, `Secure` from `settings.cookie_secure`
  (`false` by default — the dev stack and `docker-compose.app.yml` both serve plain HTTP; set to
  `true` behind a TLS-terminating reverse proxy).
- **Revocation without a session table**: `users.password_changed_at` + the JWT's `iat` claim.
  `AuthService.get_user_from_token` rejects any token whose `iat` predates the account's last
  password change, so changing a password logs out every other device without needing
  server-side session storage. `PATCH /auth/me/password` (self-service, requires the current
  password) and admin-initiated password reset (`POST /admin/users/{id}/password-reset` +
  `POST /auth/reset-password`, single-use token) both set it.
- **Logout** clears the cookie. A token copied before logout stays valid until it expires (the
  revocation mechanism above only fires on a password change, not on logout). Rotating
  `JWT_SECRET` invalidates every session at once.
- **Registration is invite-only** (`invites` table, `kind` discriminates `'invite'` vs
  `'password_reset'`, SHA-256-hashed tokens, consumed via one atomic `UPDATE ... RETURNING`) —
  except the very first account on a fresh install, which can register freely unless
  `INITIAL_INVITE_TOKEN` is set (then that token stands in for an invite, once).
- **Default-deny middleware** (`api/auth_middleware.py`): every request needs a valid session
  cookie except an exact allow-list (`/auth/login`, `/auth/register`, `/auth/reset-password`,
  `/auth/logout`). A middleware rather than a per-route dependency, so a route added later and
  forgotten stays protected by construction. It resolves `request.state.user` once per request and
  shares its DB session (`request.state.db_session`) with the rest of the request via
  `api/deps.py::get_db_session`, so a route mutating the user (e.g. changing the password) commits
  on the same session the middleware already loaded it on.
- **Rate limiting** (`api/rate_limit.py`, slowapi + the `limits` library it wraps, in-memory by
  default — `RATE_LIMIT_STORAGE_URI` for a shared store across more than one backend process):
  keyed by session-or-IP, not a trusted proxy header (`X-Real-IP`/`X-Forwarded-For` are never
  read) — a logged-in request's budget follows the account (decoded from the JWT locally, no DB
  round-trip), an unauthenticated one falls back to the raw socket peer. `register` and
  `change_password` (3/min, 5/min) use this default key. `login` additionally enforces a 5/min
  limit keyed by the submitted *email* specifically (checked inside the handler, since slowapi's
  decorator can't read the request body) — an IP/session-only limit alone can't bound "many guesses
  against one account", since an attacker can trivially vary either. `register` itself is the one
  route that overrides the key back to plain IP: it's what *mints* a session, so keying its own
  limit by session would let every successful call escape into a fresh, unlimited budget.

`get_current_user` (`api/auth_api.py`) reads the already-resolved `request.state.user` — routes
still declare `Depends(get_current_user)`, only where the identity comes from changed once the
middleware started resolving it up front.

## Admin feature

Five pieces, referenced in comments as points #1–#5:

1. **Promotion** (`services/admin_bootstrap.py`) — on every backend startup, if `ADMIN_EMAIL`
   matches an already-registered account, its `is_admin` flips to true. Promotion only: it never
   creates an account. Idempotent, so running it on every `--reload` is safe.
2. *(Frontend admin entry point — the `/admin` route and its UserMenu link.)*
3. **User admin** (`api/admin_api.py`) — an `is_admin` account can list all users and edit any
   user's full name / username / skin. Reuses `auth_schemas.py`'s DTOs applied to an arbitrary
   `user_id`.
4. **Game settings** (`api/admin_games_api.py`, `services/game_settings.py`) — per-`game_type`
   overrides of the scoring/difficulty constants each game module defines.
5. **Embedding cache worker** (roadmap #15; `services/embedding_jobs.py`, `api/admin_workers_api.py`)
   — lets an admin see how much of `person_face_embedding_cache`/`album_embedding_cache` is warm
   and kick off a background (re)compute run. `EmbeddingJobRunner` is a single-job-at-a-time
   in-memory registry (no persistence, no Redis - state is deliberately disposable, the job is
   idempotent and re-runnable) running on a plain daemon `threading.Thread`, not asyncio, since
   every query this app makes is already synchronous SQLAlchemy. It takes the same `MLService`
   instance the rest of the app shares via `api/deps.py::get_ml_service()` rather than constructing
   its own - `get_app_engine`/`get_immich_engine` aren't memoized themselves, so a second bare
   `MLService()` would silently open a second pair of connection pools. `main.py`'s `lifespan`
   cancels and joins it (bounded by a timeout) on shutdown, so a long-running job doesn't hang a
   restart. Two request-response endpoints (`GET`/`POST /admin/workers/embeddings`) plus
   `DELETE` to cancel; `POST` raises `JobAlreadyRunningError` (409) if one is already in flight,
   caught nowhere - it propagates to `api/error_handlers.py` like every other domain exception.

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
> `Infinity`/`NaN`.

## Request lifecycle: playing a round

`POST /api/v1/games/{game_id}/rounds/{round_id}` is the most involved path:

1. `get_current_user` (an `api/deps.py` dependency) resolves the account from the session's httpOnly
   JWT cookie, already validated by the default-deny `auth_middleware`.
2. `games_service.get_game(game_id, user)` → `_load_game`: fetch `GameModel`, compare `user.id` to
   `user_id` (raise `GameOwnershipError` on mismatch), look up the `(game_type, mode)` spec, rebuild
   every round via `from_payload`, construct the game with live admin settings.
3. `parse_guess(existing_game.current_round, body)` picks the right pydantic schema from
   `_ROUND_SPECS` keyed on the round's concrete class, validates, and converts to a domain guess.
   The client never states its own `game_type` — `game_id` already fixes it, so there is nothing to
   disagree about.
4. `play_loaded_round` checks the round is genuinely the pending one (`RoundNotPendingError`),
   delegates to the game's `play_round`, then persists: update the game's score/finished, write the
   answered round's `score_delta` + `payload`, and insert the newly created round if there is one.
5. `PlayRoundOut.from_answered` serializes, redacting anything that would spoil an unanswered round.

> Step 4 is not concurrency-safe: two simultaneous requests for the same round can both pass the
> pending check.

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
thumbnail proxy: the faces are hidden by a DOM overlay, not by altering the image.

## Rounds review (roadmap #10)

`GET /api/v1/games/{game_id}` already returns every round of a finished game, redacted exactly as
above — the post-game "Ver rondas"/"Ver juego" review is a pure GET + render, no new endpoint per
game. `GamesService._load_game`'s existing ownership check (`user_id` match, else
`GameOwnershipError`/`GameNotFoundError`) is inherited for free.

The one new endpoint is `GET /api/v1/config` (`api/api.py`, public, unauthenticated, no rate limit —
static config, touches neither the DB nor Immich): returns `{"immich_external_url": ...}`, the
frontend's only way to build a "Ver en Immich" deep link. It's `Settings.immich_public_url`
(`IMMICH_EXTERNAL_URL`, falling back to `IMMICH_SERVER_URL` if unset — see the Configuration table
below), never `IMMICH_SERVER_URL` directly: that variable is how the *backend* reaches Immich (often
an internal Docker host in `docker-compose.app.yml`), not a URL a browser can open.

## Daily games (roadmap #G)

Wordle-style: the same content for every player each day, one attempt, its own leaderboard.

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
deliberately never gets cross-day exclusion, which
this makes automatic rather than a special case in `DailyService` itself.

A **daily game** (`games.daily_challenge_id` set) is state, per player, instantiated from a
challenge by `GamesService.create_daily_game` - checked against `daily_configs.enabled`
(`DailyNotEnabledError`) and the caller's existing game for that challenge
(`DailyAlreadyPlayedError`, backed by two partial unique indexes on `games` since Postgres never
treats two NULLs as equal). A daily game is the *exact same game class* a normal game uses (no
`Daily*Game` subclasses - that used to be `games/daily_scripted.py`, since deleted) - only its
content source differs, via each game's own `game_kwargs()`: MoreOrLess's `ScriptedCandidateProvider`
replays a pre-generated chain (mirroring its normal `CandidateProvider` seam); Geoguessr/Dateguessr/
WhosThatPerson/Timeline each get a `ScriptedContent` implementing that game's own `<Name>Content`
protocol (mirroring their normal `LiveContent`); `PersondleGame.start()`/`AlbumdleGame.start()` each
take an optional `target` (no content protocol needed - Immichdle's only precomputed content *is*
the target, guesses stay live either way; `games/immichdle/daily.py` dispatches both modes' own
`build_spec`/`game_kwargs` by `mode`, mirroring how `games/more_or_less/daily.py` dispatches its
three modes' `CandidateProvider`s from one shared `daily.py`). Timeline's `build_spec()` is chain-shaped like MoreOrLess's (it drives
`create_next_round()` directly in a loop, since `has_next_round()` depends on a guess that a
throwaway spec-generation game never makes) but its `exclusion_ids()`/`no_repeat_days` behave like
every other content-protocol game's, since its cards are concrete assets, not a value chain - the
first mode that needs both a `chain_length` cap *and* a `no_repeat_days` window at once. Everything else - scoring, streaks, `play_round`, persistence - is the exact same
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

## Metadata reporting (roadmap #N)

A player flags a person/album/asset as having bad metadata from the "⋯" menu already on every
round-review row; an admin reviews and resolves. Three endpoints, all in `api/reports_api.py`
(player) / `api/admin_reports_api.py` (admin):

| Endpoint | Auth | What |
|---|---|---|
| `POST /reports` | any logged-in account | Create - one row per selected reason, `ON CONFLICT DO NOTHING` against the partial unique index above, so reporting the same thing twice while still open is silent. |
| `GET /reports/context?entity_type=&entity_id=` | any logged-in account | What the report modal shows above the checkboxes (name/birth date for a person; lat/long/city/country/date/named-people-in-photo for an asset; name/date range for an album) - `null`, not 404, when the entity no longer exists in Immich, since reporting itself never depends on that. |
| `GET /admin/reports?entity_type=&solved=&offset=&limit=`, `GET /admin/reports/counts`, `PATCH /admin/reports/{id}` | `is_admin` | The review panel's three paginated lists (one per `entity_type`), an open-report count per type, and marking resolved/unresolved. Batch-resolves entity names (`ImmichService.get_persons/get_albums/get_assets(ids=...)`) and usernames (`AuthService.usernames_for`) per page, not per row. |

`ReportsService` (`services/reports_service.py`) owns persistence and stays decoupled from Immich -
`reason`/`entity_type` are plain strings on its own methods, never the `games/report_spec.py`
enums. `games/report_spec.py` is contract-only (`ReportEntity`, `ReportReason`,
`REASON_ENTITY: dict[ReportReason, ReportEntity]`) - `POST /reports` validates a submitted reason
against it (`InvalidReportReasonError`, 400, not the 422 a pydantic validator would give, since
this is a business rule, not a malformed request) before any row is written.

**Round generation excludes what's reported; searching/guessing never does.** Each game declares
its own `games/<name>/reports.py::REPORT_EXCLUSIONS: dict[mode, frozenset[ReportReason]]` -
`games/reports_registry.py` assembles all of them into one `(game_type, mode)`-keyed dict, mirrored
by a unit test that fails if a `games/registry.py::GAMES` entry has no matching declaration.
`ReportsService.filter_for(immich_service, game_type, mode)` looks that up, and — only if there's
at least one open report for a relevant reason — wraps `immich_service` in
`_ReportsExcludingImmichService` (composition, not a subclass, same shape as
`_ExcludingImmichService` above): `GameFactory.kwargs_for` and
`DailyChallengeService._build_spec` both wrap once, up front, so the common case (no open reports)
costs one query and nothing else. Two rules make "reported but still guessable" true:

- **`ids=` bypasses filtering entirely.** `get_persons`/`get_albums`/`get_assets`'s `ids=` always
  means "resolve these concrete ids" (a guess lookup - Immichdle, Who'sThatPerson's guessed-name
  freeze; a display lookup - the admin panel's batch name resolution, `GET /reports/context`),
  never "sample the pool". The wrapper only widens `exclude_ids` when `ids is None`; search
  endpoints (`/persons/search`, `/albums/search`) aren't touched by the wrapper at all, so they're
  unaffected either way.
- **A sampling call that comes back empty because of the exclusion retries once without it.** A
  report is a best-effort nudge, not a hard guarantee that could otherwise stall a game mid-run
  because its whole remaining pool happens to be reported. Who'sThatPerson is the one case that
  needs a person, not just an asset, excluded mid-pool: `get_random_asset_with_named_faces` gained
  `exclude_person_ids` for this (see `docs/ARCHITECTURE/IMMICH.md`) - applied to both of that
  query's statements, same as its existing `isHidden` filter.

For the daily flow, the reports wrapper nests **outside** `_ExcludingImmichService`'s no-repeat
window in `DailyChallengeService._build_spec` - if the reports wrapper's own empty-result fallback
retries without report-exclusion, it still goes through the window wrapper underneath and so still
respects it; the reverse nesting would let a report-emptied pool silently drop the window too. A
daily challenge already generated is unaffected either way - `ScriptedContent`/
`ScriptedCandidateProvider` replay the frozen `spec` JSONB and never call Immich at all, so the
wrapper has nothing to intercept there.

## Push notifications (roadmap #O)

Web Push (RFC 8291/8292, VAPID) - no third-party account or SDK involved. The browser itself picks
which push service a subscription goes through (Chrome/Edge → Google's, Firefox → Mozilla's,
Safari → Apple's); VAPID is just this backend proving to that service it's the legitimate sender,
via a key pair it generates and owns (`scripts/generate_vapid_keys.py`). All three
`VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/`VAPID_CONTACT_EMAIL` unset (the default) turns the whole
feature off - `GET /config`'s `push_public_key` comes back `null` and the frontend hides its
settings section entirely, gated on all three together (not just the public key) so a partial
config can't leave the UI offering something that can subscribe but can never send.

`services/notifications/` (mirrors `services/immich/`'s facade-over-a-package shape):

| Module | Job |
|---|---|
| `__init__.py` | `NotificationService` facade - preference CRUD, subscribe/unsubscribe, and `send_to_user` (the per-device send-and-record loop both the manual test and the scheduler share). |
| `sender.py` | Wraps `pywebpush`. A `requests.Session` subclass forces `allow_redirects=False` - pywebpush sends over `requests`, not `httpx`, so this is where the "don't follow a push-service redirect" mitigation actually lives, not in a client constructor arg. Maps 404/410 to "delete the subscription", everything else to "transient, just count it". |
| `endpoint_safety.py` | The SSRF guard for `POST /notifications/subscriptions` - that endpoint takes a URL from the client that the backend will later POST to, so without this an authenticated user could register an internal address and turn the backend into a proxy into its own network. Order: scheme (`https` only) → host allowlist (`PUSH_ALLOWED_HOSTS`, wildcard-subdomain patterns) → DNS resolution, rejecting private/loopback/link-local/multicast results. |
| `content.py` | What's notifiable *today* - `todays_birthdays`/`todays_album_anniversaries` against Immich, installation-wide facts computed once per tick, not per user. Excludes people with an open `person_birth_date` report; no equivalent exclusion exists for albums (no `ReportReason` currently captures "this album's date is wrong" - adding one is a reports-feature change of its own, left out on purpose). |
| `messages.py` | ~10 strings × 4 languages, duplicated by hand from `frontend/src/i18n/locales/*.json` rather than shared - the payload is composed here because it travels to a *closed* app (the service worker has neither `localStorage` nor i18next), and it's cheap enough that the coupling a shared source of truth would add isn't worth it. |
| `schedule.py` | Pure decision functions, no I/O - `active_kinds_for_tick(now)` (which of the four fixed times of day, if any, `now` falls within a 60-minute grace window of) and `decide_daily_notification(...)` (the streak rule table below). `now`/pre-fetched data always come in as parameters, same "as of a date" convention `DailyGamesService.get_daily_status` already uses - testable with literal values, no freezegun or thread involved. |
| `runner.py` | The scheduler thread - ticks every 60s, mirrors `services/embedding_jobs.py`'s thread/event shape with one real difference: `embedding_jobs.py` only ever starts on-demand, from an admin route; this one starts unconditionally in `main.py`'s `lifespan` (a no-op if push isn't configured), because it's a real schedule, not tied to any request. |

**The streak rule** (`schedule.decide_daily_notification`) decides between two mutually exclusive
daily notifications per user per day - "new daily's up" at 10:00, or "you're about to lose a
streak" at 21:00, never both. With `H` = enabled daily modes, `U ⊆ H` = not finished today,
`racha(m)` = consecutive days played **through yesterday** (not today - see below): 10:00 fires
only if the user has no active streak anywhere in `H`; 21:00 only if they do, `U ≠ ∅`, and either
names the largest at-risk streak in `U` (ties broken by `games/registry.py`'s declaration order,
not randomly) or, if every streaked mode was already played today, sends a generic "today's games
are ending" instead.

**Through yesterday, never through today.** `persistence/games_repository.py::daily_streaks`
already counts a streak through **today** (right for the leaderboard badge it backs), and
`daily_streaks_by_mode` (same walk, generalized over every mode/user in one query) takes `as_of` as
an explicit parameter rather than hardcoding either - the scheduler always passes `today - 1`.
Reusing "through today" here would make every mode not yet played today read as streak 0 and
collapse the whole rule table, since a mode played every day including today and one whose streak
just started today would look identical.

**Idempotency and multi-process safety** - two different mechanisms for two different failure
modes:
- *Restart mid-window*: `notification_deliveries` (`user_id`, `kind`, `day`), unique-indexed -
  `INSERT ... ON CONFLICT DO NOTHING ... RETURNING id` marks a delivery **before** sending, and a
  restart re-processing an already-marked day sends nothing twice. Checked via `RETURNING`, not
  `rowcount` - this driver reports `rowcount = -1` for `ON CONFLICT DO NOTHING` regardless of
  whether the conflict actually happened, which silently makes every insert look skipped if you
  trust it.
- *More than one backend process*: `pg_try_advisory_lock` (non-blocking - a tick that loses the
  race just skips this minute) around the whole tick, keyed by hashing a `"notif-tick"`-prefixed
  string distinct from `daily_challenge_service.py`'s `"daily:..."` keys, so the two locks can
  never collide. Unlike that service's `pg_advisory_xact_lock` (transaction-scoped, releases
  itself on commit), `pg_try_advisory_lock` is **session**-scoped - `runner.py` releases it with
  `pg_advisory_unlock` explicitly, in the same session that acquired it, before that session's
  connection goes back to the pool. Skipping that would leave the lock held by whichever unrelated
  session happens to reuse the same pooled connection next.

**Time zone**: a single `TZ` per installation (`docker-compose.app.yml` passes it through; unset
means the container's own default, usually UTC), read implicitly by Python's `datetime.now()` -
there's no per-user time zone and no `Settings` field for it. This is a real footgun worth stating
plainly: `logging_setup.py`'s formatters always print a log line's own timestamp in **UTC**,
regardless of `TZ`, but the scheduler compares against **local** time - reading a time off a log
line and pasting it into a hand-test is silently off by the UTC offset. `NotificationRunner.start()`
logs the local time it's actually comparing against for exactly this reason.
`POST /admin/notifications/run-tick` (admin-only, optional `now=` query param) sidesteps the whole
question for testing - it simulates any local time directly, no clock-watching or `SLOT_TIMES`
edits required.

## Logging (roadmap #I)

Goal: answer "who did what, when, from
where" on an exposed instance — structured (JSON lines) to stdout, rotation left to Docker
(`json-file` + `max-size`/`max-file` in both compose files) rather than the app managing files or
integrating a concrete aggregator itself (same deployment-agnostic philosophy as auth — whoever
wants Loki/Grafana/etc. connects it externally, over the stdout already emitted).

Three loggers, stdlib `logging` + a hand-written JSON formatter (`logging_setup.py`) — no new
dependency:

- **`audit`** — account/security events (`audit.py`'s `audit(event, **fields)`), always INFO,
  never filtered by `LOG_LEVEL` (a quiet `LOG_LEVEL=ERROR` for app noise must not also silence
  security events). Emitted from the **services** where each fact actually happens and the data is
  on hand (`auth_service.py`, `invite_service.py`, `admin_bootstrap.py`) — not from routes or
  `main.py`'s exception handlers, which only see an already-generic exception. One exception:
  `admin_api.py::create_password_reset` emits its own `password_reset_created` in addition to
  `invite_service`'s generic `invite_created` — it has `target_user_id`, which `invite_service`
  has no reason to know. Never logs passwords, tokens in the clear (JWT/invite/reset), or
  authorization headers — enforced by `tests/test_audit.py`'s dedicated secrets test, which drives
  a real register → login → change-password → admin-reset → reset-password sequence and asserts
  none of the plaintext values used anywhere appear in any emitted log line.
- **`access`** — one line per request (`api/request_log_middleware.py`, the outermost middleware so
  it also catches the 401s `AuthMiddleware` cuts before a route runs), replacing uvicorn's own
  access log (silenced in `logging_setup.py` — otherwise every request would log twice): method,
  path, status, duration, and the caller's `user_id`/`username` when authenticated — uvicorn's
  default only ever logged the socket peer, useless for "which account did this" now that every
  route requires one.
- Everything else — ordinary `getLogger(__name__)` app logging, level controlled by `LOG_LEVEL`.

**Request context without threading it through every call site**: `api/request_context.py`
contextvars (`request_id`, `ip`, `forwarded_for`, `user`) are set once, by
`RequestLogMiddleware`/`AuthMiddleware`, and merged into *every* record by the formatters — an
`audit()` call never needs to know the request it's in. One propagation gotcha this relies on:
`BaseHTTPMiddleware`'s `call_next` runs the rest of the stack in a task that inherits a *copy* of
the calling context (downward propagation works), but nothing set further in flips back up to the
caller once that inner task returns — so the outer `RequestLogMiddleware` reads the authenticated
user off `request.state` (shared via the ASGI scope) rather than the `user` contextvar
`AuthMiddleware` set one layer in.

`LOG_FORMAT` (`console`, human-readable — the default for bare `uv run uvicorn` dev; `json` — one
object per line, what the Docker image's own `Dockerfile` defaults to via `ENV LOG_FORMAT=json` so
every packaged install emits it without touching `.env`) picks the formatter; `LOG_LEVEL` only
gates ordinary app logging. Querying: `docker logs <container> | jq 'select(.logger == "audit")'`
and variants — see `docs/INSTALL.md` § *Viewing the audit logs*.

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
| `IMMICH_EXTERNAL_URL` | Public URL the *browser* opens for "Ver en Immich" (roadmap #10) — served via `GET /config`. Falls back to `IMMICH_SERVER_URL` only when genuinely **unset** (`None`); set to an explicit empty string to get `null` back instead (no link, no leak of an internal-only `IMMICH_SERVER_URL` to the browser) — see `Settings.immich_public_url`. |
| `JWT_SECRET` / `JWT_EXPIRE_DAYS` | This app's own sessions (see § Auth). `JWT_SECRET` is the real perimeter now that login is mandatory — generate it with `openssl rand -hex 32`. |
| `COOKIE_SECURE` | Marks the session cookie `Secure` (HTTPS-only). `false` by default (dev stack / `docker-compose.app.yml` both plain HTTP) — set `true` behind a TLS-terminating reverse proxy. |
| `ADMIN_EMAIL` | Account to promote to admin on startup. |
| `INITIAL_INVITE_TOKEN` | Roadmap #H, F1. Stands in for an invite code for the very first account on a fresh install (registration is otherwise invite-only, see § Auth). Unset means the first registration is free — a one-shot door that closes itself the moment any account exists, regardless of this setting. |
| `RATE_LIMIT_STORAGE_URI` | Roadmap #H, F5. Backing store for `api/rate_limit.py`'s counters. `memory://` (default) — fine for this app's single-backend-container deployment; `redis://host:port` only matters if more than one backend process shares the same traffic. |
| `LOG_LEVEL` | Roadmap #I (see § Logging). Ordinary app logging only — `audit`/`access` always stay at INFO. |
| `LOG_FORMAT` | Roadmap #I. `console` (default for bare `uv run uvicorn`) or `json` (what the Docker image defaults to via its own `Dockerfile`, regardless of this file). |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CONTACT_EMAIL` | Roadmap #O (see § Push notifications). Generate a pair with `uv run python -m scripts.generate_vapid_keys`. All three unset (default) turns push off entirely. Rotating the private key invalidates every existing subscription, same as `JWT_SECRET` with sessions. |
| `PUSH_ALLOWED_HOSTS` | Roadmap #O. SSRF allowlist for `POST /notifications/subscriptions` — comma-separated, `*.` prefix matches any subdomain. Defaults to every major browser's push service; only add to it, never remove the restriction. |
| `TZ` | Roadmap #O. Not a `Settings` field — a bare OS/container env var Python's `datetime.now()` reads implicitly. What the four scheduled notification times are timed against; unset means the container's own default (usually UTC), not your local time. |
