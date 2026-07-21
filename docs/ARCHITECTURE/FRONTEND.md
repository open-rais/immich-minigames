# Frontend

React 19 + Vite + TypeScript + Tailwind 4 + Axios + react-i18next + MapLibre GL, in `frontend/src/`.
Dev: `npm run dev`. Typecheck: `npx tsc -b`. Lint: `npx oxlint`. Both clean as of 2026-07-20.

## Routing

`App.tsx` nests `ThemeProvider > BrowserRouter > AuthProvider > Routes`:

| Route | Component |
|---|---|
| `/` | `MainMenu` |
| `/login`, `/signup`, `/profile`, `/profile/edit` | auth pages |
| `/admin` | `AdminPage` (redirects non-admins) |
| `/:gameType/:mode` | `GameRoute` → looks up `GAME_CATALOG`, renders that mode's component |
| `/:gameType/:mode/leaderboard` | `LeaderboardPage` |

`games/catalog.ts` is the frontend's registry of playable game/modes and is **hand-mirrored** from
the backend's `_GAMES` dict. An unknown `:gameType/:mode` bounces to `/` rather than 404ing.

## API layer

`api/client.ts` is a single axios instance with `baseURL: "/api/v1"` and a 10s timeout. A request
interceptor attaches `X-Owner-Id` from `api/ownerId.ts` to every request.

**Everything is same-origin**: Vite proxies `/api` in dev, nginx proxies it in prod. That is why
there is no CORS config anywhere and why the httpOnly session cookie just works with no
`withCredentials`.

`api/types.ts` mirrors `backend/src/api/dto/` **by hand** — there is no codegen. When either side
changes, both must be edited. Same convention as `catalog.ts` vs `_GAMES`.

## Game state machines

Each game's top-level `*Game.tsx` owns its screen state machine:
`idle → playing → finished | error`, plus a per-round phase `guessing → submitting → revealed`.

**`games/shared/useRoundGame.ts`** encapsulates that machine for the "fixed rounds, one picker,
auto-advance after a reveal hold" shape. Geoguessr, Dateguessr and Who'sThatPerson use it; the
component keeps only its own guess-input state. It handles:

- **Re-entrancy guards** (`startInFlightRef`, `guessInFlightRef`) — a double-click can fire two
  handlers before React re-renders, so state alone cannot prevent a duplicate request.
- **Request tokens** (`requestTokenRef`) — bumped on every start/guess and on Back, so a late
  response for a superseded request is discarded.
- **Reveal hold** — a timer that auto-advances to the next round (or the finished screen) after
  `revealHoldMs`, with no explicit "next" click.

> MoreOrLess and Immichdle predate the hook and reimplement the same three mechanisms inline. See
> finding #17.

Reveal-hold durations differ on purpose: MoreOrLess 1400ms, Geoguessr/Dateguessr 2400ms (the map's
own 600ms `fitBounds` animation plus reading two numbers), Who'sThatPerson 2800ms (several faces to
read at once).

## Design system

`index.css`'s `@theme` block is the single source of design tokens. The primary
(`oklch(0.48 0.16 265)`) is Immich's actual brand indigo `#4250af`, verified against a running
Immich instance — not an arbitrary pick.

Token families: `--color-app-bg`/`--color-surface`; `--color-primary(-hover)`;
`--color-danger(-hover)`; `--color-clue-match/close/miss`; `--color-badge-bg/label/value`;
`--color-line-strong/line/line-soft`; `--color-ink/body/muted/faint`; `--color-hover-tint`,
`--color-count-bg`, `--color-placeholder-a/b`; `--color-map-bg/water/land`; `--shadow-card`.

**Dark mode** is a `.dark` class on `<html>` that redefines those same variables — un-layered, so it
wins over Tailwind's `@layer theme` output. This is why **no `dark:` variants appear anywhere in the
app**: every utility already resolves through a variable. It is a lightened/desaturated primary, not
a lightness flip, because dark indigo has poor contrast on near-black.

The initial class is set by an inline script in `index.html` before first paint, so there is no
flash of the wrong theme; `ThemeProvider` only *observes* what that script decided for the initial
render.

