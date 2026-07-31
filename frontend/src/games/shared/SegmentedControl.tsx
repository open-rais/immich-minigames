// Generic 3(ish)-way pill toggle - originally local to menu/UserMenu.tsx (language/theme
// selectors), extracted here once the leaderboard's daily/weekly/historic toggle
// (menu/LeaderboardPage.tsx) needed the exact same control.
//
// `size` defaults to the original compact "sm" (leaderboard toggle, still 100% of existing
// callers); "lg" is settings/SettingsPage.tsx's theme picker, sized to a touch-friendly ~44px
// target per segment instead of the compact chrome-adjacent toggle look.
const sizeClass = {
  sm: "px-2 py-1 text-xs",
  lg: "h-11 px-4 text-[15px]",
}

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  size = "sm",
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
  size?: "sm" | "lg"
}) {
  return (
    <div className="flex rounded-full bg-count-bg p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex-1 rounded-full font-semibold transition-colors ${sizeClass[size]} ${
            value === opt.value ? "bg-primary text-white" : "text-body hover:bg-hover-tint"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
