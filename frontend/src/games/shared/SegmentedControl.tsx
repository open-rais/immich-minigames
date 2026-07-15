// Generic 3(ish)-way pill toggle - originally local to menu/UserMenu.tsx (language/theme
// selectors), extracted here once the leaderboard's daily/weekly/historic toggle
// (menu/LeaderboardPage.tsx) needed the exact same control.
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <div className="flex rounded-full bg-count-bg p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`flex-1 rounded-full px-2 py-1 text-xs font-semibold transition-colors ${
            value === opt.value ? "bg-primary text-white" : "text-body hover:bg-hover-tint"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
