import { type ReactNode, useState } from 'react'

interface DisclosureProps {
  children: ReactNode
  header: ReactNode
  defaultOpen?: boolean
  forceOpen?: boolean
  className?: string
}

export function Disclosure({ children, header, defaultOpen = true, forceOpen, className = '' }: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen)
  const isOpen = forceOpen || open

  return (
    <div className={className}>
      <div
        className={`flex items-center gap-2 cursor-pointer select-none ${isOpen ? 'mb-2' : ''}`}
        onClick={() => { if (!forceOpen) setOpen(!open) }}
      >
        <svg
          className={`w-3 h-3 text-[var(--color-text-dim)] transition-transform duration-200 shrink-0 ${isOpen ? 'rotate-90' : ''}`}
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path d="M8 5l10 7-10 7z" />
        </svg>
        {header}
      </div>
      {isOpen && children}
    </div>
  )
}
