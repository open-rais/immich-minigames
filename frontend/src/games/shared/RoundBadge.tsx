// The progress pill shown top-center during a round - identical shell across every game, only the
// text differs ("Round X of Y" for Geoguessr/Dateguessr, "N of 15 people" for Who'sThatPerson), so
// callers pass their own already-translated label instead of this component owning one fixed i18n
// key.
export function RoundBadge({ label }: { label: string }) {
  return (
    <div className="fixed top-[18px] left-1/2 z-30 -translate-x-1/2 rounded-full bg-badge-bg px-4 py-2 shadow-card md:top-7">
      <span className="text-[11px] font-bold tracking-wide text-badge-label uppercase md:text-[13px]">{label}</span>
    </div>
  )
}
