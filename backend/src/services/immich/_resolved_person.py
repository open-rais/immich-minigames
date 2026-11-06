"""One `person` row per person_group - the single place deciding which Immich user's view of a
person this app shows.

Since Immich v3.2 a person is a `person_group` (its id is the public person id), and `person` holds
one row per Immich user who sees that person, each with its own name/birthDate/isHidden - several
rows per group once people are shared between users (v3.3). Every person/face query in this package
joins against `resolved_person` below instead of `person` directly, so the same person always
resolves to the same row everywhere (e.g. the guess search box and Who'sThatPerson's blacked-out
faces can never disagree on a name or on whether someone is hidden).

Ranking within a group, first row wins:
1. a row that has a name (`name <> ''`),
2. owned by an Immich admin,
3. owned by the oldest Immich account, then by ownerId - a deterministic tie-break, so a given
   game/daily always sees the same name.
So the admin's name wins when the admin has one, and a named row from another user is used only
when the admin's row is unnamed or missing. On a single-user instance each group has exactly one
row, so this is a no-op.

`birthDate` comes from the winning row when it has one, otherwise from the first row (same ranking)
that does. `hasThumbnail` is true when *any* row in the group has a face crop: rows created by
person sharing start with an empty thumbnailPath, and Immich serves the sharer's crop for them.
"""

from sqlalchemy import func, select

from persistence.immich_tables import person, user

_named_first = (person.c.name != "").desc()
_ranking = (_named_first, user.c.isAdmin.desc(), user.c.createdAt.asc(), person.c.ownerId.asc())

_ranked = (
    select(
        person.c.personGroupId.label("id"),
        person.c.name,
        person.c.isHidden,
        func.row_number().over(partition_by=person.c.personGroupId, order_by=_ranking).label("rank"),
        func.first_value(person.c.birthDate)
        .over(partition_by=person.c.personGroupId, order_by=(person.c.birthDate.is_(None).asc(), *_ranking))
        .label("birthDate"),
        func.bool_or(person.c.thumbnailPath != "").over(partition_by=person.c.personGroupId).label("hasThumbnail"),
    )
    .select_from(person.join(user, user.c.id == person.c.ownerId))
    .subquery("ranked_person")
)

resolved_person = (
    select(_ranked.c.id, _ranked.c.name, _ranked.c.birthDate, _ranked.c.isHidden, _ranked.c.hasThumbnail)
    .where(_ranked.c.rank == 1)
    .subquery("resolved_person")
)
