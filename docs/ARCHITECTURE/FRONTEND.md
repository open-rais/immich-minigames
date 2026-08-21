# Frontend

React 19 + Vite + TypeScript + Tailwind 4 + Axios + react-i18next + MapLibre GL, in `frontend/src/`.
Dev: `npm run dev`. Typecheck: `npx tsc -b`. Lint: `npx oxlint`. Both clean as of 2026-08-20.

## Routing

`App.tsx` nests `ThemeProvider > BrowserRouter > AuthProvider > Routes`:

| Route | Component |
|---|---|
| `/` | `MainMenu` |
| `/login`, `/signup`, `/profile`, `/profile/edit` | auth pages |
| `/admin` | `AdminPage` (redirects non-admins) |
| `/admin/reports` | `AdminReportsPage` (redirects non-admins) - the metadata-report review panel (roadmap #N) |
| `/:gameType/:mode` | `GameRoute` → looks up `GAME_CATALOG`, renders that mode's component |
| `/:gameType/:mode/leaderboard` | `LeaderboardPage` |
| `/:gameType/:mode/game/:gameId/rounds` | `RoundsPage` — post-game "Ver rondas"/"Ver juego" review (roadmap #10, see below) |

`games/catalog.ts` is the frontend's registry of playable game/modes and is **hand-mirrored** from
the backend's `_GAMES` dict. An unknown `:gameType/:mode` bounces to `/` rather than 404ing.

## API layer

`api/client.ts` is a single axios instance with `baseURL: "/api/v1"` and a 10s timeout. The httpOnly
session cookie rides along with every request automatically; no header wiring needed.

**Everything is same-origin**: Vite proxies `/api` in dev, nginx proxies it in prod. That is why
there is no CORS config anywhere and why the httpOnly session cookie just works with no
`withCredentials`.

`api/types.ts` mirrors `backend/src/api/dto/` **by hand** — there is no codegen. When either side
changes, both must be edited. Same convention as `catalog.ts` vs `_GAMES`.

## Game state machines

Each game's top-level `*Game.tsx` owns its screen state machine:
`idle → playing → finished | error`, plus a per-round phase `guessing → submitting → revealed`.

**`games/shared/useRoundGame.ts`** encapsulates that machine for the "one picker per round,
auto-advance after a reveal hold" shape. Geoguessr, Dateguessr and Who'sThatPerson use it for their
fixed-N-rounds games; Timeline uses the same hook for its infinite streak (no `total_rounds` —
`finished` alone, driven by the backend, is what ends it) — the hook itself doesn't care whether the
round count is fixed or open-ended. The component keeps only its own guess-input state. It handles:

- **Re-entrancy guards** (`startInFlightRef`, `guessInFlightRef`) — a double-click can fire two
  handlers before React re-renders, so state alone cannot prevent a duplicate request.
- **Request tokens** (`requestTokenRef`) — bumped on every start/guess and on Back, so a late
  response for a superseded request is discarded.
- **Reveal hold** — a timer that auto-advances to the next round (or the finished screen) after
  `revealHoldMs`, with no explicit "next" click.

> MoreOrLess and Immichdle predate the hook and reimplement the same three mechanisms inline.

Reveal-hold durations differ on purpose: MoreOrLess 1400ms, Geoguessr/Dateguessr 2400ms (the map's
own 600ms `fitBounds` animation plus reading two numbers), Who'sThatPerson 2800ms (several faces to
read at once), Timeline 2200ms (its own ~500ms fly-in animation plus reading the result).

## Rounds review (roadmap #10)

`games/rounds/RoundsPage.tsx` loads `GET /games/{id}` and hands it to that mode's own review
component, chosen from `catalog.ts`'s `roundsComponent` (mirroring how `GameRoute` picks
`component`). Two visual families, both driven by `CatalogMode.roundsLayout`:

- **`"list"`** (default, unset — MoreOrLess, Immichdle): wrapped in `games/rounds/RoundsShell.tsx`,
  a normal padded/scrolling page (back button, title, final score).
