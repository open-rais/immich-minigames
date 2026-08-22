"""Postgres queries over Immich's `person`/`asset_face` tables."""

from datetime import date
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.engine import Engine

from domain.person import Person
from persistence.immich_tables import asset, asset_face, person

from ._rows import row_to_person
from ._text import word_prefix_conditions


def get_persons(
    engine: Engine,
    *,
    named_only: bool = True,
    with_birthdate: bool | None = None,
    min_asset_count: int | None = None,
    name_query: str | None = None,
    ids: frozenset[UUID] | None = None,
    randomize: bool = False,
    asset_count_weight: float | None = None,
    limit: int = 1,
    exclude_ids: frozenset[UUID] = frozenset(),
) -> list[Person]:
    asset_count_agg = func.count(func.distinct(asset_face.c.assetId))
    asset_count = asset_count_agg.label("asset_count")

    stmt = (
        select(person.c.id, person.c.name, person.c.birthDate, asset_count)
        .select_from(
            person.outerjoin(
                asset_face,
                (asset_face.c.personId == person.c.id)
                & asset_face.c.deletedAt.is_(None)
                & asset_face.c.isVisible.is_(True),
            )
        )
        .where(person.c.isHidden.is_(False), person.c.thumbnailPath != "")
        .group_by(person.c.id, person.c.name, person.c.birthDate)
    )

    if named_only:
        stmt = stmt.where(person.c.name != "")
    if with_birthdate is True:
        stmt = stmt.where(person.c.birthDate.is_not(None))
    elif with_birthdate is False:
        stmt = stmt.where(person.c.birthDate.is_(None))
    if name_query:
        stmt = stmt.where(person.c.name.ilike(f"%{name_query}%"))
    if ids is not None:
        stmt = stmt.where(person.c.id.in_(ids))
    if exclude_ids:
        stmt = stmt.where(person.c.id.notin_(exclude_ids))
    if min_asset_count is not None:
        stmt = stmt.having(asset_count >= min_asset_count)

    if randomize and asset_count_weight:
        # Weighted random pick (Efraimidis-Spirakis: order by random()^(1/weight) desc)
        # instead of a plain ORDER BY random() - see games/immichdle.py's
        # ASSET_COUNT_WEIGHT_EXPONENT for the admin-configurable exponent this implements.
        # greatest(..., 1) avoids a division by zero for a person with 0 tagged assets.
        weight = func.pow(func.greatest(asset_count_agg, 1), asset_count_weight)
        stmt = stmt.order_by(func.pow(func.random(), 1.0 / weight).desc())
    elif randomize:
        stmt = stmt.order_by(func.random())
    else:
        stmt = stmt.order_by(person.c.name)
    stmt = stmt.limit(limit)

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    return [row_to_person(row) for row in rows]


