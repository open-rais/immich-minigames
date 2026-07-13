import { useEffect, useState } from "react"

/**
 * Animates from 0 to `target` over `durationMs` using an ease-out curve. `target === null` holds
 * the display at 0 (used while waiting on the network before the real value is known).
 */
export function useCountUp(target: number | null, durationMs: number) {
  const [value, setValue] = useState(0)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (target === null) {
      setValue(0)
      setDone(false)
      return
    }

    setDone(false)
    const start = performance.now()
    let raf = 0

    function tick(now: number) {
      const elapsed = now - start
      const t = Math.min(1, elapsed / durationMs)
      const eased = 1 - (1 - t) ** 3
      setValue(Math.round(eased * (target as number)))
      if (t < 1) {
        raf = requestAnimationFrame(tick)
      } else {
        setDone(true)
      }
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, durationMs])

  return { value, done }
}
