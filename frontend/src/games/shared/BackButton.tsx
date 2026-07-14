export function BackButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="fixed top-[18px] left-[18px] z-30 flex h-11 w-11 items-center justify-center rounded-full border border-line-strong bg-surface text-[15px] font-semibold text-body shadow-card transition-colors hover:bg-hover-tint md:top-7 md:left-10 md:h-auto md:w-auto md:justify-start md:gap-2 md:py-2.5 md:pr-[18px] md:pl-3.5"
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M15 18l-6-6 6-6" />
      </svg>
      <span className="hidden md:inline">{label}</span>
    </button>
  )
}
