import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types"
import type { RoundOut, WhosThatPersonRoundOut } from "../../api/types"
import type { GameComponentProps } from "../catalog"
import { Button } from "../shared/Button"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { RevealResultCard } from "../shared/RevealResultCard"
import { RoundBadge } from "../shared/RoundBadge"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useRoundGame } from "../shared/useRoundGame"
import { IncognitoPhoto } from "./IncognitoPhoto"

const GAME_TYPE = GameType.WhosThatPerson
const MODE = Mode.NamedFaces
// Mirrors backend/src/games/whos_that_person.py's _TOTAL_PEOPLE - display only.
const TOTAL_PEOPLE = 15
// Longer than Geoguessr/Dateguessr's 2400ms - a round can reveal several faces at once, so the
// player needs more time to read all of them.
const REVEAL_HOLD_MS = 2800

// This component only ever creates/plays "whos-that-person" games, so a mismatched game_type means
// the backend returned something unexpected - same convention as every other game.
function isWhosThatPersonRound(round: RoundOut): round is WhosThatPersonRoundOut {
  return round.game_type === GameType.WhosThatPerson
}

export function WhosThatPersonGame({ coverUrl }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [guesses, setGuesses] = useState<Record<string, string>>({})
  const [activeFaceId, setActiveFaceId] = useState<string | null>(null)
  // Running "N of 15 people asked" progress, since (unlike every other game) the round count isn't
  // fixed - a round can cover 1-5 people. seenRoundIdsRef guards against double-counting the same
  // round on a re-render (e.g. once it's answered and its own fields update).
  const [peopleAskedTotal, setPeopleAskedTotal] = useState(0)
  const seenRoundIdsRef = useRef<Set<string>>(new Set())

  const { screen, busy, game, round, phase, revealed, startGame, submitGuess, backToIdle } = useRoundGame<
    WhosThatPersonRoundOut,
    Record<string, string>
  >({
    gameType: GAME_TYPE,
    mode: MODE,
    revealHoldMs: REVEAL_HOLD_MS,
    isRound: isWhosThatPersonRound,
    playRound: (gameId, roundId, guess) => playRound(gameId, roundId, { guesses: guess }),
    onNewRound: () => {
      setGuesses({})
      setActiveFaceId(null)
    },
  })

  useEffect(() => {
    if (!round || seenRoundIdsRef.current.has(round.id)) return
    seenRoundIdsRef.current.add(round.id)
    setPeopleAskedTotal((total) => total + round.faces.length)
  }, [round])

  function handleStart() {
    seenRoundIdsRef.current.clear()
    setPeopleAskedTotal(0)
    startGame()
  }

  function handleGuess(faceId: string, personId: string) {
    setGuesses((g) => ({ ...g, [faceId]: personId }))
  }

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("whosThatPerson.title")}
        modeTitle={t("whosThatPerson.modes.namedFaces")}
        description={t("whosThatPerson.start.description")}
        coverUrl={coverUrl}
        onStart={handleStart}
        onBack={backToMenu}
        busy={busy}
      />
    )
  }

  if (screen === "error") {
    return <ErrorScreen onRetry={handleStart} onBack={backToMenu} busy={busy} />
  }

  if (screen === "finished") {
    return <FinishedScreen score={game?.score ?? 0} onPlayAgain={handleStart} onBack={backToMenu} busy={busy} />
  }

  if (!game || !round) return null

  const allAnswered = round.faces.every((face) => guesses[face.face_id])
  const correctCount = round.faces.filter((face) => face.correct).length

  return (
    <div className="h-dvh w-full overflow-hidden bg-app-bg">
      <IncognitoPhoto
        key={round.id}
        assetId={round.asset_id}
        faces={round.faces}
        guesses={guesses}
        activeFaceId={activeFaceId}
        onSelectFace={setActiveFaceId}
        onGuess={handleGuess}
        phase={phase}
      />

      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />
      <RoundBadge label={t("whosThatPerson.progress", { current: peopleAskedTotal, total: TOTAL_PEOPLE })} />

      {phase === "guessing" && (
        <div className="fixed bottom-[18px] left-[18px] z-30 md:bottom-7 md:left-10">
          <Button
            variant="primary"
            className="px-6 py-3 shadow-card"
            onClick={() => submitGuess(guesses)}
            disabled={!allAnswered || busy}
          >
            {t("whosThatPerson.submit")}
          </Button>
        </div>
      )}

      {revealed && round.score_delta !== null && (
        <RevealResultCard
          positionClassName="bottom-[18px] left-[18px] md:bottom-7 md:left-10"
          scoreDelta={round.score_delta}
          subtitle={t("whosThatPerson.result.correctCount", { correct: correctCount, total: round.faces.length })}
        />
      )}
    </div>
  )
}
