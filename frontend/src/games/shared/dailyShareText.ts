import type { TFunction } from "i18next"

import { GameType } from "../../api/types"
import type {
  DateguessrRoundOut,
  GameOut,
  GeoguessrRoundOut,
  ImmichdleRoundOut,
  WhosThatPersonRoundOut,
} from "../../api/types"

// Mirrors backend/src/games/geoguessr/round.py's and games/dateguessr/round.py's MAX_SCORE default
// (both 5000) - a daily challenge's actual frozen max_score (services/daily_service.py's settings
// snapshot) isn't exposed per round in GameOut, so this is a cosmetic approximation for the share
// text's emoji color, not a scored value.
const DEFAULT_MAX_SCORE = 5000

function scoreColor(scoreDelta: number, maxScore: number): string {
  const pct = maxScore > 0 ? scoreDelta / maxScore : 0
  if (pct >= 0.8) return "🟩"
  if (pct >= 0.4) return "🟨"
  return "🟥"
}

function assetRoundsBody(
  t: TFunction,
  rounds: (GeoguessrRoundOut | DateguessrRoundOut)[],
  detailFor: (round: GeoguessrRoundOut | DateguessrRoundOut) => string,
  score: number,
): string {
  const lines = rounds.map((round) => {
    const delta = round.score_delta ?? 0
    return t("daily.share.roundLine", {
      color: scoreColor(delta, DEFAULT_MAX_SCORE),
      points: delta,
      detail: detailFor(round),
    })
  })
  return [...lines, t("daily.share.total", { score })].join("\n")
}

function whosThatPersonCorrectTotal(game: GameOut): { correct: number; total: number } {
  const rounds = game.rounds as WhosThatPersonRoundOut[]
  const correct = rounds.reduce(
    (sum, round) => sum + round.faces.filter((f) => f.correct === true).length,
    0,
  )
  const total = game.total_people ?? rounds.reduce((sum, round) => sum + round.faces.length, 0)
  return { correct, total }
}

// Roadmap #G, F6 - the per-game emoji summary from the "Copy-Paste de daily" section of
// docs/TODO/ROADMAP.md, built client-side from an already-finished GameOut (score, each round's
// score_delta/distance/days-off) - no backend endpoint needed for this.
export function buildDailyShareBody(t: TFunction, game: GameOut): string {
  switch (game.type) {
    case GameType.MoreOrLess:
      return t("daily.share.moreOrLess", { score: game.score })

    case GameType.Geoguessr:
      return assetRoundsBody(
        t,
        game.rounds as GeoguessrRoundOut[],
        (round) =>
          t("daily.share.km", {
            value: (round as GeoguessrRoundOut).distance_km?.toFixed(1) ?? "?",
          }),
        game.score,
      )

    case GameType.Dateguessr:
      return assetRoundsBody(
        t,
        game.rounds as DateguessrRoundOut[],
        (round) => t("daily.share.days", { count: (round as DateguessrRoundOut).days_off ?? "?" }),
        game.score,
      )

    case GameType.Immichdle: {
      const rounds = game.rounds as ImmichdleRoundOut[]
      const won = rounds[rounds.length - 1]?.correct === true
      const line = won
        ? t("daily.share.immichdleWon", { attempts: rounds.length })
        : t("daily.share.immichdleLost")
      return `${line}\n${t("daily.share.total", { score: game.score })}`
    }

    case GameType.WhosThatPerson: {
      const { correct, total } = whosThatPersonCorrectTotal(game)
      return `${t("daily.share.whosThatPerson", { correct, total })}\n${t("daily.share.total", { score: game.score })}`
    }

    case GameType.Timeline:
      // Score IS the streak of correctly placed cards (docs/TODO/TIMELINE.md decision [B]), same
      // "score doubles as the headline count" shape as MoreOrLess's own streak line above.
      return `${t("daily.share.timeline", { count: game.score })}\n${t("daily.share.total", { score: game.score })}`

    default:
      return t("daily.share.total", { score: game.score })
  }
}

export function buildDailyShareMessage(
  t: TFunction,
  game: GameOut,
  gameTitle: string,
  modeTitle: string,
  link: string,
): string {
  const header = t("daily.share.header", {
    game: `${gameTitle} · ${modeTitle}`,
    date: game.daily_challenge_date ?? "",
  })
  return `${header}\n${buildDailyShareBody(t, game)}\n${link}`
}

// Roadmap #G, F6 - the condensed "todos resumidos a una linea" variant (docs/TODO/ROADMAP.md's
// "Copy-Paste de daily" section) - one line per mode instead of each mode's full round-by-round
// breakdown, used when every enabled daily mode has been played (menu/DailySection.tsx's header
// share button).
export function buildDailyShareOneLiner(t: TFunction, game: GameOut): string {
  switch (game.type) {
    case GameType.MoreOrLess:
      return t("daily.share.moreOrLess", { score: game.score })

    case GameType.Geoguessr:
    case GameType.Dateguessr: {
      const rounds = game.rounds as (GeoguessrRoundOut | DateguessrRoundOut)[]
      const squares = rounds
        .map((round) => scoreColor(round.score_delta ?? 0, DEFAULT_MAX_SCORE))
        .join("")
      return `${squares} ${game.score}pts`
    }

    case GameType.Immichdle: {
      const rounds = game.rounds as ImmichdleRoundOut[]
      const won = rounds[rounds.length - 1]?.correct === true
      return won
        ? t("daily.share.immichdleWon", { attempts: rounds.length })
        : t("daily.share.immichdleLost")
    }

    case GameType.WhosThatPerson: {
      const { correct, total } = whosThatPersonCorrectTotal(game)
      return t("daily.share.whosThatPerson", { correct, total })
    }

    case GameType.Timeline:
      // One-liner: just the first line (docs/TODO/TIMELINE.md §6.3) - the score is already in it.
      return t("daily.share.timeline", { count: game.score })

    default:
      return `${game.score}pts`
  }
}

export function buildDailyShareAllMessage(
  t: TFunction,
  entries: { modeTitle: string; game: GameOut }[],
  link: string,
): string {
  const date = entries[0]?.game.daily_challenge_date ?? ""
  const header = t("daily.share.allHeader", { date })
  const lines = entries.map(
    ({ modeTitle, game }) => `${modeTitle}: ${buildDailyShareOneLiner(t, game)}`,
  )
  return [header, ...lines, link].join("\n")
}
