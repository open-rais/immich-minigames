"""Text-search plumbing shared by persons.py's search_persons and albums.py's search_albums -
accent folding, LIKE escaping, and the word-prefix condition builder both build on. Private to
this *package* (leading underscore - not games/shared/, which is the cross-game boundary): this is
Immich-query plumbing, narrower in scope than anything a game itself would reach for."""

from sqlalchemy import ColumnElement, func

# Accent-insensitive search (e.g. "Rodriguez" should match stored "Rodríguez") without CREATE
# EXTENSION unaccent - this role only has SELECT on Immich's `public` schema (see
# docs/ARCHITECTURE/IMMICH.md) and translate() is a builtin Postgres function, not an extension.
_ACCENTED_CHARS = "áéíóúÁÉÍÓÚñÑüÜ"
_FOLDED_CHARS = "aeiouAEIOUnNuU"
_ACCENT_FOLD_TABLE = str.maketrans(_ACCENTED_CHARS, _FOLDED_CHARS)


def _fold_accents(value: str) -> str:
    return value.translate(_ACCENT_FOLD_TABLE)


def _escape_like(value: str) -> str:
    """Escapes LIKE/ILIKE wildcard characters in free-typed user input before interpolating it
    into a pattern - otherwise a literal % or _ in someone's search text would act as a wildcard
    instead of a literal character."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def word_prefix_conditions(column: ColumnElement[str], query: str) -> list[ColumnElement[bool]]:
    """One condition per whitespace-separated token in `query` (empty list for an empty/blank
    query), each requiring the token to prefix a *word* somewhere in `column` (case- and accent-
    insensitive) - e.g. "rai rodriguez" matches "Raimundo Rodríguez" (each token prefixes a
    different word, regardless of typed order) but not "Martin Perez" (no mid-word match). Per
    token, two ILIKE conditions cover "prefixes a word anywhere in the value": the token prefixing
    the first word, or prefixing any later word (the leading `%` in the second pattern absorbs
    everything before that word, including other whole words). The caller ANDs every token's
    condition together (via search_persons/search_albums' own `*token_conditions` in `.where`),
    which is what makes multi-word queries need every token satisfied rather than any one."""
    folded_column = func.translate(column, _ACCENTED_CHARS, _FOLDED_CHARS)
    conditions = []
    for token in query.split():
        escaped = _escape_like(_fold_accents(token))
        starts_with = folded_column.ilike(f"{escaped}%", escape="\\")
        contains_word_starting_with = folded_column.ilike(f"% {escaped}%", escape="\\")
        conditions.append(starts_with | contains_word_starting_with)
    return conditions
