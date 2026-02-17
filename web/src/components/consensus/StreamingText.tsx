import { useEffect, useRef, useState } from 'react'

interface StreamingTextProps {
  text: string
  speed?: number
  onComplete?: () => void
  className?: string
}

export function StreamingText({ text, speed = 8, onComplete, className = '' }: StreamingTextProps) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)
  const onCompleteRef = useRef(onComplete)
  onCompleteRef.current = onComplete

  useEffect(() => {
    setDisplayed('')
    setDone(false)
    let idx = 0
    const interval = setInterval(() => {
      idx += 1
      if (idx >= text.length) {
        setDisplayed(text)
        setDone(true)
        onCompleteRef.current?.()
        clearInterval(interval)
      } else {
        setDisplayed(text.slice(0, idx))
      }
    }, 1000 / speed)

    return () => clearInterval(interval)
  }, [text, speed])

  return (
    <span className={`transition-opacity duration-300 ${className}`}>
      {displayed}
      {!done && <span className="animate-cursor-blink text-[var(--color-primary)]">&#9612;</span>}
    </span>
  )
}
