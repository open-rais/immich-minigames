import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { createGame, getCurrentGame, getGame, personThumbnailUrl, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types"
import type { ImmichdleRoundOut, RoundOut } from "../../api/types"
import type { GameComponentProps } from "../catalog"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { PersonAvatar } from "../shared/PersonAvatar"
import { ScoreBadge } from "../shared/ScoreBadge"
import { PersonSearchInput } from "../shared/PersonSearchInput"
import { useGuardedRequests } from "../shared/useGuardedRequests"
import { GuessTable } from "./GuessTable"

const GAME_TYPE = GameType.Immichdle
const MODE = Mode.Person

type Screen = "idle" | "playing" | "finished" | "error"

// This component only ever creates/plays "immichdle" games, so a mismatched game_type here means
// the backend returned something unexpected - fail loudly, same convention as MoreOrLessGame.tsx.
function assertImmichdle(round: RoundOut): asserts round is ImmichdleRoundOut {
  if (round.game_type !== GameType.Immichdle) throw new Error(`expected an immichdle round, got ${round.game_type}`)
}

interface GameState {
  id: string
  score: number
  finished: boolean
  won: boolean
  targetName: string | null
  targetPersonId: string | null
}

export function ImmichdleGame({ coverUrl, hasRoundsView }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)
  const [game, setGame] = useState<GameState | null>(null)
  const [pendingRoundId, setPendingRoundId] = useState<string | null>(null)
  const [history, setHistory] = useState<ImmichdleRoundOut[]>([])
  // §7 of docs/TODO/UI-ENHANCEMENTS.md - the guess-reveal sequence. `animatingRoundId` is the row
  // GuessTable/AnimatedGuessRow is currently running its own entrance/reveal timers for; the effect
  // below only advances past it once that row reports done *and* (only relevant when this was the
  // game's last guess) the target-person fetch below has also resolved - whichever finishes last.
  const [animatingRoundId, setAnimatingRoundId] = useState<string | null>(null)
  const [rowAnimationDone, setRowAnimationDone] = useState(false)
  const [targetFetchDone, setTargetFetchDone] = useState(true)
  // Stable reference across renders that don't change history - PersonSearchInput's debounced
  // search effect depends on excludeIds by reference (see its own docstring, and the other
  // consumers - SkinPicker/AdminUserRow/FaceGuessPopover - that already follow this contract).
  const guessedIds = useMemo(() => new Set(history.map((r) => r.guess_person_id!)), [history])

  // Roadmap #e - whether the current player has an unfinished game for this mode; null while the
  // idle-screen check below is still in flight (IdleScreen treats that the same as false).
  const [hasCurrentGame, setHasCurrentGame] = useState<boolean | null>(null)

  const { isCurrent, guarded, discardInFlight } = useGuardedRequests()
  // One in-flight ref per action - start vs guess don't need to block each other, but each needs
  // its own re-entrancy guard against a fast double-click firing before React re-renders.
  const guessInFlightRef = useRef(false)
  const startInFlightRef = useRef(false)

  async function startGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = await createGame(GAME_TYPE, MODE)
        if (!isCurrent(token)) return
        const round = g.rounds[g.rounds.length - 1]
        assertImmichdle(round)
        setGame({ id: g.id, score: g.score, finished: false, won: false, targetName: null, targetPersonId: null })
        setPendingRoundId(round.id)
        setHistory([])
        setAnimatingRoundId(null)
        setRowAnimationDone(false)
        setTargetFetchDone(true)
        setScreen("playing")
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // Re-checked every time the idle screen is (re-)shown - roadmap #e's "Continuar" affordance.
  useEffect(() => {
    if (screen !== "idle") return
    let cancelled = false
    getCurrentGame(GAME_TYPE, MODE)
      .then((g) => {
        if (!cancelled) setHasCurrentGame(g !== null)
      })
      .catch(() => {
        if (!cancelled) setHasCurrentGame(false)
      })
    return () => {
      cancelled = true
    }
  }, [screen])

  // Roadmap #e - "Continuar" button's action: rebuilds `history` from every already-answered round
  // of the resumed game (all but the last, still-pending one), newest-first to match how a live
  // game accumulates it (see handleGuess's setHistory below). No reveal animation on resume - the
  // player just sees the table as it already stood.
  async function resumeGame() {
    await guarded(startInFlightRef, async (token) => {
      setBusy(true)
      try {
        const g = await getCurrentGame(GAME_TYPE, MODE)
        if (!isCurrent(token) || !g) return
        const answered = g.rounds.slice(0, -1)
        answered.forEach(assertImmichdle)
        const pending = g.rounds[g.rounds.length - 1]
        assertImmichdle(pending)
        setGame({ id: g.id, score: g.score, finished: false, won: false, targetName: null, targetPersonId: null })
        setPendingRoundId(pending.id)
        setHistory([...(answered as ImmichdleRoundOut[])].reverse())
        setAnimatingRoundId(null)
        setRowAnimationDone(false)
        setTargetFetchDone(true)
        setScreen("playing")
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  async function handleGuess(personId: string) {
    if (!game || !pendingRoundId) return
    await guarded(guessInFlightRef, async (token) => {
      setBusy(true)
      try {
        const result = await playRound(game.id, pendingRoundId, { person_id: personId })
        if (!isCurrent(token)) return
        assertImmichdle(result.answered_round)
        if (result.next_round) assertImmichdle(result.next_round)
        const answeredRound = result.answered_round as ImmichdleRoundOut

        setHistory((h) => [answeredRound, ...h])
        setGame((g) => (g ? { ...g, score: result.score, finished: result.finished, won: result.correct === true } : g))
        setPendingRoundId(result.next_round ? result.next_round.id : null)

        // Kicks off the row's own entrance/reveal timers (AnimatedGuessRow, via GuessTable) - the
        // watcher effect below advances the screen once it reports done.
        setAnimatingRoundId(answeredRound.id)
        setRowAnimationDone(false)

        // The target-person fetch runs in parallel with that animation instead of blocking before
        // it (so the row doesn't sit frozen waiting on the network) - only relevant when this guess
        // just finished the game; otherwise there's nothing to fetch and the row alone gates the
        // watcher effect below.
        if (result.finished) {
          setTargetFetchDone(false)
          getGame(game.id)
            .then((finalState) => {
              if (!isCurrent(token)) return
              setGame((g) =>
                g
                  ? {
                      ...g,
                      targetName: finalState.target_person_name ?? null,
                      targetPersonId: finalState.target_person_id ?? null,
                    }
                  : g,
              )
              setTargetFetchDone(true)
            })
            .catch(() => {
              if (isCurrent(token)) setScreen("error")
            })
        } else {
          setTargetFetchDone(true)
        }
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // Advances past the guess-reveal sequence once both the row's own animation and (only when this
  // guess finished the game) the target fetch above have resolved - whichever finishes last is what
  // actually triggers this, without branching on win/lose (§7 [DECISIÓN F0]).
  useEffect(() => {
    if (!animatingRoundId || !rowAnimationDone || !targetFetchDone) return
    setAnimatingRoundId(null)
    if (game?.finished) setScreen("finished")
  }, [animatingRoundId, rowAnimationDone, targetFetchDone, game?.finished])

  function backToIdle() {
    discardInFlight() // discard any in-flight guess/start response that arrives later
    setScreen("idle")
  }

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("immichdle.title")}
        modeTitle={t("immichdle.modes.person")}
        description={t("immichdle.start.description")}
        coverUrl={coverUrl}
        onStart={startGame}
        onBack={backToMenu}
        busy={busy}
        hasCurrentGame={hasCurrentGame}
        onContinue={resumeGame}
      />
    )
  }

  if (screen === "error") {
    return <ErrorScreen onRetry={startGame} onBack={backToMenu} busy={busy} />
  }

  if (screen === "finished" && game) {
    return (
      <FinishedScreen
        score={game.score}
        onPlayAgain={startGame}
        onBack={backToMenu}
        busy={busy}
        gameId={game.id}
        hasRoundsView={hasRoundsView}
        title={t(game.won ? "immichdle.finished.won" : "immichdle.finished.lost")}
      >
        {game.targetPersonId && (
          <div className="flex flex-col items-center gap-2">
            <PersonAvatar src={personThumbnailUrl(game.targetPersonId)} alt={game.targetName ?? ""} size="lg" />
            {game.targetName && <p className="text-xl font-bold text-primary">{game.targetName}</p>}
          </div>
        )}
      </FinishedScreen>
    )
  }

  if (!game) return null

  return (
    <div className="flex min-h-dvh flex-col gap-4 bg-app-bg px-[18px] py-[22px] md:px-10 md:py-7">
      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-4 pt-14 md:pt-16">
        {/* Search bar stays narrower/centered - the table below is free to be wider on desktop
            (up to the outer max-w-5xl), matching the rest of the app's cards rather than smashdle's
            own full-bleed layout. max-w-5xl (not -4xl) is deliberate: GuessTable's own natural
            desktop width (PERSON_COL + 6*CLUE_COL = 224+672 = 896px, plus its border) lands right at
            -4xl's 896px cap, so it used to clip by a couple pixels and trigger an unnecessary
            horizontal scrollbar on desktop even though the table visually "fits". */}
        <div className="w-full md:max-w-md">
          <PersonSearchInput
            excludeIds={guessedIds}
            onSelect={handleGuess}
            disabled={busy || !pendingRoundId || animatingRoundId !== null}
            focusOnTypeAnywhere
          />
        </div>

        <GuessTable
          history={history}
          animatingRoundId={animatingRoundId}
          onRowAnimationDone={() => setRowAnimationDone(true)}
        />
      </div>
    </div>
  )
}