- **`"fullscreen"`** (Geoguessr, Dateguessr, Who'sThatPerson, Timeline): `RoundsShell` is skipped
  entirely — `MapPicker`/`TimelineRuler`/`AssetPhoto` are all `position: fixed`, full-viewport
  components that don't belong inside a padded scrolling shell, and each `<XxxRounds>` owns its
  whole screen the same way the live `*Game.tsx` components already do (their own `BackButton`). The
  first three step through one round at a time via `games/rounds/RoundStepper.tsx` — an interactive
  `RoundBadge` with prev/next arrows — in the same top-center slot `RoundBadge` uses during play.
  `TimelineRounds.tsx` is the odd one out here: the owner explicitly asked for the *whole* final
  board at once instead of a stepper, so it reuses
  `TimelineTrack.tsx` read-only rather than `RoundStepper` — same "fullscreen, no `RoundsShell`"
  family, different internal shape.

`games/shared/EntryOptionsMenu.tsx` (a "⋯" trigger + popover) is the shared per-entity actions menu
everywhere it appears — `games/shared/ImmichLink.tsx` ("Ver en Immich") and, since roadmap #N,
`games/shared/ReportMenuItem.tsx` ("Reportar", opening `ReportModal.tsx`). Its popover is
positioned `fixed` from the trigger's own `getBoundingClientRect()` rather than `absolute` relative
to the trigger — Immichdle's `GuessTable` needs it inside an `overflow-x-auto` container, and a
mismatched-axis `overflow` (one axis non-`visible`, e.g. `overflow-x-auto`) computes the other axis
to `auto` too, silently clipping an `absolute` popover that spills past the table's box. `fixed`
ignores ancestor overflow clipping entirely.

`ReportModal.tsx` itself goes one step further and portals to `document.body` (unlike every other
modal in the app, e.g. `ShareModal.tsx`/`ConfirmExitModal.tsx`, which are plain in-tree `fixed`
overlays) - it's the one modal that can open from inside `Timeline/TimelineCard.tsx`'s per-card
badge overlay, itself `absolute` + `z-index`ed, which creates its own stacking context that traps
a plain `fixed` descendant no matter how high its own `z-index` goes. Portalling to `document.body`
escapes that; the tradeoff is that `EntryOptionsMenu`'s own outside-click/scroll auto-close (see
above) would then read every click inside the portalled modal as "outside" and cascade-unmount it
along with the popover, since the modal's DOM node is no longer a descendant of the popover's own
root - guarded by a `[data-report-modal]` marker those handlers explicitly skip while present.

`ImmichLink` itself renders `null` whenever `useImmichLinks()` (`api/config.ts`) has no
`IMMICH_EXTERNAL_URL`/`IMMICH_SERVER_URL` to build a link from (a single, module-scope-cached
`GET /config` shared by every mounted `ImmichLink` on a page) — every call site is written with no
conditional of its own around it.

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
> states, with no dark-mode variant.

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
> button overlaps the expanded map on mobile.

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
> `useMemo` it; two construct it inline per render.

**`games/Geoguessr/MapPicker.tsx`** — MapLibre map, collapsed to a corner thumbnail and expanded on
hover (desktop) / tap (mobile). Remounts entirely on theme change because MapLibre style JSON cannot
take `var()`. Uses refs for the click handler's dependencies so the listener attaches once.

**`games/Dateguessr/timeMath.ts`** — all date math goes through an integer "day index" (days since
epoch via `Date.UTC`) rather than `Date` objects, sidestepping the
local-calendar-day-shifts-by-one-through-UTC pitfall. Immichdle's `ClueCell` guards the same trap by
formatting with `timeZone: "UTC"`.

