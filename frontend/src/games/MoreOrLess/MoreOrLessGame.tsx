import { useEffect, useRef, useState } from "react"
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
const MOBILE_BREAKPOINT_QUERY = "(min-width: 768px)" // matches Tailwind's `md:`
// Cards are side-by-side on desktop (horizontal slide) but stacked on mobile (vertical slide) -
// these must match the gap-10/gap-4 classes on the row/column wrapper below.
const DESKTOP_GAP_PX = 40
const MOBILE_GAP_PX = 16

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
  const [slideOffset, setSlideOffset] = useState({ x: 0, y: 0 })
  const slidingCardRef = useRef<HTMLDivElement>(null)

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
        const el = slidingCardRef.current
        const isDesktop = window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
        if (el) {
          setSlideOffset(
            isDesktop
              ? { x: -(el.offsetWidth + DESKTOP_GAP_PX), y: 0 }
              : { x: 0, y: -(el.offsetHeight + MOBILE_GAP_PX) },
          )
        }
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
    <div className="flex h-dvh flex-col overflow-hidden bg-app-bg px-[18px] py-[22px] md:px-10 md:py-7">
      {/* Fixed/floating, not in normal flow - on mobile they sit over the top card rather than
          pushing it down, and free up that vertical space for the cards (no-scroll budget). */}
      <BackButton label={t("moreOrLess.back")} onClick={backToIdle} />
      <ScoreBadge score={game.score} />

      <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row md:items-center md:justify-center md:gap-10">
        <div className="flex min-h-0 w-full flex-1 flex-col md:w-[300px] md:flex-none">
          <PersonCard
            name={reference.name}
            assetCount={reference.assetCount}
            thumbnailUrl={personThumbnailUrl(reference.id)}
          />
        </div>

        <div className="relative flex min-h-0 w-full flex-1 flex-col md:w-[300px] md:flex-none">
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
            ref={slidingCardRef}
            className="relative z-10 flex h-full min-h-0 flex-col md:h-auto"
            style={{
              transform: sliding ? `translate(${slideOffset.x}px, ${slideOffset.y}px)` : "translate(0px, 0px)",
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
  )
}
