import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { useTranslation } from "react-i18next"

import { albumThumbnailUrl, assetThumbnailUrl, personThumbnailUrl } from "../../api/games"
import { apiErrorMessage } from "../../api/errors"
import { createReport, getReportContext } from "../../api/reports"
import { ReportEntity } from "../../api/types/reports"
import type { ReportContextOut, ReportReason } from "../../api/types/reports"
import { Button } from "./Button"
import { PersonAvatar } from "./PersonAvatar"
import { REASONS_FOR_KIND, reasonLabelKey } from "./reportReasons"
import { Spinner } from "./Spinner"

const NOTE_MAX_LENGTH = 200

interface ReportModalProps {
  kind: ReportEntity
  id: string
  onClose: () => void
}

// A plain "YYYY-MM-DD" date has no time component - new Date(value) parses that as UTC midnight,
// so formatting must stay in UTC too or it silently shifts a day backward in any timezone behind
// UTC. Same trap (and fix) as games/MoreOrLess/birthDate.ts::formatBirthDate - duplicated rather
// than imported, since this shared component shouldn't depend on one specific game's folder.
function formatDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(language, { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(
    new Date(value),
  )
}

const PERSONS_PREVIEW_COUNT = 3

// Shows up to PERSONS_PREVIEW_COUNT names; "show N more" expands to the rest in place instead of
// truncating with an ellipsis - a name list is exactly the kind of content a player would want to
// actually read (e.g. to recognize whose face is mislabeled), not just know exists.
function PersonsList({ persons }: { persons: string[] }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? persons : persons.slice(0, PERSONS_PREVIEW_COUNT)
  const remaining = persons.length - shown.length

  return (
    <div>
      <p>{shown.join(", ")}</p>
      {remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="text-xs font-semibold text-primary hover:text-primary-hover"
        >
          {t("reports.modal.showMore", { count: remaining })}
        </button>
      )}
    </div>
  )
}

function ContextPanel({ kind, id, context }: { kind: ReportEntity; id: string; context: ReportContextOut }) {
  const { i18n } = useTranslation()

  if (kind === ReportEntity.Person) {
    return (
      <div className="flex items-center gap-3">
        <PersonAvatar src={personThumbnailUrl(id)} alt="" size="md" />
        <div className="min-w-0">
          {context.name && <p className="truncate font-semibold text-ink">{context.name}</p>}
          {context.birth_date && (
            <p className="text-sm text-muted">{formatDate(context.birth_date, i18n.language)}</p>
          )}
        </div>
      </div>
    )
  }

  if (kind === ReportEntity.Album) {
    return (
      <div className="flex items-center gap-3">
        <PersonAvatar src={albumThumbnailUrl(id)} alt="" size="md" />
        <div className="min-w-0">
          {context.name && <p className="truncate font-semibold text-ink">{context.name}</p>}
          {context.start_date && context.end_date && (
            <p className="text-sm text-muted">
              {formatDate(context.start_date, i18n.language)} – {formatDate(context.end_date, i18n.language)}
            </p>
          )}
        </div>
      </div>
    )
  }

  const hasLocation = context.latitude != null && context.longitude != null
  const place = [context.city, context.country].filter(Boolean).join(", ")
  return (
    <div className="flex items-start gap-3">
      <PersonAvatar src={assetThumbnailUrl(id)} alt="" size="md" />
      <div className="min-w-0 flex-1 text-sm text-muted">
        {hasLocation && (
          <p>
            {context.latitude!.toFixed(5)}, {context.longitude!.toFixed(5)}
          </p>
        )}
        {place && <p>{place}</p>}
        {context.start_date && <p>{formatDate(context.start_date, i18n.language)}</p>}
        {context.persons && context.persons.length > 0 && <PersonsList persons={context.persons} />}
      </div>
    </div>
  )
}

