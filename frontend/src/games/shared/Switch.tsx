// The pill switch widget itself, no label - callers wrap it in their own <label> with whatever
// text/layout their context needs (admin/AdminGameRow.tsx's StreakScoringToggle puts the label
// after the switch; settings/NotificationsCard.tsx puts it before, list-style). Extracted from
// AdminGameRow.tsx's original StreakScoringToggle, which now uses this too.
export function Switch({
  id,
  checked,
  disabled,
  onChange,
}: {
  id?: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <span className="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-line-soft transition-colors has-[:checked]:bg-primary has-[:disabled]:opacity-60">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="peer absolute inset-0 h-full w-full opacity-0 enabled:cursor-pointer disabled:cursor-not-allowed"
      />
      <span className="pointer-events-none ml-1 inline-block h-4 w-4 rounded-full bg-white shadow transition-transform peer-checked:translate-x-5" />
    </span>
  )
}
