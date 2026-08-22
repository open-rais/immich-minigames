import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"
import { useNavigate, useParams } from "react-router-dom"

import { assetThumbnailUrl, personThumbnailUrl, playRound } from "../../api/games"
import { GameType, Mode } from "../../api/types/common"
import type { RoundOut } from "../../api/types/common"
import type { PersonRef, TriviumPlayRoundIn, TriviumRoundOut } from "../../api/types/trivium"
import type { GameComponentProps } from "../catalog"
import { AssetPhoto } from "../shared/AssetPhoto"
import { ErrorScreen, FinishedScreen, IdleScreen } from "../shared/GameScreens"
import { GuardedBackButton } from "../shared/GuardedBackButton"
import { PersonAvatar } from "../shared/PersonAvatar"
import { RevealResultCard } from "../shared/RevealResultCard"
import { ScoreBadge } from "../shared/ScoreBadge"
import { useQueuedThumbnail } from "../shared/thumbnailQueue"
import { useRoundGame } from "../shared/useRoundGame"
import { FACE_ONLY_ALTERNATIVE_KINDS, PERSON_ALTERNATIVE_KINDS, QUESTION_TEXT_KEYS, formatAlternative } from "./questionText"
import type { TriviumOptionState } from "./TriviumOption"
import { TriviumOption } from "./TriviumOption"
import { TriviumTimerBar } from "./TriviumTimerBar"

const GAME_TYPE = GameType.Trivium

// One i18n key per mode - see games/catalog.ts's CatalogMode entries for this game.
const MODE_TITLE_KEYS: Record<string, string> = {
  [Mode.Birthday]: "trivium.modes.birthday",
  [Mode.Photos]: "trivium.modes.photos",
  [Mode.Location]: "trivium.modes.location",
  [Mode.Mixed]: "trivium.modes.mixed",
}

// Fallback only - the real value always comes from the started game's own answer_time_seconds
// (see useRoundGame's GameState), which reflects whatever an admin has it configured to. This is
// just what a round briefly runs on for the one render before that's known.
const DEFAULT_ANSWER_TIME_SECONDS = 10
// How long the fully-revealed question sits alone before the alternatives slide up.
const QUESTION_HOLD_MS = 3000
// Reveal speed - ms per revealed word.
const WORD_REVEAL_MS = 90
const REVEAL_HOLD_MS = 1500
// How far below the viewport the alternatives start their slide-up from, and how long that takes.
// A viewport-relative unit (not a percentage of the block's own height) so it clears the bottom of
// the screen regardless of how tall the alternatives block ends up being.
const SLIDE_START_VH = 60
const SLIDE_TRANSITION_MS = 450

function isTriviumRound(round: RoundOut): round is TriviumRoundOut {
  return round.game_type === GameType.Trivium
}

// The sequence a fresh round plays before the player can answer: reveal the question one word at
// a time (every word is always laid out in its final place, just invisible until its turn - see
// the render below - so the text never shifts as it appears), hold it fully revealed for a beat,
// then slide the alternatives up from off-screen (and start the answer timer). Answering itself
// folds back onto useRoundGame's own `phase` ("guessing"/"submitting"/"revealed") - this only
// covers what happens before a guess is even possible.
type RevealStage = "revealing" | "holding" | "alternatives"

