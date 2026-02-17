import { type ReactNode, forwardRef } from 'react'

interface GlassPanelProps {
  children: ReactNode
  className?: string
  variant?: 'default' | 'raised' | 'interactive'
  glow?: 'none' | 'subtle' | 'strong'
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const paddingMap = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
}

const glowMap = {
  none: '',
  subtle: 'shadow-[0_0_20px_rgba(0,212,255,0.05)]',
  strong: 'shadow-[0_0_30px_rgba(0,212,255,0.12)]',
}

export const GlassPanel = forwardRef<HTMLDivElement, GlassPanelProps>(
  function GlassPanel(
    { children, className = '', variant = 'default', glow = 'none', padding = 'md' },
    ref,
  ) {
    const base = [
      'rounded-[var(--radius-md)]',
      'border border-[var(--color-border)]',
      'backdrop-blur-[var(--glass-blur)]',
      paddingMap[padding],
      glowMap[glow],
    ]

    const variantStyles = {
      default: 'bg-[var(--glass-bg)]',
      raised: 'bg-[var(--color-bg-raised)]',
      interactive: [
        'bg-[var(--glass-bg)]',
        'hover:bg-[var(--color-surface-hover)]',
        'hover:border-[var(--color-border-hover)]',
        'hover:shadow-[0_0_24px_rgba(0,212,255,0.08)]',
        'transition-all duration-200 ease-out',
        'cursor-pointer',
      ].join(' '),
    }

    return (
      <div
        ref={ref}
        className={`${base.join(' ')} ${variantStyles[variant]} ${className}`}
      >
        {children}
      </div>
    )
  },
)
