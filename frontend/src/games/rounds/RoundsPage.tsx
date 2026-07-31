import { Suspense, useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, useNavigate, useParams } from "react-router-dom"

import { getGame } from "../../api/games"
import type { GameOut } from "../../api/types/common"
import { findCatalogMode, GAME_CATALOG } from "../catalog"
import { Button } from "../shared/Button"
import { RoundsShell } from "./RoundsShell"

type LoadState = { status: "loading" } | { status: "error" } | { status: "ready"; game: GameOut }

// Loads a finished game and hands it to that mode's roundsComponent (ROUNDS-VIEW.md roadmap #10) -
// modeled directly on menu/LeaderboardPage.tsx (params -> catalog lookup -> fetch -> render).
export function RoundsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { gameType, mode, gameId } = useParams<{ gameType: string; mode: string; gameId: string }>()
  const catalogMode = gameType && mode ? findCatalogMode(gameType, mode) : undefined
  const catalogGame = GAME_CATALOG.find((g) => g.gameType === gameType)
  const [state, setState] = useState<LoadState>({ status: "loading" })

  useEffect(() => {
    if (!gameId) return
    let cancelled = false
    setState({ status: "loading" })
    getGame(gameId)
      .then((game) => {
        if (!cancelled) setState({ status: "ready", game })
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" })
      })
    return () => {
      cancelled = true
    }
  }, [gameId])

  // An unknown mode, a mode with no roundsComponent registered (shouldn't happen - every mode has
  // one), or a missing gameId all mean there's nothing sensible to render here - bounce to the menu
  // the same way GameRoute does for an unknown (gameType, mode).
  if (
    !catalogMode ||
    !catalogGame ||
    !gameType ||
    !mode ||
    !gameId ||
    !catalogMode.roundsComponent
  ) {
    return <Navigate to="/" replace />
  }

  if (state.status === "loading") {
    return <div className="min-h-dvh bg-app-bg" />
  }

  if (state.status === "error") {
    // One message for every failure (including 403/404) - a game that's inaccessible or doesn't
    // exist looks the same to the player either way (§4.4 of the doc).
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-app-bg px-6 text-center">
        <p className="text-body">{t("common.rounds.notFound")}</p>
        <Button variant="primary" className="px-6 py-3" onClick={() => navigate("/")}>
          {t("common.back")}
        </Button>
      </div>
    )
  }

  const RoundsComponent = catalogMode.roundsComponent
  const onBack = () => navigate(`/${gameType}/${mode}`)

  // "Fullscreen" family (Geoguessr/Dateguessr/Who'sThatPerson) owns the whole viewport itself -
  // MapPicker/TimelineRuler/AssetPhoto are fixed full-screen components that don't belong inside
  // RoundsShell's padded scrolling column (ROUNDS-VIEW.md §5), and the round stepper needs state
  // that only the component itself holds. RoundsShell is reserved for the "list" family
  // (MoreOrLess, Immichdle).
  if (catalogMode.roundsLayout === "fullscreen") {
    return (
      // catalog.ts's roundsComponent is lazy-loaded (B-1) - this Suspense covers its chunk download.
      <Suspense fallback={<div className="min-h-dvh bg-app-bg" />}>
        <RoundsComponent game={state.game} onBack={onBack} />
      </Suspense>
    )
  }

  return (
    <RoundsShell
      gameTitle={t(catalogGame.gameTitleKey)}
      modeTitle={t(catalogMode.modeTitleKey)}
      score={state.game.score}
      onBack={onBack}
    >
      <Suspense fallback={null}>
        <RoundsComponent game={state.game} />
      </Suspense>
    </RoundsShell>
  )
}