Two deliberate exceptions to the token system: `--color-blackout` is fixed in both themes
(Who'sThatPerson's face boxes hide a face, they are not a themed surface), and MapLibre needs
literal hex in its style JSON, so `mapStyle.ts` keeps hand-synced constants.

> The system is well-disciplined but not universally applied — raw Tailwind palette colors
> (`text-rose-600`, `text-emerald-600`, `#e11d48`) appear in seven files for error/success/incorrect
> states, with no dark-mode variant. See findings #22 and #23.

## Responsive conventions

**One component tree per screen, not separate mobile components.** Tailwind's `md:` (768px)
switches layout. `MoreOrLessGame` is the reference: stacked/full-width/no-scroll below `md:`,
side-by-side/fixed-width at and above.

When an animation depends on the breakpoint, **measure the real element at trigger time** rather
than hardcoding a pixel constant that only holds at one width — see MoreOrLess's slide transition
using a ref + `offsetWidth`/`offsetHeight`. (Known limitation: the axis is captured once when the
animation starts, so rotating the phone mid-transition can use the stale axis for that one slide.
Documented in ROADMAP.md as not worth fixing.)

The in-game chrome is `fixed`-positioned and floats over the content rather than sitting in flow —
`BackButton` top-left, `RoundBadge` top-center, `ScoreBadge` top-right, the confirm button
bottom-left. On mobile this frees the vertical space the cards need for the no-scroll budget.

> Those three top badges can collide on screens narrower than ~360px, and Geoguessr's confirm
> button overlaps the expanded map on mobile. See findings #24 and #25.

Safe areas: `viewport-fit=cover` in the viewport meta, `pt-[env(safe-area-inset-top)]` on headers,
and an `html` background gradient so iOS overscroll rubber-banding reveals matching colors rather
than a bare canvas.

## Notable components

**`games/shared/AssetPhoto.tsx`** — fullscreen `object-contain` photo with wheel-zoom and
pointer/pinch pan. Computes the "fit box" (where the image's pixels actually render inside the
letterboxed container) and exposes an `overlay` slot positioned to exactly match it, so overlaid
content stays pixel-aligned at any zoom/pan. Wheel is attached natively (`{ passive: false }`)
because React's synthetic `onWheel` is passive and `preventDefault()` there silently no-ops.

**`games/WhosThatPerson/IncognitoPhoto.tsx`** — face boxes as percentage rects over that overlay,
expanded 15% for difficulty, floored at 44px via CSS `max()` and re-centered so small boxes stay
tappable. The guess popover is portaled to `<body>` so it escapes the photo's zoom transform, and
positioned from the box's measured viewport rect, clamped to stay on-screen. Contains a documented
iOS Safari workaround (scroll reset on unmount) for the keyboard leaving stale touch hit-regions.

**`games/shared/PersonSearchInput.tsx`** — debounced (250ms), paginated (3/page) person autocomplete
with full keyboard navigation, infinite scroll, and an auto-load loop for when a short page doesn't
overflow the box. Shared by Immichdle, Who'sThatPerson and both skin pickers.

> Its search effect depends on the `excludeIds` **Set by reference**. Two of the four call sites
> `useMemo` it; two construct it inline per render. See finding #18.

**`games/Geoguessr/MapPicker.tsx`** — MapLibre map, collapsed to a corner thumbnail and expanded on
hover (desktop) / tap (mobile). Remounts entirely on theme change because MapLibre style JSON cannot
take `var()`. Uses refs for the click handler's dependencies so the listener attaches once.

**`games/Dateguessr/timeMath.ts`** — all date math goes through an integer "day index" (days since
epoch via `Date.UTC`) rather than `Date` objects, sidestepping the
local-calendar-day-shifts-by-one-through-UTC pitfall. Immichdle's `ClueCell` guards the same trap by
formatting with `timeZone: "UTC"`.

## i18n

react-i18next, English + Spanish, 116 keys each, complete in both (verified 2026-07-20). Language
names in the picker are deliberately **not** translated — a language's own name shouldn't change
based on the active language, matching how browsers and OSes do it.

Note that backend error `detail` strings are surfaced raw to the user by `api/errors.ts` and are
English-only regardless of the selected language (finding #12).
