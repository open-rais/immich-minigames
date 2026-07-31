import { useEffect, useRef, useState } from "react"
import type { TransitionEvent } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useParams } from "react-router-dom"

import { playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types/common"
import type { GameOut, RoundOut } from "../../api/types/common"
import type { MoreOrLessGuess, MoreOrLessRoundOut } from "../../api/types/moreOrLess"
import type { GameComponentProps } from "../catalog"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useCountUp } from "../shared/useCountUp"
import { useGameSession } from "../shared/useGameSession"
import type { CandidatePhase } from "./CandidateCard"
import { CandidateCard } from "./CandidateCard"
import { MODE_CONFIG } from "./modeConfig"
import { PersonCard } from "./PersonCard"

const GAME_TYPE = GameType.MoreOrLess

const COUNT_DURATION_MS = 1600
const REVEAL_HOLD_MS = 1400
const MOBILE_BREAKPOINT_QUERY = "(min-width: 768px)" // matches Tailwind's `md:`
// Cards are side-by-side on desktop (horizontal slide) but stacked on mobile (vertical slide) -
// these must match the gap-10/gap-4 classes on the row/column wrapper below.
const DESKTOP_GAP_PX = 40
const MOBILE_GAP_PX = 16

type PersonRef = { id: string; name: string }

// This component only ever creates/plays "more-or-less" games (see GAME_TYPE/MODE above), so a
// mismatched game_type here means the backend returned something unexpected - the error screen
// (via useGameSession's applyGame contract), not a thrown exception (D-4: this used to throw via
// an assertMoreOrLess, the odd one out next to every other game's type-guard convention).
function isMoreOrLessRound(round: RoundOut): round is MoreOrLessRoundOut {
  return round.game_type === GameType.MoreOrLess
}