// Visual shell modeled on ShareModal.tsx/ConfirmExitModal.tsx's overlay/card pattern (no Escape
// handling, same as those two - only EntryOptionsMenu.tsx, a popover, listens for Escape), but
// portalled to document.body unlike them: this one can open from inside Timeline's per-card
// EntryOptionsMenu, which TimelineCard.tsx renders inside an `absolute` + `z-10` badge/actions
// wrapper - a plain `position: fixed` div still gets painted within that ancestor's local stacking
// context (a `z-index` on a positioned ancestor creates one, regardless of `fixed` positioning
// downstream), so without a portal it could render behind a *different* card's badge instead of on
// top of the whole page. Neither ShareModal nor ConfirmExitModal ever opens from inside a
// z-indexed ancestor, so they don't need this.
export function ReportModal({ kind, id, onClose }: ReportModalProps) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<Set<ReportReason>>(new Set())
  const [note, setNote] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  // null = still loading, undefined = failed or the entity no longer exists in Immich (fails
  // silently - the context panel just doesn't render, the report form works either way).
  const [context, setContext] = useState<ReportContextOut | null | undefined>(null)

  useEffect(() => {
    let cancelled = false
    getReportContext(kind, id)
      .then((result) => {
        if (!cancelled) setContext(result ?? undefined)
      })
      .catch(() => {
        if (!cancelled) setContext(undefined)
      })
    return () => {
      cancelled = true
    }
  }, [kind, id])

  function toggleReason(reason: ReportReason) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(reason)) next.delete(reason)
      else next.add(reason)
      return next
    })
  }

  async function handleSubmit() {
    setBusy(true)
    setError(null)
    try {
      await createReport({
        entity_type: kind,
        entity_id: id,
        reasons: Array.from(selected),
        note: note.trim() === "" ? null : note,
      })
      setSent(true)
    } catch (err) {
      setError(apiErrorMessage(err) ?? t("reports.error.generic"))
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 px-6" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-2xl border border-line-soft bg-surface p-6 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        {sent ? (
          <>
            <p className="text-sm font-semibold text-ink">{t("reports.modal.success")}</p>
            <div className="mt-6 flex justify-center">
              <Button variant="primary" className="px-5 py-2.5" onClick={onClose}>
                {t("reports.modal.done")}
              </Button>
            </div>
          </>
        ) : (
          <>
            <h2 className="text-lg font-bold text-ink">{t("reports.modal.title")}</h2>
            {context === null ? (
              <div className="mt-4 flex justify-center">
                <Spinner className="h-6 w-6" />
              </div>
            ) : (
              context && (
                <div className="mt-4 rounded-xl border border-line-soft bg-app-bg p-3">
                  <ContextPanel kind={kind} id={id} context={context} />
                </div>
              )
            )}
            <div className="mt-4 flex flex-col gap-2.5">
              {REASONS_FOR_KIND[kind].map((reason) => (
                <label key={reason} className="flex items-center gap-2.5 text-sm font-semibold text-body">
                  <input
                    type="checkbox"
                    checked={selected.has(reason)}
                    onChange={() => toggleReason(reason)}
                    className="h-4 w-4 accent-primary"
                  />
                  {t(reasonLabelKey(reason))}
                </label>
              ))}
            </div>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value.slice(0, NOTE_MAX_LENGTH))}
              placeholder={t("reports.modal.notePlaceholder")}
              rows={3}
              className="mt-4 w-full resize-none rounded-xl border border-line-soft bg-app-bg p-3 text-sm text-ink outline-none focus:border-primary"
            />
            <div className="mt-1 text-right text-xs text-muted">
              {note.length}/{NOTE_MAX_LENGTH}
            </div>
            {error && <p className="mt-2 text-sm font-semibold text-rose-600">{error}</p>}
            <div className="mt-4 flex justify-center gap-3">
              <Button variant="secondary" className="px-5 py-2.5" onClick={onClose}>
                {t("reports.modal.cancel")}
              </Button>
              <Button
                variant="primary"
                className="px-5 py-2.5"
                disabled={selected.size === 0 || busy}
                onClick={handleSubmit}
              >
                {t("reports.modal.submit")}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  )
}