def get_persons_with_birthday_on(engine: Engine, month: int, day: int) -> list[Person]:
    """Every eligible named person (same isHidden/thumbnailPath/name/birthDate filters as
    get_persons' named_only+with_birthdate) whose birthDate falls on this month/day, any year -
    Web Push's daily birthday notification (services/notifications/content.py).

    29 February deliberately never matches outside a leap year - not worked around with a nearby
    date, since inventing "the 28th" would be wrong more years than it's right. Age itself
    (current_year - birth_year) is the caller's job, not this query's - it doesn't know "today"."""
    asset_count_agg = func.count(func.distinct(asset_face.c.assetId))
    stmt = (
        select(person.c.id, person.c.name, person.c.birthDate, asset_count_agg.label("asset_count"))
        .select_from(
            person.outerjoin(
                asset_face,
                (asset_face.c.personId == person.c.id)
                & asset_face.c.deletedAt.is_(None)
                & asset_face.c.isVisible.is_(True),
            )
        )
        .where(
            person.c.isHidden.is_(False),
            person.c.thumbnailPath != "",
            person.c.name != "",
            person.c.birthDate.is_not(None),
            func.extract("month", person.c.birthDate) == month,
            func.extract("day", person.c.birthDate) == day,
        )
        .group_by(person.c.id, person.c.name, person.c.birthDate)
        .order_by(person.c.name)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return [row_to_person(row) for row in rows]


def search_persons(engine: Engine, query: str, *, offset: int = 0, limit: int = 3) -> list[Person]:
    """Named people matching every whitespace-separated token in `query` against a *word* in the
    name - see ._text.word_prefix_conditions for the actual matching rule. Kept separate from
    get_persons - its existing name_query is a plain substring filter, and nothing else needs this
    word-prefix mode. Paginated via offset/limit (small pages, e.g. for infinite scroll UIs),
    ordered by name for a stable scroll order."""
    token_conditions = word_prefix_conditions(person.c.name, query)
    if not token_conditions:
        return []

    asset_count = func.count(func.distinct(asset_face.c.assetId)).label("asset_count")

    stmt = (
        select(person.c.id, person.c.name, person.c.birthDate, asset_count)
        .select_from(
            person.outerjoin(
                asset_face,
                (asset_face.c.personId == person.c.id)
                & asset_face.c.deletedAt.is_(None)
                & asset_face.c.isVisible.is_(True),
            )
        )
        .where(
            person.c.isHidden.is_(False),
            person.c.thumbnailPath != "",
            person.c.name != "",
            *token_conditions,
        )
        .group_by(person.c.id, person.c.name, person.c.birthDate)
        .order_by(person.c.name)
        .offset(offset)
        .limit(limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    return [row_to_person(row) for row in rows]


def get_person_first_asset_date(engine: Engine, person_id: UUID) -> date | None:
    """Local calendar day of this person's earliest tagged asset - same local-day expression
    get_assets uses (see that function's localDate comment). Powers Immichdle's FirstAppearance
    clue. None if the person has no visible, non-deleted face tags."""
    local_date = cast(func.timezone("UTC", asset.c.localDateTime), Date)
    stmt = (
        select(func.min(local_date))
        .select_from(asset_face.join(asset, asset.c.id == asset_face.c.assetId))
        .where(
            asset_face.c.personId == person_id,
            asset_face.c.deletedAt.is_(None),
            asset_face.c.isVisible.is_(True),
            asset.c.status == "active",
            asset.c.visibility == "timeline",
            asset.c.deletedAt.is_(None),
        )
    )
    with engine.connect() as conn:
        return conn.execute(stmt).scalar()


def get_assets_together_count(engine: Engine, person_a_id: UUID, person_b_id: UUID) -> int:
    """How many distinct assets have both people face-tagged - powers Immichdle's
    AssetsTogether clue."""
    face_a = asset_face.alias("face_a")
    face_b = asset_face.alias("face_b")
    stmt = (
        select(func.count(func.distinct(face_a.c.assetId)))
        .select_from(face_a.join(face_b, face_a.c.assetId == face_b.c.assetId))
        .where(
            face_a.c.personId == person_a_id,
            face_a.c.deletedAt.is_(None),
            face_a.c.isVisible.is_(True),
            face_b.c.personId == person_b_id,
            face_b.c.deletedAt.is_(None),
            face_b.c.isVisible.is_(True),
        )
    )
    with engine.connect() as conn:
        return conn.execute(stmt).scalar() or 0


def get_top_co_occurring_persons(
    engine: Engine, person_id: UUID, *, limit: int = 3, exclude_ids: frozenset[UUID] = frozenset()
) -> list[tuple[UUID, str, int]]:
    """Named people ranked by how many assets they share a face tag with `person_id` in, most
    co-occurrences first - (person_id, name, count) tuples. Powers Trivium's photos_together
    question type, which needs to *rank* candidates in one query rather than call
    get_assets_together_count once per candidate (N pairwise queries)."""
    face_a = asset_face.alias("face_a")
    face_b = asset_face.alias("face_b")
    count = func.count(func.distinct(face_a.c.assetId)).label("together_count")
    stmt = (
        select(face_b.c.personId, person.c.name, count)
        .select_from(
            face_a.join(face_b, face_a.c.assetId == face_b.c.assetId).join(person, person.c.id == face_b.c.personId)
        )
        .where(
            face_a.c.personId == person_id,
            face_a.c.deletedAt.is_(None),
            face_a.c.isVisible.is_(True),
            face_b.c.deletedAt.is_(None),
            face_b.c.isVisible.is_(True),
            face_b.c.personId != person_id,
            person.c.isHidden.is_(False),
            person.c.name != "",
        )
    )
    if exclude_ids:
        stmt = stmt.where(face_b.c.personId.notin_(exclude_ids))
    stmt = stmt.group_by(face_b.c.personId, person.c.name).order_by(count.desc()).limit(limit)

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return [(row.personId, row.name, row.together_count) for row in rows]
