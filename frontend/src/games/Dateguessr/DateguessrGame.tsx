import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { assetThumbnailUrl, createGame, playDateguessrRound } from "../../api/games"
import type { DateguessrRoundOut, GameOut, RoundOut } from "../../api/types"
import { AssetPhoto } from "../shared/AssetPhoto"
import { BackButton } from "../shared/BackButton"
import { Button } from "../shared/Button"
import { ScoreBadge } from "../shared/ScoreBadge"
import { TimelineRuler } from "./TimelineRuler"

const GAME_TYPE = "dateguessr"
const MODE = "daysToDate"
const TOTAL_ROUNDS = 5 // mirrors backend/src/games/dateguessr.py's TOTAL_ROUNDS - display only
// Same reveal-hold duration as GeoguessrGame.tsx - the ruler's own reveal animation is a bit
// shorter (TimelineRuler.tsx's REVEAL_ANIMATION_MS) but the player still needs a beat to read the
// score/days-off after it settles.
const REVEAL_HOLD_MS = 2400

type Screen = "idle" | "playing" | "finished" | "error"
type RoundPhase = "guessing" | "submitting" | "revealed"

// This component only ever creates/plays "dateguessr" games (see GAME_TYPE/MODE above), so a
// mismatched game_type here means the backend returned something unexpected.
function assertDateguessr(round: RoundOut): asserts round is DateguessrRoundOut {
  if (round.game_type !== "dateguessr") throw new Error(`expected a dateguessr round, got ${round.game_type}`)
}

export function DateguessrGame() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)

  const [game, setGame] = useState<GameOut | null>(null)
  const [round, setRound] = useState<DateguessrRoundOut | null>(null)
  const [pendingNextRound, setPendingNextRound] = useState<DateguessrRoundOut | null>(null)
  const [phase, setPhase] = useState<RoundPhase>("guessing")
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

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
      const firstRound = g.rounds[g.rounds.length - 1]
      assertDateguessr(firstRound)
      setGame(g)
      setRound(firstRound)
      setPendingNextRound(null)
      setSelectedDate(null)
      setPhase("guessing")
      setScreen("playing")
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      startInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
  }

  async function handleConfirmGuess() {
    if (guessInFlightRef.current || !game || !round || !selectedDate || phase !== "guessing") return
    guessInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    setPhase("submitting")
    try {
      const result = await playDateguessrRound(game.id, round.id, selectedDate)
      if (requestTokenRef.current !== token) return
      assertDateguessr(result.answered_round)
      if (result.next_round) assertDateguessr(result.next_round)
      setGame((g) => (g ? { ...g, score: result.score, finished: result.finished } : g))
      setRound(result.answered_round)
      setPendingNextRound(result.next_round)
      setPhase("revealed")
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      guessInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
  }

  // Same pattern as GeoguessrGame.tsx's own reveal-hold effect: once a guess is revealed, wait a
  // beat so the player can see the result, then move on automatically - no "next round" click.
  useEffect(() => {
    if (phase !== "revealed") return
    const timer = setTimeout(() => {
      if (!game || game.finished || !pendingNextRound) {
        setScreen("finished")
        return
      }
      setRound(pendingNextRound)
      setPendingNextRound(null)
      setSelectedDate(null)
      setPhase("guessing")
    }, REVEAL_HOLD_MS)
    return () => clearTimeout(timer)
  }, [phase, game, pendingNextRound])

  function backToIdle() {
    requestTokenRef.current++ // discard any in-flight guess/start response that arrives later
    setScreen("idle")
  }

  if (screen === "idle") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <BackButton label={t("dateguessr.back")} onClick={backToMenu} />
        <h1 className="text-3xl font-bold text-ink">{t("dateguessr.title")}</h1>
        <p className="max-w-md text-muted">{t("dateguessr.start.description")}</p>
        <Button variant="primary" className="px-8 py-3" onClick={startGame} disabled={busy}>
          {t("dateguessr.start.cta")}
        </Button>
      </div>
    )
  }

  if (screen === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
        <BackButton label={t("dateguessr.back")} onClick={backToMenu} />
        <p className="text-body">{t("dateguessr.error.message")}</p>
        <Button variant="primary" className="px-6 py-3" onClick={startGame} disabled={busy}>
          {t("dateguessr.error.retry")}
        </Button>
      </div>
    )
  }

  if (screen === "finished") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <BackButton label={t("dateguessr.back")} onClick={backToMenu} />
        <h1 className="text-3xl font-bold text-ink">{t("dateguessr.finished.title")}</h1>
        <p className="text-xl text-muted">{t("dateguessr.finished.finalScore", { score: game?.score ?? 0 })}</p>
        <Button variant="primary" className="px-8 py-3" onClick={startGame} disabled={busy}>
          {t("dateguessr.result.playAgain")}
        </Button>
      </div>
    )
  }

  if (!game || !round) return null

  const revealed = phase === "revealed"

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <AssetPhoto key={round.asset_id} src={assetThumbnailUrl(round.asset_id)} alt={t("dateguessr.title")} />

      <BackButton label={t("dateguessr.back")} onClick={backToIdle} />
      <ScoreBadge label={t("dateguessr.score")} score={game.score} />

      <div className="fixed top-[18px] left-1/2 z-30 -translate-x-1/2 rounded-full bg-badge-bg px-4 py-2 shadow-card md:top-7">
        <span className="text-[11px] font-bold tracking-wide text-badge-label uppercase md:text-[13px]">
          {t("dateguessr.roundOf", { current: round.round_index, total: TOTAL_ROUNDS })}
        </span>
      </div>

      <TimelineRuler
        selected={selectedDate}
        onSelectedChange={setSelectedDate}
        actual={revealed ? round.actual_date : null}
        disabled={phase !== "guessing"}
      />

      {phase === "guessing" && (
        <div className="fixed bottom-[124px] left-[18px] z-30 md:bottom-[156px] md:left-10">
          <Button
            variant="primary"
            className="px-6 py-3 shadow-card"
            onClick={handleConfirmGuess}
            disabled={selectedDate === null || busy}
          >
            {t("dateguessr.confirmGuess")}
          </Button>
        </div>
      )}

      {revealed && round.days_off !== null && round.score_delta !== null && (
        <div className="fixed bottom-[124px] left-[18px] z-30 md:bottom-[156px] md:left-10">
          <div className="rounded-2xl border border-line bg-white px-5 py-3 text-left shadow-card">
            <p className="font-mono text-lg font-bold text-ink">{t("dateguessr.result.points", { score: round.score_delta })}</p>
            <p className="text-sm font-semibold text-muted">{t("dateguessr.result.daysOff", { count: round.days_off })}</p>
          </div>
        </div>
      )}
    </div>
  )
}
