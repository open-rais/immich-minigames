# Immich integration

How this app reads from an existing Immich deployment. Everything here is derived from
`backend/src/persistence/immich_tables.py`, `backend/src/services/immich_service.py`,
`backend/src/services/ml_service.py` and `backend/src/scripts/bootstrap_db_role.py` — those files
are the ground truth; this doc explains the *why*.

## Two ways to talk to Immich

Immich is reached through **two separate channels**, and which one to use is not a style choice:

| | Postgres (direct SQL) | Immich REST API |
|---|---|---|
| Used for | All game metadata: assets, people, faces, dates, GPS, face embeddings | Image bytes only |
| Why | Immich's API has no endpoint for "a random photo that has GPS and a thumbnail, excluding these 12 ids" — that is a query, and expressing it as one is far cheaper than paging the API | The image files live on disk, not in Postgres. The DB only stores paths, which this app has no filesystem access to |
| Auth | `DB_APP_USERNAME` / `DB_APP_PASSWORD` (scoped role, below) | `IMMICH_API_KEY` header (`x-api-key`) |
| Code | `ImmichService.get_assets` / `get_persons` / `search_persons` / … , `MLService` | `ImmichService.get_asset_thumbnail` / `get_person_thumbnail` |

**Never fetch image bytes via SQL, and never fetch metadata via the REST API.** Mixing the two is
the single easiest way to make this app slow or brittle.

### Thumbnails

Both thumbnail methods are thin proxies over Immich, returning `(bytes, content-type)` and letting
`httpx` errors propagate for `api/api.py::_proxy_thumbnail` to map:

- `GET {IMMICH_SERVER_URL}/api/assets/{id}/thumbnail?size=preview` — `size=preview` (~1440px JPEG)
  is deliberate: `thumbnail` (~250px) is too small for a fullscreen game, and `original` may be
  HEIC/RAW/video, which a browser `<img>` cannot render.
- `GET {IMMICH_SERVER_URL}/api/people/{id}/thumbnail` — the face crop.

One pooled `httpx.Client` with a 10s timeout is shared process-wide (`_get_http_client`,
`lru_cache`d) so a slow Immich cannot exhaust worker threads.

> ⚠️ These two endpoints are re-exposed by this app **without any authentication or scoping** —
> anyone who can reach the backend can enumerate any thumbnail in the Immich library, and in
> Who'sThatPerson a player can bypass the blacked-out faces entirely by opening the asset URL
> directly. See findings #2 and #4 in `docs/TODO/CODE-REVIEW.md`.

## The scoped DB role

The backend never uses Immich's admin Postgres credentials. `scripts/bootstrap_db_role.py` (run
once as the `db-init` compose service) provisions a dedicated role:

- **Immich's database: `SELECT` only**, granted via `GRANT pg_read_all_data`. Role membership
  rather than explicit `GRANT`s on `public`, for two reasons: it lives in `pg_auth_members` at the
  cluster level, so Immich's own database keeps zero references to this app in its dumps; and it
  doesn't go stale when an Immich upgrade adds a table.
- **This app's own database: full control** inside its `minigames` schema — the app creates and
  migrates its own tables there. A different database, so no query can span the two.
- `ALTER ROLE … IN DATABASE <immich> SET default_transaction_read_only = on` — a guard rail against
  programming mistakes, **not** a security boundary: the role can still `SET TRANSACTION READ
  WRITE` on itself. The real boundary is that only `SELECT` is ever granted.
