import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { assetThumbnailUrl, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types"
import type { GeoguessrRoundOut, RoundOut } from "../../api/types"
import { AssetPhoto } from "../shared/AssetPhoto"
import { BackButton } from "../shared/BackButton"
import { Button } from "../shared/Button"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundBadge } from "../shared/RoundBadge"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useRoundGame } from "../shared/useRoundGame"
import { MapPicker } from "./MapPicker"

const GAME_TYPE = GameType.Geoguessr
const MODE = Mode.DistanceBetweenGuess
const TOTAL_ROUNDS = 5 // mirrors backend/src/games/asset_rounds.py's TOTAL_ROUNDS - display only
// Longer than MoreOrLess's own REVEAL_HOLD_MS (1400ms) - there's more to take in here (the map's
// own 600ms fitBounds animation, plus reading both the score and the distance).
const REVEAL_HOLD_MS = 2400

// This component only ever creates/plays "geoguessr" games (see GAME_TYPE/MODE above), so a
// mismatched game_type means the backend returned something unexpected.
function isGeoguessrRound(round: RoundOut): round is GeoguessrRoundOut {
  return round.game_type === GameType.Geoguessr
}

type Pin = { lat: number; lng: number }

export function GeoguessrGame() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [pin, setPin] = useState<Pin | null>(null)
  const { screen, busy, game, round, phase, revealed, startGame, submitGuess, backToIdle } = useRoundGame<
    GeoguessrRoundOut,
    Pin
  >({
    gameType: GAME_TYPE,
    mode: MODE,
    revealHoldMs: REVEAL_HOLD_MS,
    isRound: isGeoguessrRound,
    playRound: (gameId, roundId, guess) => playRound(gameId, roundId, { latitude: guess.lat, longitude: guess.lng }),
    onNewRound: () => setPin(null),
  })

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("geoguessr.title")}
        description={t("geoguessr.start.description")}
        onStart={startGame}
        onBack={backToMenu}
        busy={busy}
      />
    )
  }

  if (screen === "error") {
    return <ErrorScreen onRetry={startGame} onBack={backToMenu} busy={busy} />
  }

  if (screen === "finished") {
    return <FinishedScreen score={game?.score ?? 0} onPlayAgain={startGame} onBack={backToMenu} busy={busy} />
  }

  if (!game || !round) return null

  const actual =
    revealed && round.actual_latitude !== null && round.actual_longitude !== null
      ? { lat: round.actual_latitude, lng: round.actual_longitude }
      : null

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <AssetPhoto key={round.asset_id} src={assetThumbnailUrl(round.asset_id)} alt={t("geoguessr.title")} />

      <BackButton label={t("common.back")} onClick={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />
      <RoundBadge current={round.round_index} total={TOTAL_ROUNDS} />

      <MapPicker pin={pin} onPinChange={setPin} actual={actual} disabled={phase !== "guessing"} forceExpanded={revealed} />

      {phase === "guessing" && (
        <div className="fixed bottom-[18px] left-[18px] z-30 md:bottom-7 md:left-10">
          <Button
            variant="primary"
            className="px-6 py-3 shadow-card"
            onClick={() => pin && submitGuess(pin)}
            disabled={pin === null || busy}
          >
            {t("common.confirmGuess")}
          </Button>
        </div>
      )}

      {revealed && round.distance_km !== null && round.score_delta !== null && (
        <RevealResultCard
          positionClassName="bottom-[18px] left-[18px] md:bottom-7 md:left-10"
          scoreDelta={round.score_delta}
          subtitle={t("geoguessr.result.distance", { distance: round.distance_km.toFixed(1) })}
        />
      )}
    </div>
  )
}
