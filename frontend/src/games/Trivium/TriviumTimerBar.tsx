// Thin bar that drains from full to empty over the answer window - painted with --color-primary
// (the app's CTA indigo), the one place on this screen that's deliberately still that color since
// it's the only thing here that isn't itself clickable (see TriviumOption.tsx for why the options
// themselves avoid it).
//
// `transform: scaleX` (compositor-only), not `width` - a width percentage driven every animation
// frame forces layout on every update, which iOS Safari in particular can end up dropping/batching
// until the next user interaction (the bar looked frozen, then snapped to the right place on tap).
// No CSS transition either: the fraction itself already updates every rAF frame, so a transition on
// top of that is fighting an already-continuous value, not smoothing a discrete jump.
export function TriviumTimerBar({ fraction }: { fraction: number }) {
  const clamped = Math.max(0, Math.min(1, fraction))
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
      <div
        className="h-full w-full origin-left rounded-full bg-primary"
        style={{ transform: `scaleX(${clamped})` }}
      />
    </div>
  )
}
