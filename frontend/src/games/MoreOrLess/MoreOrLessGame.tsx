import { useEffect, useState } from "react"
import type { TransitionEvent } from "react"
import { useTranslation } from "react-i18next"

import { createGame, getGame, personThumbnailUrl, playRound } from "../../api/games"
import type { GameOut, Guess, RoundOut } from "../../api/types"
import { BackButton } from "./BackButton"
import type { CandidatePhase } from "./CandidateCard"
import { CandidateCard } from "./CandidateCard"
import { PersonCard } from "./PersonCard"
import { ScoreBadge } from "./ScoreBadge"
import { useCountUp } from "./useCountUp"

const GAME_TYPE = "more-or-less"
const MODE = "personAssets"

const COUNT_DURATION_MS = 1600
const REVEAL_HOLD_MS = 1400
const SLIDE_DISTANCE_PX = 340 // card width (300) + gap (40)

type Screen = "idle" | "playing" | "finished" | "error"

export function MoreOrLessGame() {
  const { t } = useTranslation()

  const [screen, setScreen] = useState<Screen>("idle")
  const [starting, setStarting] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")

  const [game, setGame] = useState<GameOut | null>(null)
  const [reference, setReference] = useState<{ id: string; name: string; assetCount: number } | null>(null)
  const [candidateId, setCandidateId] = useState("")
  const [candidateName, setCandidateName] = useState("")
  const [currentRoundId, setCurrentRoundId] = useState("")
  const [candidatePhase, setCandidatePhase] = useState<CandidatePhase>("guessing")
  const [countTarget, setCountTarget] = useState<number | null>(null)
  const [correct, setCorrect] = useState<boolean | null>(null)
  const [nextRound, setNextRound] = useState<RoundOut | null>(null)
  const [sliding, setSliding] = useState(false)
  const [transitionEnabled, setTransitionEnabled] = useState(true)

  const { value: displayCount, done: countDone } = useCountUp(countTarget, COUNT_DURATION_MS)

  useEffect(() => {
    if (countDone && candidatePhase === "counting") {
      setCandidatePhase("revealed")
    }
  }, [countDone, candidatePhase])

  useEffect(() => {
    if (candidatePhase !== "revealed") return
    const timer = setTimeout(() => {
      if (correct && nextRound) {
        setSliding(true)
      } else {
        setScreen("finished")
      }
    }, REVEAL_HOLD_MS)
    return () => clearTimeout(timer)
  }, [candidatePhase, correct, nextRound])

  useEffect(() => {
    if (transitionEnabled) return
    const raf = requestAnimationFrame(() => setTransitionEnabled(true))
    return () => cancelAnimationFrame(raf)
  }, [transitionEnabled])

  async function startGame() {
    setStarting(true)
    try {
      const g = await createGame(GAME_TYPE, MODE)
      const round = g.rounds[g.rounds.length - 1]
      setGame(g)
      setReference({ id: round.reference_id, name: round.reference_name, assetCount: round.reference_asset_count })
      setCandidateId(round.candidate_id)
      setCandidateName(round.candidate_name)
      setCurrentRoundId(round.id)
      setCandidatePhase("guessing")
      setCountTarget(null)
      setCorrect(null)
      setNextRound(null)
      setSliding(false)
      setScreen("playing")
    } catch {
      setErrorMessage(t("moreOrLess.error.message"))
      setScreen("error")
    } finally {
      setStarting(false)
    }
  }

  async function handleGuess(guess: Guess) {
    if (!game || candidatePhase !== "guessing") return
    setCandidatePhase("counting")
    try {
      const result = await playRound(game.id, currentRoundId, guess)
      const updatedGame = await getGame(game.id)
      const answeredRound = updatedGame.rounds.find((r) => r.id === currentRoundId)
      setGame((g) => (g ? { ...g, score: result.score, finished: result.finished } : g))
      setCorrect(result.correct)
      setNextRound(result.next_round)
      setCountTarget(answeredRound?.candidate_asset_count ?? 0)
    } catch {
      setErrorMessage(t("moreOrLess.error.message"))
      setScreen("error")
    }
  }

  function handleSlideEnd(e: TransitionEvent<HTMLDivElement>) {
    if (e.target !== e.currentTarget || e.propertyName !== "transform") return
    if (!nextRound || countTarget === null) return

    setTransitionEnabled(false)
    setSliding(false)
    setReference({ id: candidateId, name: candidateName, assetCount: countTarget })
    setCandidateId(nextRound.candidate_id)
    setCandidateName(nextRound.candidate_name)
    setCurrentRoundId(nextRound.id)
    setCandidatePhase("guessing")
    setCountTarget(null)
    setCorrect(null)
    setNextRound(null)
  }

  function backToIdle() {
    setScreen("idle")
  }

  if (screen === "idle") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <h1 className="text-3xl font-bold text-ink">{t("moreOrLess.title")}</h1>
        <p className="max-w-md text-muted">{t("moreOrLess.start.description")}</p>
        <button
          onClick={startGame}
          disabled={starting}
          className="rounded-full bg-primary px-8 py-3 text-[15px] font-bold text-white transition-colors hover:bg-primary-hover disabled:opacity-60"
        >
          {t("moreOrLess.start.cta")}
        </button>
      </div>
    )
  }

  if (screen === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
        <p className="text-body">{errorMessage}</p>
        <button
          onClick={startGame}
          className="rounded-full bg-primary px-6 py-3 text-[15px] font-bold text-white transition-colors hover:bg-primary-hover"
        >
          {t("moreOrLess.error.retry")}
        </button>
      </div>
    )
  }

  if (screen === "finished") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <h1 className="text-3xl font-bold text-ink">{t("moreOrLess.finished.title")}</h1>
        <p className="text-xl text-muted">{t("moreOrLess.finished.finalScore", { score: game?.score ?? 0 })}</p>
        <button
          onClick={startGame}
          className="rounded-full bg-primary px-8 py-3 text-[15px] font-bold text-white transition-colors hover:bg-primary-hover"
        >
          {t("moreOrLess.result.playAgain")}
        </button>
      </div>
    )
  }

  if (!game || !reference) return null

  return (
    <div className="flex min-h-screen flex-col bg-app-bg px-10 py-7">
      <div className="flex items-center justify-between">
        <BackButton label={t("moreOrLess.back")} onClick={backToIdle} />
        <ScoreBadge score={game.score} />
      </div>

      <div className="flex flex-1 items-center justify-center">
        <div className="flex items-start gap-10">
          <div className="w-[300px]">
            <PersonCard
              name={reference.name}
              assetCount={reference.assetCount}
              thumbnailUrl={personThumbnailUrl(reference.id)}
            />
          </div>

          <div className="relative w-[300px]">
            {nextRound && (
              <div className="absolute inset-0 z-0">
                <CandidateCard
                  name={nextRound.candidate_name}
                  thumbnailUrl={personThumbnailUrl(nextRound.candidate_id)}
                  phase="guessing"
                  displayCount={0}
                  correct={null}
                  onGuess={() => {}}
                />
              </div>
            )}
            <div
              className="relative z-10"
              style={{
                transform: sliding ? `translateX(-${SLIDE_DISTANCE_PX}px)` : "translateX(0)",
                transition: transitionEnabled ? "transform 450ms ease-out" : "none",
              }}
              onTransitionEnd={handleSlideEnd}
            >
              <CandidateCard
                name={candidateName}
                thumbnailUrl={personThumbnailUrl(candidateId)}
                phase={candidatePhase}
                displayCount={displayCount}
                correct={correct}
                onGuess={handleGuess}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
