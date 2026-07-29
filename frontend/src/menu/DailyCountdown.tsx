import { useEffect, useRef, useState } from "react"

interface DailyCountdownProps {
  resetsAt: string
  serverNow: string
  onExpire: () => void
}

function pad(n: number): string {
  return String(n).padStart(2, "0")
}

// Roadmap #G, decision [G] - HH:mm:ss countdown to the next daily reset, computed off the
// backend's own resets_at/server_now rather than the client's clock alone (a skewed client clock
// would otherwise show a wrong countdown, or one that never reaches zero - docs/TODO/
// DAILY-GAMES.md §5). The offset between the two is fixed once at mount; from then on the ticking
// is driven by the *local* clock's elapsed time, not repeated server reads.
export function DailyCountdown({ resetsAt, serverNow, onExpire }: DailyCountdownProps) {
  const offsetMsRef = useRef(new Date(resetsAt).getTime() - new Date(serverNow).getTime())
  const mountedAtRef = useRef(Date.now())
  const firedRef = useRef(false)
  const onExpireRef = useRef(onExpire)
  onExpireRef.current = onExpire
  const [remainingMs, setRemainingMs] = useState(offsetMsRef.current)

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = offsetMsRef.current - (Date.now() - mountedAtRef.current)
      setRemainingMs(remaining)
      if (remaining <= 0 && !firedRef.current) {
        firedRef.current = true
        onExpireRef.current()
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  const totalSeconds = Math.max(0, Math.floor(remainingMs / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  return (
    <span className="font-mono text-sm tabular-nums text-muted">
      {pad(hours)}:{pad(minutes)}:{pad(seconds)}
    </span>
  )
}
