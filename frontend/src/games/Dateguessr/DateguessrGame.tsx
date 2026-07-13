import { useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { assetThumbnailUrl, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types"
import type { DateguessrRoundOut, RoundOut } from "../../api/types"
import { AssetPhoto } from "../shared/AssetPhoto"
import { BackButton } from "../shared/BackButton"
import { Button } from "../shared/Button"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundBadge } from "../shared/RoundBadge"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useRoundGame } from "../shared/useRoundGame"
import { TimelineRuler } from "./TimelineRuler"

const GAME_TYPE = GameType.Dateguessr
const MODE = Mode.DaysToDate
const TOTAL_ROUNDS = 5 // mirrors backend/src/games/asset_rounds.py's TOTAL_ROUNDS - display only
// Same reveal-hold duration as GeoguessrGame - the ruler's own reveal animation is a bit shorter
// (TimelineRuler.tsx's REVEAL_ANIMATION_MS) but the player still needs a beat to read the
// score/days-off after it settles.
const REVEAL_HOLD_MS = 2400

// This component only ever creates/plays "dateguessr" games (see GAME_TYPE/MODE above), so a
// mismatched game_type means the backend returned something unexpected.
function isDateguessrRound(round: RoundOut): round is DateguessrRoundOut {
  return round.game_type === GameType.Dateguessr
}

export function DateguessrGame() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const { screen, busy, game, round, phase, revealed, startGame, submitGuess, backToIdle } = useRoundGame<
    DateguessrRoundOut,
    string
  >({
    gameType: GAME_TYPE,
    mode: MODE,
    revealHoldMs: REVEAL_HOLD_MS,
    isRound: isDateguessrRound,
    playRound: (gameId, roundId, guess) => playRound(gameId, roundId, { date: guess }),
    onNewRound: () => setSelectedDate(null),
  })

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("dateguessr.title")}
        description={t("dateguessr.start.description")}
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

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <AssetPhoto key={round.asset_id} src={assetThumbnailUrl(round.asset_id)} alt={t("dateguessr.title")} />

      <BackButton label={t("common.back")} onClick={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />
      <RoundBadge current={round.round_index} total={TOTAL_ROUNDS} />

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
            onClick={() => selectedDate && submitGuess(selectedDate)}
            disabled={selectedDate === null || busy}
          >
            {t("common.confirmGuess")}
          </Button>
        </div>
      )}

      {revealed && round.days_off !== null && round.score_delta !== null && (
        <RevealResultCard
          positionClassName="bottom-[124px] left-[18px] md:bottom-[156px] md:left-10"
          scoreDelta={round.score_delta}
          subtitle={t("dateguessr.result.daysOff", { count: round.days_off })}
        />
      )}
    </div>
  )
}