- `REVOKE CREATE ON SCHEMA public FROM PUBLIC` — needed because Postgres 14 and earlier grant
  `CREATE` on `public` to everyone by default. Note this is a change to *Immich's* schema ACL
  affecting every role, not just ours (see finding #21). It names no role of ours, so unlike an
  explicit `GRANT` it restores cleanly anywhere.

Consequence for anyone writing queries: **you cannot `CREATE EXTENSION`, and you cannot write
anything to Immich's database at all.** This is why accent-insensitive search uses the builtin
`translate()` rather than `unaccent` (see below).

## Tables read

Only the columns actually used are declared, as SQLAlchemy Core `Table()`s (not ORM models — these
are Immich's tables, migrated by Immich).

**`asset`** — `id`, `ownerId`, `type` (`IMAGE`/`VIDEO`), `fileCreatedAt`, `localDateTime`,
`originalFileName`, `stackId`, `visibility`, `status`, `isFavorite`, `width`, `height`, `deletedAt`.

**`asset_exif`** — `assetId`, `latitude`, `longitude`, `city`, `state`, `country`.

**`asset_file`** — `id`, `assetId`, `type`. Used only to prove a thumbnail exists
(`type = 'thumbnail'`) before a game shows an asset.

**`person`** — `id`, `ownerId`, `name`, `birthDate`, `thumbnailPath`, `isHidden`.

**`asset_face`** — `id`, `assetId`, `personId`, `isVisible`, `deletedAt`, plus the detection box:
`imageWidth`, `imageHeight`, `boundingBoxX1/Y1/X2/Y2`.

**`face_search`** — not declared as a `Table()`; queried via raw SQL in `MLService` because of the
pgvector operator. Holds `faceId` and `embedding vector(512)`.

### Two gotchas that are easy to get wrong

**1. Native enum types.** `asset.status` and `asset.visibility` are real Postgres enums, not
varchars. They must be declared as `ENUM(..., create_type=False)`, otherwise comparing them to a
bound string fails with `operator does not exist: assets_status_enum = character varying`.

**2. `localDateTime` is not a normal timestamptz.** Immich stores the device-local wall clock in it
as a timestamptz whose *UTC rendering* is the local time (a 21:55 local shot is stored `21:55+00`).
So the true local calendar day is `CAST(timezone('UTC', "localDateTime") AS date)` — which is what
`get_assets` computes as `localDate`. Using `fileCreatedAt::date` instead silently shifts photos
taken late in the evening to the next day, which would make a correct Dateguessr guess score as
off-by-one. `domain/asset.py` exposes this as `local_date`, and Dateguessr grades against it.

### The standard eligibility filter

Every asset query starts from the same "this asset is real and showable" predicate:

```sql
status = 'active' AND visibility = 'timeline' AND "deletedAt" IS NULL
AND EXISTS (SELECT 1 FROM asset_file WHERE "assetId" = asset.id AND type = 'thumbnail')
```

And every person query filters `isHidden = false AND "thumbnailPath" <> ''`, plus `name <> ''`
whenever `named_only` (the default). Faces additionally require `isVisible AND "deletedAt" IS NULL`.
Hidden people are excluded everywhere *consistently* — a Who'sThatPerson round must never black out
a face the player cannot find in the search box.

## Query techniques worth knowing

**Random selection** — `ORDER BY random() LIMIT n`. Note `SELECT DISTINCT … ORDER BY random()` is
rejected by Postgres (ORDER BY expressions must appear in the select list under DISTINCT), which is
why `get_persons` and `get_random_asset_with_named_faces` use `GROUP BY` instead of `DISTINCT`.

**Geographic prefilter** — `near_km` is a lat/lon **bounding box**, not a circle: `lat ± r/111`,
`lon ± r/(111·cos(lat))`. Callers needing a true radius (Geoguessr's 500m extras rule) run an exact
haversine filter in Python afterwards. The box is just to keep the DB from scanning everything.

**Accent-insensitive search** — `search_persons` folds accents with the builtin
`translate(name, 'áéíóú…', 'aeiou…')` on both sides rather than the `unaccent` extension, because
the scoped role cannot `CREATE EXTENSION`. Matching is per-token *word-prefix*: each whitespace
token must satisfy `folded ILIKE 'tok%' OR folded ILIKE '% tok%'`, all ANDed. So "rai rodriguez"
matches "Raimundo Rodríguez" regardless of typed order, but not mid-word. User input is escaped for
LIKE wildcards first (`_escape_like`).

> Note: `get_persons`'s own `name_query` is a plain substring `ILIKE` that does **not** escape
> wildcards — an inconsistency with `search_persons`. See finding #14.

## Face similarity (Immich-ML)

The `MLSimilarity` clue in Immichdle does **not** call the `immich-machine-learning` service. It
reads the embeddings that service already computed and stored in `face_search.embedding`
(`vector(512)`, pgvector). Two reasons: the ML container is not reachable from the host in the dev
stack, and recomputing an embedding for a face Immich already indexed is pure waste.

```sql
SELECT MAX(1 - (fs_a.embedding <=> fs_b.embedding)) AS similarity
FROM asset_face fa
JOIN face_search fs_a ON fs_a."faceId" = fa.id
JOIN asset_face fb ON fb."personId" = :person_b_id AND fb."deletedAt" IS NULL AND fb."isVisible"
JOIN face_search fs_b ON fs_b."faceId" = fb.id
WHERE fa."personId" = :person_a_id AND fa."deletedAt" IS NULL AND fa."isVisible"
```

`<=>` is pgvector's cosine **distance**, so `1 - distance` is similarity in `0..1`.

This takes `MAX` over *every* face pair between the two people, unlike immich-power-tools' similar
faces query which compares one representative face each. The reason is the clue's purpose: catching
family resemblance. A single off-angle photo of one person would undersell a real sibling
resemblance, and the clue would read as noise. The cost is that it is a full cross join of both
people's faces — fine for a home library, potentially slow for someone with hundreds of faces per
person (see finding #16).

## Dev instance

`docker-compose.yml` at the repo root stands up a dev Immich (server + ML + Postgres + Redis) to
develop against. It does **not** include this app's own backend/frontend — those are
`docker-compose.app.yml`.

The project owner runs this locally with real test data: photos uploaded, people recognized (some
named, some not, some with birthdays), assets spread across several distinct locations, and at
least one location cluster of 15-24 photos (which is why Geoguessr enforces a 50km minimum
separation between rounds). Exact counts are intentionally not recorded here — they drift with
every upload, and no code should depend on a specific number.
