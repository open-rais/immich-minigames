import { useEffect, useRef, useState } from "react"

import { createDailyGame, getDailyStatus } from "../../api/daily"
import { apiErrorStatus } from "../../api/errors"
import { createGame, GAME_RECORDS_KEY, getCurrentGame, getGame } from "../../api/games"
import { peekCached, revalidate, setCached, updateCached, useLiveQuery } from "../../api/queryCache"
import type { GameOut } from "../../api/types/common"
import type { DailyStatusOut } from "../../api/types/daily"
import type { GameRecordsOut } from "../../api/types/records"
import { useGuardedRequests } from "./useGuardedRequests"

export type Screen = "idle" | "playing" | "finished" | "error"

// Shared with menu/DailySection.tsx, which caches/revalidates the same GET /daily under this key
export const DAILY_STATUS_KEY = "daily-status"

// A non-daily instance still has to call useLiveQuery every render (Rules of Hooks), but must never
// hit the network for it - `daily` is stable for this hook's whole lifetime (it comes from a route
// literal, menu/DailyGameRoute.tsx), so keying off it here doesn't change the hook call order across
// renders, only its arguments. The dummy value is never read: the idle effect below bails out on
// `!daily` before looking at it.
const INACTIVE_DAILY_STATUS_KEY = "daily-status:inactive"
async function emptyDailyStatus(): Promise<DailyStatusOut> {
  return { resets_at: "", server_now: "", modes: [] }
}

// Game-lifecycle layer extracted out of useRoundGame/MoreOrLessGame/ImmichdleGame
// All three had copied this same block character-for-character since useRoundGame
// only covered games whose round flow fit its own reveal-hold shape, and MoreOrLess/Immichdle's
// don't. This hook owns only screen/busy/daily/start/resume/backToIdle/the idle-screen "has an
// active game" check/the daily 409 fallback - every game uses it. useRoundGame is now built on top
// of this for the games whose round flow *does* fit its reveal-hold shape.
interface UseGameSessionConfig {
  gameType: string
  mode: string
  // Maps a freshly-created or resumed GameOut onto this game's own state; returns whether it
  // succeeded (false -> error screen, same as a network failure). isResume is only true for
  // resumeGame's call - most games don't need to branch on it (their state-mapping already works
  // the same either way), Geoguessr/Dateguessr/Timeline/WhosThatPerson use it to fire their
  // onResume hook for accumulated state derived from round history.
  applyGame: (g: GameOut, isResume: boolean) => boolean
  // Maps an already-finished daily GameOut (found by the idle-screen status check) onto this
  // game's own "finished" state; returns whether it succeeded (false -> error screen). Only ever
  // called when `daily` is true.
  hydrateFinishedDaily: (g: GameOut) => boolean
  // True when this instance is playing today's daily challenge (menu/
  // DailyGameRoute.tsx) instead of a normal game. Changes which endpoint creates a game, where the
  // idle-screen "has an active game" check reads from (GET /daily's status instead of
  // get_current_game, which excludes daily games by design), and that an already-finished daily
  // jumps straight to the finished screen instead of ever offering "Jugar" again.
  daily?: boolean
}

