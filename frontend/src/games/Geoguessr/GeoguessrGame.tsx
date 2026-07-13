import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { assetThumbnailUrl, createGame, playGeoguessrRound } from "../../api/games"
import type { GameOut, GeoguessrRoundOut, RoundOut } from "../../api/types"
import { BackButton } from "../shared/BackButton"
import { Button } from "../shared/Button"
import { ScoreBadge } from "../shared/ScoreBadge"
import { AssetPhoto } from "./AssetPhoto"
import { MapPicker } from "./MapPicker"

const GAME_TYPE = "geoguessr"
const MODE = "distanceBetweenGuess"
const TOTAL_ROUNDS = 5 // mirrors backend/src/games/geoguessr.py's TOTAL_ROUNDS - display only
// Longer than MoreOrLess's own REVEAL_HOLD_MS (1400ms) - there's more to take in here (the map's
// own 600ms fitBounds animation, plus reading both the score and the distance).
const REVEAL_HOLD_MS = 2400

type Screen = "idle" | "playing" | "finished" | "error"
type RoundPhase = "guessing" | "submitting" | "revealed"

// This component only ever creates/plays "geoguessr" games (see GAME_TYPE/MODE above), so a
// mismatched game_type here means the backend returned something unexpected.
function assertGeoguessr(round: RoundOut): asserts round is GeoguessrRoundOut {
  if (round.game_type !== "geoguessr") throw new Error(`expected a geoguessr round, got ${round.game_type}`)
}

export function GeoguessrGame() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)

  const [game, setGame] = useState<GameOut | null>(null)
  const [round, setRound] = useState<GeoguessrRoundOut | null>(null)
  const [pendingNextRound, setPendingNextRound] = useState<GeoguessrRoundOut | null>(null)
  const [phase, setPhase] = useState<RoundPhase>("guessing")
  const [pin, setPin] = useState<{ lat: number; lng: number } | null>(null)

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
      assertGeoguessr(firstRound)
      setGame(g)
      setRound(firstRound)
      setPendingNextRound(null)
      setPin(null)
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
    if (guessInFlightRef.current || !game || !round || !pin || phase !== "guessing") return
    guessInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    setPhase("submitting")
    try {
      const result = await playGeoguessrRound(game.id, round.id, pin.lat, pin.lng)
      if (requestTokenRef.current !== token) return
      assertGeoguessr(result.answered_round)
      if (result.next_round) assertGeoguessr(result.next_round)
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

  // Same pattern as MoreOrLessGame.tsx's own reveal-hold effect: once a guess is revealed, wait a
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
      setPin(null)
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
        <BackButton label={t("geoguessr.back")} onClick={backToMenu} />
        <h1 className="text-3xl font-bold text-ink">{t("geoguessr.title")}</h1>
        <p className="max-w-md text-muted">{t("geoguessr.start.description")}</p>
        <Button variant="primary" className="px-8 py-3" onClick={startGame} disabled={busy}>
          {t("geoguessr.start.cta")}
        </Button>
      </div>
    )
  }

  if (screen === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
        <BackButton label={t("geoguessr.back")} onClick={backToMenu} />
        <p className="text-body">{t("geoguessr.error.message")}</p>
        <Button variant="primary" className="px-6 py-3" onClick={startGame} disabled={busy}>
          {t("geoguessr.error.retry")}
        </Button>
      </div>
    )
  }

  if (screen === "finished") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <BackButton label={t("geoguessr.back")} onClick={backToMenu} />
        <h1 className="text-3xl font-bold text-ink">{t("geoguessr.finished.title")}</h1>
        <p className="text-xl text-muted">{t("geoguessr.finished.finalScore", { score: game?.score ?? 0 })}</p>
        <Button variant="primary" className="px-8 py-3" onClick={startGame} disabled={busy}>
          {t("geoguessr.result.playAgain")}
        </Button>
      </div>
    )
  }

  if (!game || !round) return null

  const revealed = phase === "revealed"
  const actual =
    revealed && round.actual_latitude !== null && round.actual_longitude !== null
      ? { lat: round.actual_latitude, lng: round.actual_longitude }
      : null

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <AssetPhoto key={round.asset_id} src={assetThumbnailUrl(round.asset_id)} alt={t("geoguessr.title")} />

      <BackButton label={t("geoguessr.back")} onClick={backToIdle} />
      <ScoreBadge label={t("geoguessr.score")} score={game.score} />

      <div className="fixed top-[18px] left-1/2 z-30 -translate-x-1/2 rounded-full bg-badge-bg px-4 py-2 shadow-card md:top-7">
        <span className="text-[11px] font-bold tracking-wide text-badge-label uppercase md:text-[13px]">
          {t("geoguessr.roundOf", { current: round.round_index, total: TOTAL_ROUNDS })}
        </span>
      </div>

      <MapPicker pin={pin} onPinChange={setPin} actual={actual} disabled={phase !== "guessing"} forceExpanded={revealed} />

      {phase === "guessing" && (
        <div className="fixed bottom-[18px] left-[18px] z-30 md:bottom-7 md:left-10">
          <Button
            variant="primary"
            className="px-6 py-3 shadow-card"
            onClick={handleConfirmGuess}
            disabled={pin === null || busy}
          >
            {t("geoguessr.confirmGuess")}
          </Button>
        </div>
      )}

      {revealed && round.distance_km !== null && round.score_delta !== null && (
        <div className="fixed bottom-[18px] left-[18px] z-30 md:bottom-7 md:left-10">
          <div className="rounded-2xl border border-line bg-white px-5 py-3 text-left shadow-card">
            <p className="font-mono text-lg font-bold text-ink">
              {t("geoguessr.result.points", { score: round.score_delta })}
            </p>
            <p className="text-sm font-semibold text-muted">
              {t("geoguessr.result.distance", { distance: round.distance_km.toFixed(1) })}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
