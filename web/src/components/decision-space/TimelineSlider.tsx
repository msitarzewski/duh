import { useDecisionSpaceStore } from '@/stores'
import { GlowButton } from '@/components/shared'
import { useEffect, useRef } from 'react'

export function TimelineSlider() {
  const {
    timelinePosition, timelinePlaying, timelineSpeed,
    setTimelinePosition, toggleTimelinePlaying, setTimelineSpeed,
  } = useDecisionSpaceStore()

  const animRef = useRef<number | null>(null)

  useEffect(() => {
    if (timelinePlaying) {
      const step = () => {
        setTimelinePosition(Math.min(1, timelinePosition + 0.002 * timelineSpeed))
        if (timelinePosition >= 1) {
          toggleTimelinePlaying()
        } else {
          animRef.current = requestAnimationFrame(step)
        }
      }
      animRef.current = requestAnimationFrame(step)
    }
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [timelinePlaying, timelinePosition, timelineSpeed, setTimelinePosition, toggleTimelinePlaying])

  return (
    <div className="flex items-center gap-3">
      <GlowButton variant="ghost" size="sm" onClick={toggleTimelinePlaying}>
        {timelinePlaying ? '\u23F8' : '\u25B6'}
      </GlowButton>

      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={timelinePosition}
        onChange={(e) => setTimelinePosition(Number(e.target.value))}
        className="flex-1 h-1 appearance-none bg-[var(--color-border)] rounded-full [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:bg-[var(--color-primary)] [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:duration-150 [&::-webkit-slider-thumb]:hover:scale-125 [&::-webkit-slider-thumb]:shadow-[0_0_6px_rgba(0,212,255,0.4)]"
      />

      <div className="flex gap-1">
        {[1, 2, 4].map((s) => (
          <button
            key={s}
            onClick={() => setTimelineSpeed(s)}
            className={`px-1.5 py-0.5 text-[10px] font-mono rounded ${
              timelineSpeed === s
                ? 'text-[var(--color-primary)] bg-[var(--color-primary-glow)]'
                : 'text-[var(--color-text-dim)]'
            }`}
          >
            {s}x
          </button>
        ))}
      </div>
    </div>
  )
}