export function TriviumGame({ coverUrl, hasRoundsView, daily = false }: GameComponentProps) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const backToMenu = () => navigate("/")

  // GameRoute only renders this component for a mode that resolved in the catalog, so `mode` is
  // always one of MODE_TITLE_KEYS' keys here; the Birthday fallback is just a defensive default
  // (same convention as MoreOrLessGame's own mode param).
  const { mode = Mode.Birthday } = useParams<{ mode: string }>()

  const [revealStage, setRevealStage] = useState<RevealStage>("revealing")
  const [revealedWordCount, setRevealedWordCount] = useState(0)
  // Set once QUESTION_HOLD_MS has elapsed since the question finished revealing - the alternatives
  // only actually slide up once this AND alternativesMediaLoaded (below) are both true.
  const [holdElapsed, setHoldElapsed] = useState(false)
  // The wall-clock moment the alternatives became interactable - the zero point elapsed_ms is
  // measured from.
  const [alternativesShownAt, setAlternativesShownAt] = useState<number | null>(null)
  const [remainingMs, setRemainingMs] = useState(0)
  // AssetPhoto manages its own <img> load/error state internally rather than going through the
  // thumbnail queue, so its readiness is tracked here via its onReadyChange callback instead of a
  // useQueuedThumbnail call - see the render below. Declared up here (not next to where it's
  // otherwise used, further down) so onNewRound below can reset it synchronously alongside the
  // other reveal-sequence state, rather than waiting on AssetPhoto's own src-changed effect to
  // eventually report "not ready" a render or two later.
  const [assetPhotoReady, setAssetPhotoReady] = useState(false)

  const {
    screen,
    busy,
    game,
    round,
    phase,
    revealed,
    hasCurrentGame,
    startGame,
    resumeGame,
    submitGuess,
    backToIdle,
  } = useRoundGame<TriviumRoundOut, TriviumPlayRoundIn>({
    gameType: GAME_TYPE,
    mode,
    revealHoldMs: REVEAL_HOLD_MS,
    isRound: isTriviumRound,
    playRound: (gameId, roundId, guess) => playRound(gameId, roundId, guess),
    onNewRound: () => {
      setRevealStage("revealing")
      setRevealedWordCount(0)
      setHoldElapsed(false)
      setAlternativesShownAt(null)
      setAssetPhotoReady(false)
    },
    daily,
  })

  const answerTimeMs = (game?.answerTimeSeconds ?? DEFAULT_ANSWER_TIME_SECONDS) * 1000

  // The round's media, if any - "person_thumbnail" (birthday_year/photos_together's subject face)
  // or "asset" (location_country/location_city's photo). Queried through the same dedup/
  // concurrency queue every other thumbnail in the app goes through, not a plain <img src> - see
  // thumbnailQueue.ts.
  const personThumbnailSrc =
    round?.media.kind === "person_thumbnail" && round.media.person_id
      ? personThumbnailUrl(round.media.person_id)
      : null
  const personThumbnail = useQueuedThumbnail(personThumbnailSrc)
  // assetPhotoReady itself is declared up with the other reveal-sequence state (see its own
  // comment there) - only its src is computed here, alongside personThumbnailSrc.
  const assetPhotoSrc =
    round?.media.kind === "asset" && round.media.asset_id ? assetThumbnailUrl(round.media.asset_id) : null
  // "Fully loaded" per round: no media to wait on, or whichever kind this round has has either
  // resolved or given up (a failed load still counts as loaded - the placeholder it falls back to
  // needs no further waiting), it just shouldn't hold up the round forever.
  const mediaLoaded =
    (personThumbnailSrc === null || personThumbnail.url !== null || personThumbnail.failed) &&
    (assetPhotoSrc === null || assetPhotoReady)

  // The 4 alternatives' own photos, for photos_total_assets/photos_together (every other kind has
  // none, so this is 4 nulls - useQueuedThumbnail(null) is a no-op). Computed here (not down by
  // the render, where it used to live) and subscribed via a fixed 4 calls - not a variable-length
  // loop, which Hooks can't do - so these start loading in the background as early as the round
  // itself is known, giving them the whole revealing+holding stretch to resolve instead of only
  // starting once the alternatives are about to appear.
  const hasPersonAlternatives = !!round && PERSON_ALTERNATIVE_KINDS.has(round.question_kind)
  const alternativePhotoUrls: (string | null)[] = hasPersonAlternatives
    ? (round?.alternatives ?? []).map((alt) => personThumbnailUrl((alt as PersonRef).person_id))
    : [null, null, null, null]
  const altThumb0 = useQueuedThumbnail(alternativePhotoUrls[0] ?? null)
  const altThumb1 = useQueuedThumbnail(alternativePhotoUrls[1] ?? null)
  const altThumb2 = useQueuedThumbnail(alternativePhotoUrls[2] ?? null)
  const altThumb3 = useQueuedThumbnail(alternativePhotoUrls[3] ?? null)
  const alternativesMediaLoaded =
    !hasPersonAlternatives ||
    [altThumb0, altThumb1, altThumb2, altThumb3].every((thumb) => thumb.url !== null || thumb.failed)

  const questionTextKey = round ? QUESTION_TEXT_KEYS[round.question_kind] : undefined
  const params = round?.params as PersonRef | undefined
  const questionText = questionTextKey && params ? t(questionTextKey, { name: params.person_name }) : ""
  const questionWords = questionText ? questionText.split(" ") : []

  // Starts the word-by-word reveal once a fresh round has fully loaded - keyed on round?.id (not
  // phase) so this never re-fires between "guessing" and "revealed" of the same round, only for a
  // genuinely new one. Gated on mediaLoaded so the reveal doesn't start (words fading in over a
  // blank/placeholder face) before the thumbnail is actually in.
  useEffect(() => {
    if (!round || !mediaLoaded) return
    setRevealStage("revealing")
    setRevealedWordCount(0)
    setHoldElapsed(false)
    setAlternativesShownAt(null)
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [round?.id, mediaLoaded])

  // Reveals one more word at a time, then hands off to "holding" once every word is visible.
  useEffect(() => {
    if (revealStage !== "revealing" || !mediaLoaded) return
    if (revealedWordCount >= questionWords.length) {
      setRevealStage("holding")
      return
    }
    const timer = setTimeout(() => setRevealedWordCount((n) => n + 1), WORD_REVEAL_MS)
    return () => clearTimeout(timer)
  }, [revealStage, revealedWordCount, questionWords.length, mediaLoaded])

  // QUESTION_HOLD_MS after the question finishes typing, marks the hold as elapsed - doesn't
  // slide the alternatives up itself, since they also need every alternative's photo (if any) to
  // have loaded by then (see the effect below). In the common case the photos are already long
  // done loading (they started as soon as the round was known, back at alternativePhotoUrls
  // above) so this timer is what actually determines the pacing; it only holds things up on a
  // slow connection.
  useEffect(() => {
    if (revealStage !== "holding") return
    const timer = setTimeout(() => setHoldElapsed(true), QUESTION_HOLD_MS)
    return () => clearTimeout(timer)
  }, [revealStage])

  // Slides the alternatives up (see the render below) and starts the answer timer, once both the
  // hold has elapsed and every alternative's own photo has loaded - confirmed by the owner:
  // nothing about a round should still be loading once the countdown starts.
  useEffect(() => {
    if (revealStage !== "holding" || !holdElapsed || !alternativesMediaLoaded) return
    setAlternativesShownAt(performance.now())
    setRevealStage("alternatives")
  }, [revealStage, holdElapsed, alternativesMediaLoaded])

  // Drives the timer bar once the alternatives are up, and auto-submits a null-alternative guess
  // when it runs out - not answering in time is a loss, not a free pass, so the frontend has to
  // send something rather than just sitting there (see api/types/trivium.ts's TriviumPlayRoundIn).
  // Cancels itself the instant phase leaves "guessing" (a real guess was submitted), which is what
  // keeps a manual click and this timeout from ever racing each other.
  useEffect(() => {
    if (revealStage !== "alternatives" || phase !== "guessing" || alternativesShownAt === null) return
    let raf = 0
    function tick() {
      const elapsed = performance.now() - (alternativesShownAt as number)
      const remaining = Math.max(0, answerTimeMs - elapsed)
      setRemainingMs(remaining)
      if (remaining <= 0) {
        submitGuess({ alternative: null, elapsed_ms: answerTimeMs })
        return
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [revealStage, phase, alternativesShownAt, answerTimeMs])

  function handlePick(index: number) {
    if (revealStage !== "alternatives" || phase !== "guessing" || alternativesShownAt === null) return
    const elapsed = Math.min(answerTimeMs, Math.round(performance.now() - alternativesShownAt))
    submitGuess({ alternative: index, elapsed_ms: elapsed })
  }

  // Daily's "already played today" check (useGameSession's idle effect) resolves async -
  // hasCurrentGame stays null until it does, so this avoids a beat of the idle/start screen before
  // screen flips to "finished".
  if (daily && hasCurrentGame === null) return <div className="min-h-dvh bg-app-bg" />

  const modeTitleKey = MODE_TITLE_KEYS[mode] ?? MODE_TITLE_KEYS[Mode.Birthday]

  if (screen === "idle") {
    return (
      <IdleScreen
        title={t("trivium.title")}
        modeTitle={t(modeTitleKey)}
        description={t("trivium.start.description")}
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
                gameTitle: t("trivium.title"),
                modeTitle: t(modeTitleKey),
              }
            : undefined
        }
      />
    )
  }

  if (!game || !round) return null

  // questionTextKey/params are computed above (before the early returns, since the typewriter
  // effects need them too) - a missing one here means an unrecognized question_kind, the same
  // "unexpected shape from the backend" case every other game bails to the error screen for.
  if (!questionTextKey || !params) {
    return <ErrorScreen onRetry={startGame} onBack={backToMenu} busy={busy} />
  }

  const alternativeLabels = round.alternatives.map((alt) => formatAlternative(round.question_kind, alt, i18n.language))
  // hasPersonAlternatives/alternativePhotoUrls are computed further up (alongside the
  // useQueuedThumbnail calls that need them called unconditionally) - only photos_total_assets/
  // photos_together's alternatives have their own photo, so every other kind gets `undefined`
  // here, which is what tells TriviumOption to render the plain text button instead.
  const optionPhotoUrls: (string | undefined)[] = hasPersonAlternatives
    ? alternativePhotoUrls.map((url) => url ?? undefined) // never actually null in this branch
    : [undefined, undefined, undefined, undefined]

  const optionState = (index: number): TriviumOptionState => {
    if (!revealed) return "idle"
    if (index === round.correct_index) return "correct"
    if (round.guess !== null && index === round.guess) return "wrong"
    return "muted"
  }

  const resultKey = round.correct
    ? "trivium.result.correct"
    : round.guess === null
      ? "trivium.result.timeout"
      : "trivium.result.wrong"

  return (
    // justify-between + exactly two flex children below (the question block, the answer block) is
    // what pins the question to the top and the alternatives to the bottom with the gap between
    // them flexing - GuardedBackButton/ScoreBadge are `fixed`, so they don't count as flex children
    // and don't disturb this.
    <div className="flex h-dvh flex-col justify-between overflow-hidden bg-app-bg px-6 pt-20 pb-8 md:px-10 md:pt-28 md:pb-12">
      <GuardedBackButton onExit={backToIdle} />
      <ScoreBadge label={t("common.score")} score={game.score} />

      <div className="mx-auto flex w-full max-w-md flex-col items-center md:max-w-2xl">
        <div className="flex w-full flex-col items-center gap-4 rounded-[22px] border border-line bg-surface p-6 text-center shadow-card md:rounded-3xl md:p-10">
          {round.media.kind === "person_thumbnail" && (
            <PersonAvatar src={personThumbnailSrc} alt={params.person_name} size="lg" />
          )}
          {round.media.kind === "asset" && assetPhotoSrc && (
            <div className="relative h-48 w-full overflow-hidden rounded-2xl md:h-64">
              <AssetPhoto src={assetPhotoSrc} alt="" onReadyChange={setAssetPhotoReady} />
            </div>
          )}
          {/* Every word is always rendered (reserving its final layout position) - only its
              opacity changes as revealedWordCount advances, so the text never shifts/reflows as
              it appears, unlike a literal typewriter that grows the string itself. */}
          <p className="text-xl font-bold text-ink md:text-2xl">
            {questionWords.map((word, index) => (
              <span
                key={index}
                className={`transition-opacity duration-200 ${index < revealedWordCount ? "opacity-100" : "opacity-0"}`}
              >
                {word}
                {index < questionWords.length - 1 ? " " : ""}
              </span>
            ))}
          </p>
        </div>
      </div>

      {/* Floating (fixed), not in normal flow - same "doesn't shift anything around it" shell
          Geoguessr/Dateguessr/Timeline's own reveal card uses. Top-right, just below ScoreBadge
          (same right offset, top offset cleared to sit under it rather than overlap). */}
      {revealed && round.score_delta !== null && (
        <RevealResultCard
          positionClassName="top-[70px] right-[18px] md:top-24 md:right-10"
          scoreDelta={round.score_delta}
          subtitle={t(resultKey)}
        />
      )}

      <div className="mx-auto flex w-full max-w-md flex-col items-center gap-4 md:max-w-2xl">
        {/* Mounted already during "holding" (positioned off-screen below the viewport) so the
            flip to "alternatives" is a genuine transition between two committed states, not an
            instant snap - see SLIDE_START_VH/SLIDE_TRANSITION_MS above. */}
        {revealStage !== "revealing" && (
          <div
            className="flex w-full flex-col items-center gap-4"
            style={{
              transform: revealStage === "alternatives" ? "translateY(0)" : `translateY(${SLIDE_START_VH}vh)`,
              transition: `transform ${SLIDE_TRANSITION_MS}ms ease-out`,
            }}
          >
            <TriviumTimerBar fraction={remainingMs / answerTimeMs} />
            {/* Person alternatives are always a 2x2 grid (mobile included, "cuadrantes") since
                they read as photo tiles, not a text list - every other kind keeps 1 column on
                mobile, 2 on desktop. */}
            <div
              className={`grid w-full gap-3 md:gap-5 ${hasPersonAlternatives ? "grid-cols-2" : "grid-cols-1 md:grid-cols-2"}`}
            >
              {alternativeLabels.map((label, index) => (
                <TriviumOption
                  key={index}
                  state={optionState(index)}
                  disabled={phase !== "guessing"}
                  onClick={() => handlePick(index)}
                  photoUrl={optionPhotoUrls[index]}
                  hideCaption={FACE_ONLY_ALTERNATIVE_KINDS.has(round.question_kind)}
                >
                  {label}
                </TriviumOption>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
