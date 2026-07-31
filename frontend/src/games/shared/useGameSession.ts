import { useEffect, useRef, useState } from "react"

import { createDailyGame, getDailyStatus } from "../../api/daily"
import { apiErrorStatus } from "../../api/errors"
import { createGame, getCurrentGame, getGame } from "../../api/games"
import type { GameOut } from "../../api/types"
import { useGuardedRequests } from "./useGuardedRequests"

export type Screen = "idle" | "playing" | "finished" | "error"

// Game-lifecycle layer extracted out of useRoundGame/MoreOrLessGame/ImmichdleGame (CODE-REVIEW-
// FRONT.md A-1) - all three had copied this same block character-for-character since useRoundGame
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
  // Roadmap #G - true when this instance is playing today's daily challenge (menu/
  // DailyGameRoute.tsx) instead of a normal game. Changes which endpoint creates a game, where the
  // idle-screen "has an active game" check reads from (GET /daily's status instead of
  // get_current_game, which excludes daily games by design - see docs/TODO/DAILY-GAMES.md §4.5),
  // and that an already-finished daily jumps straight to the finished screen instead of ever
  // offering "Jugar" again.
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
  // Roadmap #e - whether the current player has an unfinished game for this (gameType, mode); null
  // while the idle-screen check below is still in flight, which IdleScreen treats the same as
  // false (an accepted brief "plain layout, then Continue pops in" flash).
  const [hasCurrentGame, setHasCurrentGame] = useState<boolean | null>(null)
  // Roadmap #G - the daily game's id, known from GET /daily's status before the player has done
  // anything - resumeGame() reads this instead of calling getCurrentGame (which never returns a
  // daily game).
  const dailyGameIdRef = useRef<string | null>(null)
  // Bumped when the idle-screen status needs re-fetching while the screen is already "idle" -
  // today only the daily 409 fallback in startGame below (docs/TODO/DAILY-GAMES.md §4.7).
  const [idleRefresh, setIdleRefresh] = useState(0)

  const { isCurrent, guarded, discardInFlight } = useGuardedRequests()
  const startInFlightRef = useRef(false)

  // Kept in a ref so the idle effect below can call the latest hydrateFinishedDaily without listing
  // it as a dependency (which would re-run the effect - and the fetch it triggers - every render).
  // applyGame doesn't need the same treatment: it's only ever called from startGame/resumeGame,
  // plain functions re-created fresh every render, not from inside a useEffect.
  const hydrateFinishedDailyRef = useRef(hydrateFinishedDaily)
  hydrateFinishedDailyRef.current = hydrateFinishedDaily

  // Re-checked every time the idle screen is (re-)shown - e.g. after backToIdle, not just on mount.
  useEffect(() => {
    if (screen !== "idle") return
    let cancelled = false

    if (daily) {
      getDailyStatus()
        .then((status) => {
          if (cancelled) return
          const modeStatus = status.modes.find((m) => m.game_type === gameType && m.mode === mode)
          dailyGameIdRef.current = modeStatus?.game_id ?? null

          if (modeStatus?.status === "finished" && modeStatus.game_id) {
            setHasCurrentGame(false)
            getGame(modeStatus.game_id)
              .then((g) => {
                if (cancelled) return
                setScreen(hydrateFinishedDailyRef.current(g) ? "finished" : "error")
              })
              .catch(() => {
                if (!cancelled) setScreen("error")
              })
            return
          }
          setHasCurrentGame(modeStatus?.status === "in_progress")
        })
        .catch(() => {
          if (!cancelled) setHasCurrentGame(false)
        })
      return () => {
        cancelled = true
      }
    }

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
  }, [screen, gameType, mode, daily, idleRefresh])

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
          // the finished (or in-progress) state, the "ya jugado" behavior of DAILY-GAMES.md §4.7.
          setHasCurrentGame(null)
          setIdleRefresh((n) => n + 1)
          return
        }
        setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // Roadmap #e - "Continuar" button's action: picks the player's existing unfinished game back up
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
    isCurrent,
    guarded,
  }
}
