"""Postgres queries over Immich's `album`/`album_asset` tables."""

from datetime import date
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.engine import Engine

from domain.album import Album
from persistence.immich_tables import album, album_asset, asset, asset_face, person

from ._rows import row_to_album
from ._text import word_prefix_conditions

# The standard "this asset is real and showable" predicate (docs/ARCHITECTURE/IMMICH.md's
# "standard eligibility filter") - every album-scoped query below joins through `asset` and
# applies this, because `album_asset` rows outlive Immich's soft-delete (deletedAt/status are set
# on `asset`, but the row isn't removed from `asset` or `album_asset` until the trash is emptied).
_ASSET_ELIGIBLE = (asset.c.status == "active") & (asset.c.visibility == "timeline") & asset.c.deletedAt.is_(None)


def get_albums(
    engine: Engine,
    *,
    ids: frozenset[UUID] | None = None,
    name_query: str | None = None,
    min_asset_count: int | None = None,
    randomize: bool = False,
    asset_count_weight: float | None = None,
    limit: int = 1,
    exclude_ids: frozenset[UUID] = frozenset(),
) -> list[Album]:
    """Non-deleted albums with their asset count - the data source for MoreOrLess's albumAssets
    mode (see games/more_or_less/album_assets.py) and Albumdle (games/immichdle/albumdle.py),
    mirroring get_persons' shape (ids/name_query/min_asset_count/randomize/asset_count_weight/
    limit/exclude_ids). An album with no assets still comes back (count 0) unless
    min_asset_count filters it out."""
    asset_count_agg = func.count(album_asset.c.assetId)
    asset_count = asset_count_agg.label("asset_count")

    stmt = (
        select(album.c.id, album.c.albumName, album.c.albumThumbnailAssetId, asset_count)
        .select_from(album.outerjoin(album_asset, album_asset.c.albumId == album.c.id))
        .where(album.c.deletedAt.is_(None))
        .group_by(album.c.id, album.c.albumName, album.c.albumThumbnailAssetId)
    )

    if ids is not None:
        stmt = stmt.where(album.c.id.in_(ids))
    if name_query:
        stmt = stmt.where(album.c.albumName.ilike(f"%{name_query}%"))
    if exclude_ids:
        stmt = stmt.where(album.c.id.notin_(exclude_ids))
    if min_asset_count is not None:
        stmt = stmt.having(asset_count_agg >= min_asset_count)

    if randomize and asset_count_weight:
        # Weighted random pick (Efraimidis-Spirakis: order by random()^(1/weight) desc) - same
        # technique get_persons uses for its own asset_count_weight (see that function's
        # comment); greatest(..., 1) avoids a division by zero for an album with 0 assets.
        weight = func.pow(func.greatest(asset_count_agg, 1), asset_count_weight)
        stmt = stmt.order_by(func.pow(func.random(), 1.0 / weight).desc())
    elif randomize:
        stmt = stmt.order_by(func.random())
    else:
        stmt = stmt.order_by(album.c.albumName)
    stmt = stmt.limit(limit)

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    return [row_to_album(row) for row in rows]


