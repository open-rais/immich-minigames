import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { getGame, personThumbnailUrl, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types/common"
import type { GameOut, RoundOut } from "../../api/types/common"
import type { ImmichdleRoundOut } from "../../api/types/immichdle"
import type { GameComponentProps } from "../catalog"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { PersonAvatar } from "../shared/PersonAvatar"
import { ScoreBadge } from "../shared/ScoreBadge"
import { PersonSearchInput } from "../shared/PersonSearchInput"
import { useGameSession } from "../shared/useGameSession"
import { GuessTable } from "./GuessTable"

const GAME_TYPE = GameType.Immichdle
const MODE = Mode.Person

// This component only ever creates/plays "immichdle" games in the "person" mode, so a mismatched
// game_type/mode here means the backend returned something unexpected - the error screen (via
// useGameSession's applyGame contract), not a thrown exception (D-4: this used to throw via an
// assertImmichdle, the odd one out next to every other game's type-guard convention). The `mode`
// check (not just game_type) is required now that Albumdle (roadmap #14) shares the same
// game_type with a differently-shaped round - see api/types/immichdle.ts's mode field.
function isImmichdleRound(round: RoundOut): round is ImmichdleRoundOut {
  return round.game_type === GameType.Immichdle && round.mode === Mode.Person
}

interface GameState {
  id: string
  score: number
  finished: boolean
  won: boolean
  targetName: string | null
  targetPersonId: string | null
}

export function ImmichdleGame({ coverUrl, hasRoundsView, daily = false }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [game, setGame] = useState<GameState | null>(null)
  const [pendingRoundId, setPendingRoundId] = useState<string | null>(null)
  const [history, setHistory] = useState<ImmichdleRoundOut[]>([])
  // The guess-reveal sequence. `animatingRoundId` is the row
  // GuessTable/AnimatedGuessRow is currently running its own entrance/reveal timers for; the effect
  // below only advances past it once that row reports done *and* (only relevant when this was the
  // game's last guess) the target-person fetch below has also resolved - whichever finishes last.
  const [animatingRoundId, setAnimatingRoundId] = useState<string | null>(null)
  const [rowAnimationDone, setRowAnimationDone] = useState(false)
  const [targetFetchDone, setTargetFetchDone] = useState(true)
  // Stable reference across renders that don't change history - PersonSearchInput's debounced
  // search effect depends on excludeIds by reference (see its own docstring, and the other
  // consumers - EditProfilePage/AdminUserRow/FaceGuessPopover - that already follow this
  // contract).
  const guessedIds = useMemo(() => new Set(history.map((r) => r.guess_person_id!)), [history])

  // One in-flight ref for guesses - start/resume have their own inside useGameSession.
  const guessInFlightRef = useRef(false)

  // Shared by startGame (fresh GameOut, a single pending round) and resumeGame (an existing one,
  // any number of already-answered rounds plus one pending) - `g.rounds.slice(0, -1)` is the
  // answered history either way (empty for a fresh game), so both share this without needing to
  // branch on isResume.
  function applyGame(g: GameOut, _isResume: boolean): boolean {
    const answered = g.rounds.slice(0, -1)
    if (!answered.every(isImmichdleRound)) return false
    const pending = g.rounds[g.rounds.length - 1]
    if (!isImmichdleRound(pending)) return false
    setGame({
      id: g.id,
      score: g.score,
      finished: false,
      won: false,
      targetName: null,
      targetPersonId: null,
    })
    setPendingRoundId(pending.id)
    setHistory([...answered].reverse())
    setAnimatingRoundId(null)
    setRowAnimationDone(false)
    setTargetFetchDone(true)
    return true
  }

  function hydrateFinishedDaily(g: GameOut): boolean {
    const lastRound = g.rounds[g.rounds.length - 1]
    if (!isImmichdleRound(lastRound)) return false
    setGame({
      id: g.id,
      score: g.score,
      finished: true,
      won: lastRound.correct === true,
      targetName: g.target_person_name ?? null,
      targetPersonId: g.target_person_id ?? null,
    })
    return true
  }

  const {
    screen,
    setScreen,
    busy,
    setBusy,
    hasCurrentGame,
    startGame,
    resumeGame,
    backToIdle,
    markDailyFinished,
    markRecordBeaten,
    isCurrent,
    guarded,
  } = useGameSession({ gameType: GAME_TYPE, mode: MODE, daily, applyGame, hydrateFinishedDaily })

  async function handleGuess(personId: string) {
    if (!game || !pendingRoundId) return
    await guarded(guessInFlightRef, async (token) => {
      setBusy(true)
      try {
        const result = await playRound(game.id, pendingRoundId, { person_id: personId })
        if (!isCurrent(token)) return
        if (!isImmichdleRound(result.answered_round)) {
          setScreen("error")
          return
        }
        if (result.next_round && !isImmichdleRound(result.next_round)) {
          setScreen("error")
          return
        }
        const answeredRound = result.answered_round

        setHistory((h) => [answeredRound, ...h])
        setGame((g) =>
          g
            ? { ...g, score: result.score, finished: result.finished, won: result.correct === true }
            : g,
        )
        setPendingRoundId(result.next_round ? result.next_round.id : null)
        if (result.finished) {
          markDailyFinished(game.id, result.score)
          markRecordBeaten(result.score)
        }

        // Kicks off the row's own entrance/reveal timers (AnimatedGuessRow, via GuessTable) - the
        // watcher effect below advances the screen once it reports done.
        setAnimatingRoundId(answeredRound.id)
        setRowAnimationDone(false)

        // The target-person fetch runs in parallel with that animation instead of blocking before
        // it (so the row doesn't sit frozen waiting on the network) - only relevant when this guess
        // just finished the game; otherwise there's nothing to fetch and the row alone gates the
        // watcher effect below.
        if (result.finished) {
          setTargetFetchDone(false)
          getGame(game.id)
            .then((finalState) => {
              if (!isCurrent(token)) return
              setGame((g) =>
                g
                  ? {
                      ...g,
                      targetName: finalState.target_person_name ?? null,
                      targetPersonId: finalState.target_person_id ?? null,
                    }
                  : g,
              )
              setTargetFetchDone(true)
            })
            .catch(() => {
              if (isCurrent(token)) setScreen("error")
            })
        } else {
          setTargetFetchDone(true)
        }
      } catch {
        if (isCurrent(token)) setScreen("error")
      } finally {
        if (isCurrent(token)) setBusy(false)
      }
    })
  }

  // Advances past the guess-reveal sequence once both the row's own animation and (only when this
  // guess finished the game) the target fetch above have resolved - whichever finishes last is what
  // actually triggers this, without branching on win/lose.
  useEffect(() => {
    if (!animatingRoundId || !rowAnimationDone || !targetFetchDone) return
    setAnimatingRoundId(null)
    if (game?.finished) setScreen("finished")
  }, [animatingRoundId, rowAnimationDone, targetFetchDone, game?.finished, setScreen])

  // Daily's "already played today" check (useGameSession's idle effect) resolves async -
  // hasCurrentGame stays null until it does, so this avoids a beat of the idle/start screen before
  // screen flips to "finished".
  if (daily && hasCurrentGame === null) return <div className="min-h-dvh bg-app-bg" />

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
        hasCurrentGame={hasCurrentGame}
        onContinue={resumeGame}
        allowNewGame={!daily}
      />
    )
  }

  if (screen === "error") {
    return <ErrorScreen onRetry={startGame} onBack={backToMenu} busy={busy} />
  }

  if (screen === "finished" && game) {
    return (
      <FinishedScreen
        score={game.score}
        onPlayAgain={startGame}
        onBack={backToMenu}
        busy={busy}
        gameId={game.id}
        hasRoundsView={hasRoundsView}
        title={t(game.won ? "immichdle.finished.won" : "immichdle.finished.lost")}
        allowPlayAgain={!daily}
        dailyShare={
          daily
            ? {
                gameId: game.id,
                gameType: GAME_TYPE,
                mode: MODE,
                gameTitle: t("immichdle.title"),
                modeTitle: t("immichdle.modes.person"),
              }
            : undefined
        }
      >
        {game.targetPersonId && (
          <div className="flex flex-col items-center gap-2">
            <PersonAvatar
              src={personThumbnailUrl(game.targetPersonId)}
              alt={game.targetName ?? ""}
              size="lg"
            />
            {game.targetName && <p className="text-xl font-bold text-primary">{game.targetName}</p>}
          </div>
        )}
      </FinishedScreen>
    )
  }

  if (!game) return null

  return (
    <div className="flex min-h-dvh flex-col gap-4 bg-app-bg px-[18px] py-[22px] md:px-10 md:py-7">
      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-4 pt-14 md:pt-16">
        {/* Search bar stays narrower/centered - the table below is free to be wider on desktop
            (up to the outer max-w-5xl), matching the rest of the app's cards rather than smashdle's
            own full-bleed layout. max-w-5xl (not -4xl) is deliberate: GuessTable's own natural
            desktop width (PERSON_COL + 6*CLUE_COL = 224+672 = 896px, plus its border) lands right at
            -4xl's 896px cap, so it used to clip by a couple pixels and trigger an unnecessary
            horizontal scrollbar on desktop even though the table visually "fits". */}
        <div className="w-full md:max-w-md">
          <PersonSearchInput
            excludeIds={guessedIds}
            onSelect={handleGuess}
            disabled={busy || !pendingRoundId || animatingRoundId !== null}
            focusOnTypeAnywhere
          />
        </div>

        <GuessTable
          history={history}
          animatingRoundId={animatingRoundId}
          onRowAnimationDone={() => setRowAnimationDone(true)}
        />
      </div>
    </div>
  )
}
