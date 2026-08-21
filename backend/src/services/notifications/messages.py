"""Push notification copy in the app's 4 languages, composed server-side (the payload travels to a
closed app - the service worker has neither localStorage nor i18next available, see
frontend/src/i18n/index.ts). Deliberately duplicated with frontend/src/i18n/locales/*.json rather
than sharing a source of truth: two different surfaces (one rendered by React, one carried inside
an encrypted push), and this is 11 short strings x 4 languages - keeping them in sync by hand costs
less than the coupling would.
"""

from dataclasses import dataclass

from services.notifications.content import AlbumAnniversaryEntry, BirthdayEntry

DEFAULT_LANGUAGE = "en"

GAME_DISPLAY_NAMES: dict[str, dict[str, str]] = {
    "more-or-less": {"en": "More or Less", "es": "More or Less", "fr": "Plus ou Moins", "de": "Mehr oder Weniger"},
    "geoguessr": {"en": "Geoguessr", "es": "Geoguessr", "fr": "Geoguessr", "de": "Geoguessr"},
    "dateguessr": {"en": "Dateguessr", "es": "Dateguessr", "fr": "Dateguessr", "de": "Dateguessr"},
    "immichdle": {"en": "Immichdle", "es": "Immichdle", "fr": "Immichdle", "de": "Immichdle"},
    "whos-that-person": {
        "en": "Who's That Person",
        "es": "¿Quién es?",
        "fr": "Qui est cette personne",
        "de": "Wer ist diese Person",
    },
    "timeline": {"en": "Timeline", "es": "Timeline", "fr": "Timeline", "de": "Timeline"},
}

_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "daily_available_title": "New daily challenge",
        "daily_available_body": "Today's daily games are ready to play",
        "daily_reminder_title": "Daily reminder",
        "daily_reminder_streak_at_risk_body": "You're about to lose your {streak}-day streak in {game}",
        "daily_reminder_generic_body": "Today's games are about to change - play them before they do",
        "birthdays_title": "Birthday today",
        "birthdays_body_one": "{name} turns {age} today",
        "birthdays_body_many": "Today is the birthday of {names}",
        "album_anniversary_title": "On this day",
        "album_anniversary_body_one": '"{name}" started {years} year(s) ago today',
        "album_anniversary_body_many": "{count} albums started on a day like today",
    },
    "es": {
        "daily_available_title": "Nuevo desafío diario",
        "daily_available_body": "Los juegos diarios de hoy ya están disponibles",
        "daily_reminder_title": "Recordatorio diario",
        "daily_reminder_streak_at_risk_body": "Estás por perder tu racha de {streak} en {game}",
        "daily_reminder_generic_body": "Los juegos de hoy están por terminar. Juégalos antes de que cambien",
        "birthdays_title": "Cumpleaños hoy",
        "birthdays_body_one": "Hoy {name} cumple {age} años",
        "birthdays_body_many": "Hoy cumplen años {names}",
        "album_anniversary_title": "Un día como hoy",
        "album_anniversary_body_one": '"{name}" empezó hace {years} año(s)',
        "album_anniversary_body_many": "{count} álbumes empezaron un día como hoy",
    },
    "fr": {
        "daily_available_title": "Nouveau défi quotidien",
        "daily_available_body": "Les jeux quotidiens d'aujourd'hui sont prêts",
        "daily_reminder_title": "Rappel quotidien",
        "daily_reminder_streak_at_risk_body": (
            "Vous êtes sur le point de perdre votre série de {streak} jours dans {game}"
        ),
        "daily_reminder_generic_body": "Les jeux d'aujourd'hui touchent à leur fin - jouez-y avant qu'ils ne changent",
        "birthdays_title": "Anniversaire aujourd'hui",
        "birthdays_body_one": "{name} fête ses {age} ans aujourd'hui",
        "birthdays_body_many": "C'est l'anniversaire de {names} aujourd'hui",
        "album_anniversary_title": "Il y a jour pour jour",
        "album_anniversary_body_one": '"{name}" a commencé il y a {years} an(s)',
        "album_anniversary_body_many": "{count} albums ont commencé un jour comme aujourd'hui",
    },
    "de": {
        "daily_available_title": "Neue tägliche Herausforderung",
        "daily_available_body": "Die heutigen täglichen Spiele sind bereit",
        "daily_reminder_title": "Tägliche Erinnerung",
        "daily_reminder_streak_at_risk_body": "Du bist dabei, deine {streak}-Tage-Serie in {game} zu verlieren",
        "daily_reminder_generic_body": "Die heutigen Spiele enden bald - spiel sie, bevor sie sich ändern",
        "birthdays_title": "Geburtstag heute",
        "birthdays_body_one": "{name} hat heute Geburtstag und wird {age}",
        "birthdays_body_many": "Heute haben {names} Geburtstag",
        "album_anniversary_title": "Heute vor Jahren",
        "album_anniversary_body_one": '"{name}" wurde vor {years} Jahr(en) begonnen',
        "album_anniversary_body_many": "{count} Alben wurden an einem Tag wie heute begonnen",
    },
}


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str


def _string(language: str, key: str) -> str:
    # Falls back to English per-key, not per-language - a language missing exactly one key
    # (typo, a key added and only English filled in) still reads correctly in every other key of
    # that language, instead of the whole language silently reverting to English.
    table = _MESSAGES.get(language, _MESSAGES[DEFAULT_LANGUAGE])
    return table.get(key) or _MESSAGES[DEFAULT_LANGUAGE][key]


def game_display_name(game_type: str, language: str) -> str:
    names = GAME_DISPLAY_NAMES.get(game_type)
    if names is None:
        return game_type
    return names.get(language) or names[DEFAULT_LANGUAGE]


def daily_available(language: str) -> PushMessage:
    return PushMessage(_string(language, "daily_available_title"), _string(language, "daily_available_body"))


def daily_reminder_streak_at_risk(language: str, game_type: str, streak: int) -> PushMessage:
    body = _string(language, "daily_reminder_streak_at_risk_body").format(
        streak=streak, game=game_display_name(game_type, language)
    )
    return PushMessage(_string(language, "daily_reminder_title"), body)


def daily_reminder_generic(language: str) -> PushMessage:
    return PushMessage(_string(language, "daily_reminder_title"), _string(language, "daily_reminder_generic_body"))


def birthdays(language: str, entries: list[BirthdayEntry]) -> PushMessage:
    if len(entries) == 1:
        body = _string(language, "birthdays_body_one").format(name=entries[0].name, age=entries[0].age)
    else:
        body = _string(language, "birthdays_body_many").format(names=", ".join(e.name for e in entries))
    return PushMessage(_string(language, "birthdays_title"), body)


def album_anniversary(language: str, entries: list[AlbumAnniversaryEntry]) -> PushMessage:
    if len(entries) == 1:
        body = _string(language, "album_anniversary_body_one").format(
            name=entries[0].name, years=entries[0].years_ago
        )
    else:
        body = _string(language, "album_anniversary_body_many").format(count=len(entries))
    return PushMessage(_string(language, "album_anniversary_title"), body)