def search_albums(engine: Engine, query: str, *, offset: int = 0, limit: int = 3) -> list[Album]:
    """Albums matching every whitespace-separated token in `query` against a *word* in the album
    name - see ._text.word_prefix_conditions for the actual matching rule, applied here to
    `album.albumName` instead of `person.name`. Powers Albumdle's guess-input autocomplete."""
    token_conditions = word_prefix_conditions(album.c.albumName, query)
    if not token_conditions:
        return []

    asset_count = func.count(album_asset.c.assetId).label("asset_count")

    stmt = (
        select(album.c.id, album.c.albumName, album.c.albumThumbnailAssetId, asset_count)
        .select_from(album.outerjoin(album_asset, album_asset.c.albumId == album.c.id))
        .where(album.c.deletedAt.is_(None), *token_conditions)
        .group_by(album.c.id, album.c.albumName, album.c.albumThumbnailAssetId)
        .order_by(album.c.albumName)
        .offset(offset)
        .limit(limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    return [row_to_album(row) for row in rows]


def get_album_cover_asset_id(engine: Engine, album_id: UUID) -> UUID | None:
    """The asset whose thumbnail represents this album: Immich's chosen cover
    (album.albumThumbnailAssetId) if set, else this album's first asset. None if the album
    doesn't exist or has no assets at all - the caller (api/api.py's album thumbnail route)
    maps that to a 404. The actual image bytes are then served via images.get_asset_thumbnail."""
    with engine.connect() as conn:
        cover_id = conn.execute(select(album.c.albumThumbnailAssetId).where(album.c.id == album_id)).scalar()
        if cover_id is not None:
            return cover_id
        return conn.execute(select(album_asset.c.assetId).where(album_asset.c.albumId == album_id).limit(1)).scalar()


def get_album_first_asset_date(engine: Engine, album_id: UUID) -> date | None:
    """Local calendar day of this album's earliest eligible asset - same local-day expression
    get_person_first_asset_date uses. Powers Albumdle's first_asset_date clue. None if the album
    has no currently-eligible assets."""
    local_date = cast(func.timezone("UTC", asset.c.localDateTime), Date)
    stmt = (
        select(func.min(local_date))
        .select_from(album_asset.join(asset, asset.c.id == album_asset.c.assetId))
        .where(album_asset.c.albumId == album_id, _ASSET_ELIGIBLE)
    )
    with engine.connect() as conn:
        return conn.execute(stmt).scalar()


def get_album_last_asset_date(engine: Engine, album_id: UUID) -> date | None:
    """Local calendar day of this album's most recent eligible asset - twin of
    get_album_first_asset_date (func.max instead of func.min). Powers the report modal's album
    date-range context; nothing else needed a "last" date before this."""
    local_date = cast(func.timezone("UTC", asset.c.localDateTime), Date)
    stmt = (
        select(func.max(local_date))
        .select_from(album_asset.join(asset, asset.c.id == album_asset.c.assetId))
        .where(album_asset.c.albumId == album_id, _ASSET_ELIGIBLE)
    )
    with engine.connect() as conn:
        return conn.execute(stmt).scalar()


def get_albums_starting_on(engine: Engine, month: int, day: int) -> list[tuple[UUID, str, date]]:
    """Every album whose earliest eligible asset's local calendar day falls on this month/day, any
    year - one grouped query instead of a get_album_first_asset_date call per album. Web Push's
    daily "on this day" album-anniversary notification (services/notifications/content.py). Years-
    ago math (current_year - first_asset_date.year) is the caller's job, not this query's."""
    local_date = cast(func.timezone("UTC", asset.c.localDateTime), Date)
    first_date = func.min(local_date).label("first_asset_date")
    stmt = (
        select(album.c.id, album.c.albumName, first_date)
        .select_from(
            album.join(album_asset, album_asset.c.albumId == album.c.id).join(
                asset, asset.c.id == album_asset.c.assetId
            )
        )
        .where(album.c.deletedAt.is_(None), _ASSET_ELIGIBLE)
        .group_by(album.c.id, album.c.albumName)
        .having(func.extract("month", first_date) == month, func.extract("day", first_date) == day)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return [(row.id, row.albumName, row.first_asset_date) for row in rows]


def get_album_named_face_counts(engine: Engine, album_id: UUID) -> list[tuple[UUID, str, int]]:
    """(person_id, name, distinct_asset_count) for every named person appearing (via an eligible,
    visible, non-deleted face tag) in this album's eligible assets, ordered by count desc - the
    data source for both Albumdle's dominant_face clue (the tie-break itself is a game rule, done
    in games/immichdle/albumdle.py, not here) and, via len(), its unique_face_count clue."""
    distinct_asset_count = func.count(func.distinct(asset_face.c.assetId)).label("distinct_asset_count")
    stmt = (
        select(person.c.id, person.c.name, distinct_asset_count)
        .select_from(
            album_asset.join(asset, asset.c.id == album_asset.c.assetId)
            .join(asset_face, asset_face.c.assetId == asset.c.id)
            .join(person, person.c.id == asset_face.c.personId)
        )
        .where(
            album_asset.c.albumId == album_id,
            _ASSET_ELIGIBLE,
            asset_face.c.deletedAt.is_(None),
            asset_face.c.isVisible.is_(True),
            person.c.isHidden.is_(False),
            person.c.thumbnailPath != "",
            person.c.name != "",
        )
        .group_by(person.c.id, person.c.name)
        .order_by(distinct_asset_count.desc())
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return [(row.id, row.name, row.distinct_asset_count) for row in rows]


def get_persons_present_in_album(engine: Engine, album_id: UUID, person_ids: frozenset[UUID]) -> frozenset[UUID]:
    """The subset of `person_ids` that appear via any eligible face tag anywhere in this album -
    powers Albumdle's dominant_face amber/red membership check. Empty in, empty out (no query)."""
    if not person_ids:
        return frozenset()
    stmt = (
        select(asset_face.c.personId)
        .distinct()
        .select_from(album_asset.join(asset, asset.c.id == album_asset.c.assetId).join(
            asset_face, asset_face.c.assetId == asset.c.id
        ))
        .where(
            album_asset.c.albumId == album_id,
            _ASSET_ELIGIBLE,
            asset_face.c.deletedAt.is_(None),
            asset_face.c.isVisible.is_(True),
            asset_face.c.personId.in_(person_ids),
        )
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return frozenset(row.personId for row in rows)
