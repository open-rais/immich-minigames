import { useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { createGame, getGame, personThumbnailUrl, playRound } from "../../api/games"
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

export function ImmichdleGame({ coverUrl }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)
  const [game, setGame] = useState<GameState | null>(null)
  const [pendingRoundId, setPendingRoundId] = useState<string | null>(null)
  const [history, setHistory] = useState<ImmichdleRoundOut[]>([])
  // Stable reference across renders that don't change history - PersonSearchInput's debounced
  // search effect depends on excludeIds by reference (see its own docstring, and the other
  // consumers - SkinPicker/AdminUserRow/FaceGuessPopover - that already follow this contract).
  const guessedIds = useMemo(() => new Set(history.map((r) => r.guess_person_id!)), [history])

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

        let targetName: string | null = null
        let targetPersonId: string | null = null
        if (result.finished) {
          const finalState = await getGame(game.id)
          if (!isCurrent(token)) return
          targetName = finalState.target_person_name ?? null
          targetPersonId = finalState.target_person_id ?? null
        }

        setHistory((h) => [result.answered_round as ImmichdleRoundOut, ...h])
        setGame((g) =>
          g
            ? { ...g, score: result.score, finished: result.finished, won: result.correct === true, targetName, targetPersonId }
            : g,
        )
        setPendingRoundId(result.next_round ? result.next_round.id : null)
        if (result.finished) setScreen("finished")
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

      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center gap-4 pt-14 md:pt-16">
        {/* Search bar stays narrower/centered - the table below is free to be wider on desktop
            (up to the outer max-w-4xl), matching the rest of the app's cards rather than smashdle's
            own full-bleed layout. */}
        <div className="w-full md:max-w-md">
          <PersonSearchInput
            excludeIds={guessedIds}
            onSelect={handleGuess}
            disabled={busy || !pendingRoundId}
            focusOnTypeAnywhere
          />
        </div>

        <GuessTable history={history} />
      </div>
    </div>
  )
}
