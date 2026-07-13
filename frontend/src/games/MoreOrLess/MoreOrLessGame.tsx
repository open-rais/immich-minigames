import { useEffect, useRef, useState } from "react"
import type { TransitionEvent } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { createGame, personThumbnailUrl, playRound } from "../../api/games"
import type { GameOut, Guess, RoundOut } from "../../api/types"
import { BackButton } from "./BackButton"
import { Button } from "./Button"
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
type PersonRef = { id: string; name: string }

export function MoreOrLessGame() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [screen, setScreen] = useState<Screen>("idle")
  const [busy, setBusy] = useState(false)

  const [game, setGame] = useState<GameOut | null>(null)
  const [reference, setReference] = useState<(PersonRef & { assetCount: number }) | null>(null)
  const [candidate, setCandidate] = useState<(PersonRef & { roundId: string }) | null>(null)
  const [candidatePhase, setCandidatePhase] = useState<CandidatePhase>("guessing")
  const [countTarget, setCountTarget] = useState<number | null>(null)
  // Set together once a guess resolves, reset together once the next round starts - see
  // handleGuess/handleSlideEnd.
  const [revealResult, setRevealResult] = useState<{ correct: boolean; nextRound: RoundOut | null } | null>(null)
  const [sliding, setSliding] = useState(false)
  const [transitionEnabled, setTransitionEnabled] = useState(true)
  const [slideOffset, setSlideOffset] = useState({ x: 0, y: 0 })
  const slidingCardRef = useRef<HTMLDivElement>(null)

  // Synchronous re-entrancy guards - a click handler can fire twice before React re-renders
  // (e.g. a fast double-click), so state like `candidatePhase`/`busy` alone isn't enough to stop
  // a second network call; these refs are checked and set immediately, no render involved.
  const guessInFlightRef = useRef(false)
  const startInFlightRef = useRef(false)
  // Bumped on every new start/guess and on "Back" - a response for a request that's no longer
  // current (e.g. the user hit Back while a guess was still in flight) is ignored when it arrives.
  const requestTokenRef = useRef(0)

  const { value: displayCount, done: countDone } = useCountUp(countTarget, COUNT_DURATION_MS)

  useEffect(() => {
    if (countDone && candidatePhase === "counting") {
      setCandidatePhase("revealed")
    }
  }, [countDone, candidatePhase])

  useEffect(() => {
    if (candidatePhase !== "revealed" || !revealResult) return
    const timer = setTimeout(() => {
      if (revealResult.correct && revealResult.nextRound) {
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
  }, [candidatePhase, revealResult])

  useEffect(() => {
    if (transitionEnabled) return
    const raf = requestAnimationFrame(() => setTransitionEnabled(true))
    return () => cancelAnimationFrame(raf)
  }, [transitionEnabled])

  async function startGame() {
    if (startInFlightRef.current) return
    startInFlightRef.current = true
    const token = ++requestTokenRef.current
    setBusy(true)
    try {
      const g = await createGame(GAME_TYPE, MODE)
      if (requestTokenRef.current !== token) return
      const round = g.rounds[g.rounds.length - 1]
      setGame(g)
      setReference({ id: round.reference_id, name: round.reference_name, assetCount: round.reference_asset_count })
      setCandidate({ id: round.candidate_id, name: round.candidate_name, roundId: round.id })
      setCandidatePhase("guessing")
      setCountTarget(null)
      setRevealResult(null)
      setSliding(false)
      setScreen("playing")
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      startInFlightRef.current = false
      if (requestTokenRef.current === token) setBusy(false)
    }
  }

  async function handleGuess(guess: Guess) {
    if (guessInFlightRef.current || !game || !candidate || candidatePhase !== "guessing") return
    guessInFlightRef.current = true
    const token = ++requestTokenRef.current
    setCandidatePhase("counting")
    try {
      const result = await playRound(game.id, candidate.roundId, guess)
      if (requestTokenRef.current !== token) return
      setGame((g) => (g ? { ...g, score: result.score, finished: result.finished } : g))
      setRevealResult({ correct: result.correct, nextRound: result.next_round })
      setCountTarget(result.answered_round.candidate_asset_count)
    } catch {
      if (requestTokenRef.current === token) setScreen("error")
    } finally {
      guessInFlightRef.current = false
    }
  }

  function handleSlideEnd(e: TransitionEvent<HTMLDivElement>) {
    if (e.target !== e.currentTarget || e.propertyName !== "transform") return
    if (!revealResult?.nextRound || countTarget === null || !candidate) return
    const nextRound = revealResult.nextRound

    setTransitionEnabled(false)
    setSliding(false)
    setReference({ id: candidate.id, name: candidate.name, assetCount: countTarget })
    setCandidate({ id: nextRound.candidate_id, name: nextRound.candidate_name, roundId: nextRound.id })
    setCandidatePhase("guessing")
    setCountTarget(null)
    setRevealResult(null)
  }

  function backToIdle() {
    requestTokenRef.current++ // discard any in-flight guess/start response that arrives later
    setScreen("idle")
  }

  if (screen === "idle") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <BackButton label={t("moreOrLess.back")} onClick={backToMenu} />
        <h1 className="text-3xl font-bold text-ink">{t("moreOrLess.title")}</h1>
        <p className="max-w-md text-muted">{t("moreOrLess.start.description")}</p>
        <Button variant="primary" className="px-8 py-3" onClick={startGame} disabled={busy}>
          {t("moreOrLess.start.cta")}
        </Button>
      </div>
    )
  }

  if (screen === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
        <BackButton label={t("moreOrLess.back")} onClick={backToMenu} />
        <p className="text-body">{t("moreOrLess.error.message")}</p>
        <Button variant="primary" className="px-6 py-3" onClick={startGame} disabled={busy}>
          {t("moreOrLess.error.retry")}
        </Button>
      </div>
    )
  }

  if (screen === "finished") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-app-bg px-6 text-center">
        <BackButton label={t("moreOrLess.back")} onClick={backToMenu} />
        <h1 className="text-3xl font-bold text-ink">{t("moreOrLess.finished.title")}</h1>
        <p className="text-xl text-muted">{t("moreOrLess.finished.finalScore", { score: game?.score ?? 0 })}</p>
        <Button variant="primary" className="px-8 py-3" onClick={startGame} disabled={busy}>
          {t("moreOrLess.result.playAgain")}
        </Button>
      </div>
    )
  }

  if (!game || !reference || !candidate) return null

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-app-bg px-[18px] py-[22px] md:px-10 md:py-7">
      {/* Fixed/floating, not in normal flow - on mobile they sit over the top card rather than
          pushing it down, and free up that vertical space for the cards (no-scroll budget). */}
      <BackButton label={t("moreOrLess.back")} onClick={backToIdle} />
      <ScoreBadge score={game.score} />

      <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row md:items-center md:justify-center md:gap-10">
        <div className="flex min-h-0 w-full flex-1 flex-col md:w-[300px] md:flex-none">
          <PersonCard
            key={reference.id}
            name={reference.name}
            assetCount={reference.assetCount}
            thumbnailUrl={personThumbnailUrl(reference.id)}
          />
        </div>

        <div className="relative flex min-h-0 w-full flex-1 flex-col md:w-[300px] md:flex-none">
          {revealResult?.nextRound && (
            <div className="absolute inset-0 z-0">
              <CandidateCard
                key={revealResult.nextRound.candidate_id}
                name={revealResult.nextRound.candidate_name}
                thumbnailUrl={personThumbnailUrl(revealResult.nextRound.candidate_id)}
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
              key={candidate.id}
              name={candidate.name}
              thumbnailUrl={personThumbnailUrl(candidate.id)}
              phase={candidatePhase}
              displayCount={displayCount}
              correct={revealResult?.correct ?? null}
              onGuess={handleGuess}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
