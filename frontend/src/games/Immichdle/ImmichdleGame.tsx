import { useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { createGame, getGame, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types"
import type { ImmichdleRoundOut, RoundOut } from "../../api/types"
import type { GameComponentProps } from "../catalog"
import { Button } from "../shared/Button"
import { ErrorScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { ScoreBadge } from "../shared/ScoreBadge"
import { BackButton } from "../shared/BackButton"
import { GuessTable } from "./GuessTable"
import { PersonSearchInput } from "./PersonSearchInput"

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
}

function FinishedScreen({ game, onPlayAgain, onBack, busy }: { game: GameState; onPlayAgain: () => void; onBack: () => void; busy: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
      <BackButton label={t("common.back")} onClick={onBack} />
      <h1 className="text-3xl font-bold text-ink">{t(game.won ? "immichdle.finished.won" : "immichdle.finished.lost")}</h1>
      {game.targetName && <p className="text-xl font-bold text-primary">{game.targetName}</p>}
      <p className="text-xl text-muted">{t("common.finished.finalScore", { score: game.score })}</p>
      <Button variant="primary" className="px-8 py-3" onClick={onPlayAgain} disabled={busy}>
        {t("common.playAgain")}
      </Button>
    </div>
  )
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

  const guessInFlightRef = useRef(false)
  const startInFlightRef = useRef(false)
  const requestTokenRef = useRef(0)

  async function startGame() {
    if (startInFlightRef.current) return
    startInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    try {
      const g = await createGame(GAME_TYPE, MODE)
      if (requestTokenRef.current !== token) return
      const round = g.rounds[g.rounds.length - 1]
      assertImmichdle(round)
      setGame({ id: g.id, score: g.score, finished: false, won: false, targetName: null })
      setPendingRoundId(round.id)
      setHistory([])
      setScreen("playing")
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      startInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
  }

  async function handleGuess(personId: string) {
    if (guessInFlightRef.current || !game || !pendingRoundId) return
    guessInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    try {
      const result = await playRound(game.id, pendingRoundId, { person_id: personId })
      if (requestTokenRef.current !== token) return
      assertImmichdle(result.answered_round)
      if (result.next_round) assertImmichdle(result.next_round)

      let targetName: string | null = null
      if (result.finished) {
        const finalState = await getGame(game.id)
        if (requestTokenRef.current !== token) return
        targetName = finalState.target_person_name ?? null
      }

      setHistory((h) => [result.answered_round as ImmichdleRoundOut, ...h])
      setGame((g) =>
        g ? { ...g, score: result.score, finished: result.finished, won: result.correct === true, targetName } : g,
      )
      setPendingRoundId(result.next_round ? result.next_round.id : null)
      if (result.finished) setScreen("finished")
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      guessInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
  }

  function backToIdle() {
    requestTokenRef.current++ // discard any in-flight guess/start response that arrives later
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
    return <FinishedScreen game={game} onPlayAgain={startGame} onBack={backToMenu} busy={busy} />
  }

  if (!game) return null

  const guessedIds = new Set(history.map((r) => r.guess_person_id!))

  return (
    <div className="flex min-h-dvh flex-col gap-4 bg-app-bg px-[18px] py-[22px] md:px-10 md:py-7">
      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />

      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center gap-4 pt-14 md:pt-16">
        {/* Search bar stays narrower/centered - the table below is free to be wider on desktop
            (up to the outer max-w-4xl), matching the rest of the app's cards rather than smashdle's
            own full-bleed layout. */}
        <div className="w-full md:max-w-md">
          <PersonSearchInput excludeIds={guessedIds} onGuess={handleGuess} disabled={busy || !pendingRoundId} />
        </div>

        <GuessTable history={history} />
      </div>
    </div>
  )
}