**`admin/AdminWorkersSection.tsx`** (roadmap #15) — the embedding-cache admin panel: coverage
counters and "process missing"/"reprocess all" buttons for Persondle's face-similarity cache and
Albumdle's similarity cache, backed by `backend/src/services/embedding_jobs.py`'s single
background job. Deliberately does **not** go through `api/queryCache.ts`'s `useLiveQuery` - that
cache's whole model is "show what's cached, always issue a real request when something asks again",
with no notion of a recurring interval. This panel needs to repoll roughly every second *while a
job is running* to drive its progress bar, a different shape of problem, so it's a plain local
`useCallback` fetch plus two `useEffect`s instead: one to load on mount, one that opens a
`setInterval` only while `status.job` is `"running"` and tears it down (not just skips its own
work) the moment a poll reports otherwise. Pure formatting/decision logic (`jobProgressPercent`,
`isJobRunning`, ...) is split into `admin/embeddingWorkerFormat.ts`, kept free of React/fetch so it's
testable without jsdom (same split `games/shared/dailyShareText.ts` uses for its own share-text
formatting).

## PWA & push notifications (roadmap #O)

Installable app shell, an offline-capable cache, and opt-in Web Push - three features sharing one
piece of machinery (the service worker), built in that order since each is usable on its own and
the last one needs the first two already in place.

**Installability**: `public/manifest.webmanifest` (hand-written, not `vite-plugin-pwa`-generated -
its icon set is deliberate, see below) plus `index.html`'s `<link rel="manifest">`/
`<link rel="apple-touch-icon">`/theme-color `<meta>` pair (light/dark, media-queried). Icons are
baked onto a **solid** background (`--color-surface` light), not the logo's own transparent one -
iOS/Android compose a transparent icon inconsistently, and there's no standard mechanism at all for
a native-style light/dark/tinted icon trio on installed web apps (checked as of writing; only
`purpose: "monochrome"` exists, declared for whenever Android PWA theming catches up to it).

**Caching**: `vite-plugin-pwa` in `injectManifest` mode (not `generateSW` - the per-route caching
strategies below and the push handlers need real code, that mode only takes a glob list) builds
`src/sw.ts` into the served service worker; `src/pwa/register.ts` registers it itself
(`injectRegister: false`) behind the three-way feature-detect a self-hosted install actually needs
(`serviceWorker` in `navigator` implies a secure context; `PushManager` in `window`, absent on iOS
Safari until added to the home screen; `Notification.permission`). Routes, by strategy:

| Route | Strategy | Why |
|---|---|---|
| Hashed `assets/**` | Precached (`self.__WB_MANIFEST`) | Content-addressed, safe to cache forever. |
| Navigations | Network-first, single cache key | Every client-routed path serves the same `index.html`, so one entry (not one per visited path) covers all of them offline; network-first so a new deploy is seen immediately when online. |
| `logo.svg`/icons/`covers/*` | Stale-while-revalidate | Fixed names, no hash - a cache-first policy would never see an update. |
| Thumbnail proxies | Cache-first, `ExpirationPlugin(maxEntries: 300)` | `games/shared/thumbnailQueue.ts`'s own in-memory cache already dedupes/limits concurrency within a session; this is what survives a reload. |
| `/api/v1/config` | Stale-while-revalidate | Static, rarely changes. |
| Everything else under `/api/` | Not cached | Live, per-user data - `api/queryCache.ts`'s in-memory SWR is where "serve stale while refetching" belongs for anything that must not survive a logout on disk. |

Auto-update is deliberate and un-prompted: `skipWaiting()`/`clientsClaim()` in `sw.ts`, plus a
reload on `controllerchange` in `register.ts`. Skipping the reload would be the actual bug here -
every game chunk is its own dynamic `import()`, so a tab left open across a deploy would otherwise
resolve a chunk hash the new service worker's precache no longer has
(`Failed to fetch dynamically imported module`). Logout clears the one cache holding anything
account-scoped (`caches.delete("minigames-api-v1")`, see `src/pwa/clearApiCache.ts`) - Cache
Storage is per-origin, not per-session, so without this a shared browser would keep serving
account A's thumbnails to account B after they log in.

**Push notifications**: `src/pwa/push.ts` (permission, subscribe/unsubscribe,
`urlBase64ToUint8Array` for the VAPID key) and `useNotificationSettings.ts` (the hook backing
`settings/NotificationsCard.tsx` - a `Switch` per toggle, matching `admin/AdminGameRow.tsx`'s
`StreakScoringToggle`, both now built on the shared `games/shared/Switch.tsx`). The card renders
nothing at all when `GET /config`'s `push_public_key` is `null` (push not configured
server-side - see `docs/ARCHITECTURE/BACKEND.md` § Push notifications); when it's configured but
the browser can't (no secure context, no `PushManager`, permission denied), it renders disabled
with an explanatory note instead. `sw.ts`'s `push`/`notificationclick` handlers stay deliberately
dumb - they just render whatever `{title, body, url, tag}` the backend composed and focus/open
`url` on click - so a future fifth notification is backend-only work, never a service worker
version every installed device has to pick up on its own.

## i18n

react-i18next, English, Spanish, French and German, 279 keys each, complete in all four. Language
names in the picker are deliberately **not** translated — a language's own name shouldn't change
based on the active language, matching how browsers and OSes do it.

Note that backend error `detail` strings are surfaced raw to the user by `api/errors.ts` and are
English-only regardless of the selected language.