export function useGameSession({
  gameType,
  mode,
  applyGame,
  hydrateFinishedDaily,
  daily = false,
}: UseGameSessionConfig) {
  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)
  // Whether the current player has an unfinished game for this (gameType, mode); null
  // while the idle-screen check below is still in flight, which IdleScreen treats the same as
  // false (an accepted brief "plain layout, then Continue pops in" flash).
  const [hasCurrentGame, setHasCurrentGame] = useState<boolean | null>(null)
  // The daily game's id, known from GET /daily's status before the player has done
  // anything - resumeGame() reads this instead of calling getCurrentGame (which never returns a
  // daily game).
  const dailyGameIdRef = useRef<string | null>(null)

  const { isCurrent, guarded, discardInFlight } = useGuardedRequests()
  const startInFlightRef = useRef(false)

  // Kept in a ref so the idle effect below can call the latest hydrateFinishedDaily without listing
  // it as a dependency (which would re-run the effect - and the fetch it triggers - every render).
  // applyGame doesn't need the same treatment: it's only ever called from startGame/resumeGame,
  // plain functions re-created fresh every render, not from inside a useEffect.
  const hydrateFinishedDailyRef = useRef(hydrateFinishedDaily)
  hydrateFinishedDailyRef.current = hydrateFinishedDaily

  // menu/DailySection.tsx reads/revalidates the same "daily-status" key, so finishing a daily here
  // and going back to the menu (or viceversa) shows the fresh state without a round trip's worth of flash.
  const dailyStatusQuery = useLiveQuery<DailyStatusOut>(
    daily ? DAILY_STATUS_KEY : INACTIVE_DAILY_STATUS_KEY,
    daily ? getDailyStatus : emptyDailyStatus,
  )

  // Derived from dailyStatusQuery.value instead of chained off the fetch promise directly, since
  // that value can now change for reasons other than this effect re-running (another mounted
  // consumer's revalidate(), or this hook's own markDailyFinished() below) - the `screen !== "idle"`
  // guard is what keeps those from interfering with an active/just-finished game.
  useEffect(() => {
    if (screen !== "idle" || !daily) return

    if (dailyStatusQuery.error && !dailyStatusQuery.value) {
      setHasCurrentGame(false)
      return
    }
    const status = dailyStatusQuery.value
    if (!status) return

    const modeStatus = status.modes.find((m) => m.game_type === gameType && m.mode === mode)
    dailyGameIdRef.current = modeStatus?.game_id ?? null

    if (modeStatus?.status === "finished" && modeStatus.game_id) {
      // hasCurrentGame stays null (not false) until this resolves - every game component's own
      // `if (daily && hasCurrentGame === null) return <blank>` guard is what's keeping the screen
      // blank right now, and setting it false early would release that guard while screen is still
      // "idle", showing a stutter of the idle/play screen before the fetch below flips to
      // "finished". Setting it together with the screen transition (both branches below) means the
      // guard only lifts once there's something real to show.
      let cancelled = false
      getGame(modeStatus.game_id)
        .then((g) => {
          if (cancelled) return
          setScreen(hydrateFinishedDailyRef.current(g) ? "finished" : "error")
          setHasCurrentGame(false)
        })
        .catch(() => {
          if (cancelled) return
          setScreen("error")
          setHasCurrentGame(false)
        })
      return () => {
        cancelled = true
      }
    }
    setHasCurrentGame(modeStatus?.status === "in_progress")
  }, [screen, daily, gameType, mode, dailyStatusQuery.value, dailyStatusQuery.error])

  // Non-daily "has an active game" check - unaffected by the cache migration above.
  useEffect(() => {
    if (screen !== "idle" || daily) return
    let cancelled = false
    getCurrentGame(gameType, mode)
      .then((g) => {
        if (!cancelled) setHasCurrentGame(g !== null)
      })
      .catch(() => {
        if (!cancelled) setHasCurrentGame(false)
      })
    return () => {
      cancelled = true
    }
  }, [screen, gameType, mode, daily])

  async function startGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = daily ? await createDailyGame(gameType, mode) : await createGame(gameType, mode)
        if (!isCurrent(token)) return
        setScreen(applyGame(g, false) ? "playing" : "error")
      } catch (err) {
        if (!isCurrent(token)) return
        if (daily && apiErrorStatus(err) === 409) {
          // Today's attempt was consumed between the idle status check and this create (another
          // tab/device) - re-run the status check instead of showing a generic error; it lands on
          // the finished (or in-progress) state instead, the "already played today" behavior.
          // Bypasses revalidate()'s dedup/version guard on purpose: this must always be a real,
          // fresh fetch, and must never leave hasCurrentGame stuck at null - on failure it falls
          // back to false, same as before the cache migration.
          setHasCurrentGame(null)
          getDailyStatus()
            .then((status) => {
              if (isCurrent(token)) setCached(DAILY_STATUS_KEY, status)
            })
            .catch(() => {
              if (isCurrent(token)) setHasCurrentGame(false)
            })
          return
        }
        setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // "Continuar" button's action: picks the player's existing unfinished game back up
  // instead of creating a new one.
  async function resumeGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = daily
          ? dailyGameIdRef.current
            ? await getGame(dailyGameIdRef.current)
            : null
          : await getCurrentGame(gameType, mode)
        if (!isCurrent(token) || !g) return
        setScreen(applyGame(g, true) ? "playing" : "error")
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  function backToIdle() {
    discardInFlight() // discard any in-flight guess/start response that arrives later
    setScreen("idle")
    // The idle effect above only re-derives from dailyStatusQuery.value, it doesn't itself fetch -
    // without this explicit revalidate, returning to idle would keep showing whatever "daily-status"
    // last resolved to instead of re-checking (e.g. after a finished/in-progress game was abandoned).
    if (daily) revalidate(DAILY_STATUS_KEY, getDailyStatus)
  }

  // For when the player's own action just finished today's daily (the round hook/game component
  // already has the final GameOut's id and score in hand) - pushes it into the "daily-status" cache
  // immediately instead of waiting for the next revalidation's round trip. `gameId` is needed
  // because the cached entry for this mode was last written while still "not_played" (game_id
  // null) - without passing it here, DailySection's "share all" would drop this mode until the next
  // real revalidation fills game_id back in. No-op for non-daily games.
  function markDailyFinished(gameId: string, score: number) {
    // Nothing to read-modify-write if this mode's status was never fetched yet (shouldn't happen in
    // practice: reaching a playable daily round means the idle screen's own useLiveQuery already
    // populated this key) - skip rather than fabricate a DailyStatusOut for the other modes we don't
    // know about; the next real revalidation (e.g. backToIdle's) fills it in correctly.
    if (!daily || !dailyStatusQuery.value) return
    updateCached<DailyStatusOut>(DAILY_STATUS_KEY, (prev) => {
      const base = prev ?? dailyStatusQuery.value!
      return {
        ...base,
        modes: base.modes.map((m) =>
          m.game_type === gameType && m.mode === mode
            ? { ...m, status: "finished", game_id: gameId, score }
            : m,
        ),
      }
    })
  }

  // For when the player's own action just finished a *non-daily* game with a new personal best -
  // pushes it into the "game-records" cache immediately instead of
  // waiting for the next time the main menu mounts and revalidates. Daily games never touch this
  // key: ScoresService.get_personal_records excludes them (a daily score isn't comparable to
  // normal play), same reason markDailyFinished above is a no-op for non-daily games.
  function markRecordBeaten(score: number) {
    if (daily) return
    const prev = peekCached<GameRecordsOut>(GAME_RECORDS_KEY)
    // Nothing to read-modify-write if the main menu's own useLiveQuery never populated this key in
    // this tab session yet - skip rather than fabricate a records list missing every other mode;
    // the next real mount of the menu fills it in correctly (with this score already included,
    // since it's already persisted server-side by the time this runs).
    if (!prev) return
    const existing = prev.records.find((r) => r.game_type === gameType && r.mode === mode)
    if (existing && existing.best_score >= score) return
    updateCached<GameRecordsOut>(GAME_RECORDS_KEY, (p) => {
      const base = p ?? prev
      return {
        records: existing
          ? base.records.map((r) =>
              r.game_type === gameType && r.mode === mode ? { ...r, best_score: score } : r,
            )
          : [...base.records, { game_type: gameType, mode, best_score: score }],
      }
    })
  }

  return {
    screen,
    setScreen,
    busy,
    setBusy,
    hasCurrentGame,
    startGame,
    resumeGame,
    backToIdle,
    markDailyFinished,
    markRecordBeaten,
    isCurrent,
    guarded,
  }
}