export function MoreOrLessGame({ coverUrl, hasRoundsView, daily = false }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  // GameRoute only renders this component for a mode that resolved in the catalog, so `mode` is
  // always one of MODE_CONFIG's keys here; the PersonAssets fallback is just a defensive default.
  const { mode = Mode.PersonAssets } = useParams<{ mode: string }>()
  const config = MODE_CONFIG[mode] ?? MODE_CONFIG[Mode.PersonAssets]
  const thumbnailUrl = config.thumbnailUrl

  const [game, setGame] = useState<GameOut | null>(null)
  const [reference, setReference] = useState<(PersonRef & { assetCount: number }) | null>(null)
  const [candidate, setCandidate] = useState<(PersonRef & { roundId: string }) | null>(null)
  const [candidatePhase, setCandidatePhase] = useState<CandidatePhase>("guessing")
  const [countTarget, setCountTarget] = useState<number | null>(null)
  // Set together once a guess resolves, reset together once the next round starts - see
  // handleGuess/handleSlideEnd.
  const [revealResult, setRevealResult] = useState<{
    correct: boolean | null
    nextRound: MoreOrLessRoundOut | null
  } | null>(null)
  const [sliding, setSliding] = useState(false)
  const [transitionEnabled, setTransitionEnabled] = useState(true)
  const [slideOffset, setSlideOffset] = useState({ x: 0, y: 0 })
  const slidingCardRef = useRef<HTMLDivElement>(null)

  // One in-flight ref for guesses - start/resume have their own inside useGameSession.
  const guessInFlightRef = useRef(false)

  const { value: displayCount, done: countDone } = useCountUp(countTarget, COUNT_DURATION_MS)

  // Shared by startGame (fresh GameOut from createGame) and resumeGame (an existing one from
  // getCurrentGame) - both hand off a GameOut whose last round is the current pending one. isResume
  // is unused: nothing here differs between a fresh game and a resumed one.
  function applyGame(g: GameOut, _isResume: boolean): boolean {
    const round = g.rounds[g.rounds.length - 1]
    if (!isMoreOrLessRound(round)) return false
    setGame(g)
    setReference({
      id: round.reference_id,
      name: round.reference_name,
      assetCount: round.reference_asset_count,
    })
    setCandidate({ id: round.candidate_id, name: round.candidate_name, roundId: round.id })
    setCandidatePhase("guessing")
    setCountTarget(null)
    setRevealResult(null)
    setSliding(false)
    return true
  }

  function hydrateFinishedDaily(g: GameOut): boolean {
    setGame(g)
    return true
  }

  const {
    screen,
    setScreen,
    busy,
    hasCurrentGame,
    startGame,
    resumeGame,
    backToIdle,
    isCurrent,
    guarded,
  } = useGameSession({ gameType: GAME_TYPE, mode, daily, applyGame, hydrateFinishedDaily })

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
  }, [candidatePhase, revealResult, setScreen])

  useEffect(() => {
    if (transitionEnabled) return
    const raf = requestAnimationFrame(() => setTransitionEnabled(true))
    return () => cancelAnimationFrame(raf)
  }, [transitionEnabled])

  async function handleGuess(guess: MoreOrLessGuess) {
    if (!game || !candidate || candidatePhase !== "guessing") return
    await guarded(guessInFlightRef, async (token) => {
      setCandidatePhase("counting")
      try {
        const result = await playRound(game.id, candidate.roundId, { guess })
        if (!isCurrent(token)) return
        if (!isMoreOrLessRound(result.answered_round)) {
          setScreen("error")
          return
        }
        if (result.next_round && !isMoreOrLessRound(result.next_round)) {
          setScreen("error")
          return
        }
        setGame((g) => (g ? { ...g, score: result.score, finished: result.finished } : g))
        setRevealResult({ correct: result.correct, nextRound: result.next_round })
        setCountTarget(result.answered_round.candidate_asset_count)
      } catch {
        if (isCurrent(token)) setScreen("error")
      }
    })
  }

  function handleSlideEnd(e: TransitionEvent<HTMLDivElement>) {
    if (e.target !== e.currentTarget || e.propertyName !== "transform") return
    if (!revealResult?.nextRound || countTarget === null || !candidate) return
    const nextRound = revealResult.nextRound

    setTransitionEnabled(false)
    setSliding(false)
    setReference({ id: candidate.id, name: candidate.name, assetCount: countTarget })
    setCandidate({
      id: nextRound.candidate_id,
      name: nextRound.candidate_name,
      roundId: nextRound.id,
    })
    setCandidatePhase("guessing")
    setCountTarget(null)
    setRevealResult(null)
  }

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("moreOrLess.title")}
        modeTitle={t(config.modeTitleKey)}
        description={t(config.descriptionKey)}
        coverUrl={coverUrl}
        onStart={startGame}
        onBack={backToMenu}
        busy={busy}
        hasCurrentGame={hasCurrentGame}
        onContinue={resumeGame}
        allowNewGame={!daily}
      />
    )
  }

  if (screen === "error") {
    return <ErrorScreen onRetry={startGame} onBack={backToMenu} busy={busy} />
  }

  if (screen === "finished") {
    return (
      <FinishedScreen
        score={game?.score ?? 0}
        onPlayAgain={startGame}
        onBack={backToMenu}
        busy={busy}
        gameId={game?.id}
        hasRoundsView={hasRoundsView}
        allowPlayAgain={!daily}
        dailyShare={
          daily && game
            ? {
                gameId: game.id,
                gameType: GAME_TYPE,
                mode,
                gameTitle: t("moreOrLess.title"),
                modeTitle: t(config.modeTitleKey),
              }
            : undefined
        }
      />
    )
  }

  if (!game || !reference || !candidate) return null

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-app-bg px-[18px] py-[22px] md:px-10 md:py-7">
      {/* Fixed/floating, not in normal flow - on mobile they sit over the top card rather than
          pushing it down, and free up that vertical space for the cards (no-scroll budget). */}
      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />

      <div className="flex min-h-0 flex-1 flex-col gap-4 md:flex-row md:items-center md:justify-center md:gap-10">
        <div className="flex min-h-0 w-full flex-1 flex-col md:w-[300px] md:flex-none">
          <PersonCard
            key={reference.id}
            name={reference.name}
            assetCount={reference.assetCount}
            thumbnailUrl={thumbnailUrl(reference.id)}
          />
        </div>

        <div className="relative flex min-h-0 w-full flex-1 flex-col md:w-[300px] md:flex-none">
          {revealResult?.nextRound && (
            <div className="absolute inset-0 z-0">
              <CandidateCard
                key={revealResult.nextRound.candidate_id}
                name={revealResult.nextRound.candidate_name}
                thumbnailUrl={thumbnailUrl(revealResult.nextRound.candidate_id)}
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
              transform: sliding
                ? `translate(${slideOffset.x}px, ${slideOffset.y}px)`
                : "translate(0px, 0px)",
              transition: transitionEnabled ? "transform 450ms ease-out" : "none",
            }}
            onTransitionEnd={handleSlideEnd}
          >
            <CandidateCard
              key={candidate.id}
              name={candidate.name}
              thumbnailUrl={thumbnailUrl(candidate.id)}
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
