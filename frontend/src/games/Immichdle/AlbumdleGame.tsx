import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router-dom"

import { albumThumbnailUrl, getGame, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types/common"
import type { GameOut, RoundOut } from "../../api/types/common"
import type { AlbumdleRoundOut } from "../../api/types/immichdle"
import type { GameComponentProps } from "../catalog"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { PersonAvatar } from "../shared/PersonAvatar"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useGameSession } from "../shared/useGameSession"
import { AlbumGuessTable } from "./AlbumGuessTable"
import { AlbumSearchInput } from "./AlbumSearchInput"

const GAME_TYPE = GameType.Immichdle
const MODE = Mode.Album

// Mirrors ImmichdleGame.tsx's isImmichdleRound exactly - the `mode` check (not just game_type) is
// required since Albumdle shares its game_type with Persondle (see api/types/immichdle.ts).
function isAlbumdleRound(round: RoundOut): round is AlbumdleRoundOut {
  return round.game_type === GameType.Immichdle && round.mode === Mode.Album
}

interface GameState {
  id: string
  score: number
  finished: boolean
  won: boolean
  targetName: string | null
  targetAlbumId: string | null
}

export function AlbumdleGame({ coverUrl, hasRoundsView, daily = false }: GameComponentProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  const [game, setGame] = useState<GameState | null>(null)
  const [pendingRoundId, setPendingRoundId] = useState<string | null>(null)
  const [history, setHistory] = useState<AlbumdleRoundOut[]>([])
  const [animatingRoundId, setAnimatingRoundId] = useState<string | null>(null)
  const [rowAnimationDone, setRowAnimationDone] = useState(false)
  const [targetFetchDone, setTargetFetchDone] = useState(true)
  // Stable reference across renders that don't change history - AlbumSearchInput's debounced
  // search effect depends on excludeIds by reference (same contract as PersonSearchInput's).
  const guessedIds = useMemo(() => new Set(history.map((r) => r.guess_album_id!)), [history])

  const guessInFlightRef = useRef(false)

  function applyGame(g: GameOut, _isResume: boolean): boolean {
    const answered = g.rounds.slice(0, -1)
    if (!answered.every(isAlbumdleRound)) return false
    const pending = g.rounds[g.rounds.length - 1]
    if (!isAlbumdleRound(pending)) return false
    setGame({
      id: g.id,
      score: g.score,
      finished: false,
      won: false,
      targetName: null,
      targetAlbumId: null,
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
    if (!isAlbumdleRound(lastRound)) return false
    setGame({
      id: g.id,
      score: g.score,
      finished: true,
      won: lastRound.correct === true,
      targetName: g.target_album_name ?? null,
      targetAlbumId: g.target_album_id ?? null,
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
    isCurrent,
    guarded,
  } = useGameSession({ gameType: GAME_TYPE, mode: MODE, daily, applyGame, hydrateFinishedDaily })

  async function handleGuess(albumId: string) {
    if (!game || !pendingRoundId) return
    await guarded(guessInFlightRef, async (token) => {
      setBusy(true)
      try {
        const result = await playRound(game.id, pendingRoundId, { album_id: albumId })
        if (!isCurrent(token)) return
        if (!isAlbumdleRound(result.answered_round)) {
          setScreen("error")
          return
        }
        if (result.next_round && !isAlbumdleRound(result.next_round)) {
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

        setAnimatingRoundId(answeredRound.id)
        setRowAnimationDone(false)

        if (result.finished) {
          setTargetFetchDone(false)
          getGame(game.id)
            .then((finalState) => {
              if (!isCurrent(token)) return
              setGame((g) =>
                g
                  ? {
                      ...g,
                      targetName: finalState.target_album_name ?? null,
                      targetAlbumId: finalState.target_album_id ?? null,
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
        modeTitle={t("immichdle.modes.album")}
        description={t("immichdle.album.start.description")}
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
                modeTitle: t("immichdle.modes.album"),
              }
            : undefined
        }
      >
        {game.targetAlbumId && (
          <div className="flex flex-col items-center gap-2">
            <PersonAvatar
              src={albumThumbnailUrl(game.targetAlbumId)}
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
        <div className="w-full md:max-w-md">
          <AlbumSearchInput
            excludeIds={guessedIds}
            onSelect={handleGuess}
            disabled={busy || !pendingRoundId || animatingRoundId !== null}
            focusOnTypeAnywhere
          />
        </div>

        <AlbumGuessTable
          history={history}
          animatingRoundId={animatingRoundId}
          onRowAnimationDone={() => setRowAnimationDone(true)}
        />
      </div>
    </div>
  )
}
