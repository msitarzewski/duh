import { type ButtonHTMLAttributes, forwardRef } from 'react'

interface GlowButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
}

const sizeMap = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export const GlowButton = forwardRef<HTMLButtonElement, GlowButtonProps>(
  function GlowButton(
    { variant = 'primary', size = 'md', loading, children, className = '', disabled, ...props },
    ref,
  ) {
    const base = [
      'inline-flex items-center justify-center gap-2',
      'font-medium rounded-[var(--radius-sm)]',
      'transition-all duration-150 ease-out',
      'hover:scale-[1.02] active:scale-[0.98]',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-bg)]',
      'disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100',
      sizeMap[size],
    ]

    const variantStyles = {
      primary: [
        'bg-[var(--color-primary)] text-[var(--color-bg)]',
        'hover:shadow-[0_0_20px_rgba(0,212,255,0.3)]',
        'active:shadow-[0_0_10px_rgba(0,212,255,0.2)]',
        'font-semibold',
      ].join(' '),
      ghost: [
        'bg-transparent text-[var(--color-primary)]',
        'border border-[var(--color-border)]',
        'hover:bg-[var(--color-primary-glow)]',
        'hover:border-[var(--color-border-hover)]',
      ].join(' '),
      danger: [
        'bg-transparent text-[var(--color-red)]',
        'border border-[rgba(255,59,79,0.2)]',
        'hover:bg-[rgba(255,59,79,0.1)]',
        'hover:border-[rgba(255,59,79,0.4)]',
      ].join(' '),
    }

    return (
      <button
        ref={ref}
        className={`${base.join(' ')} ${variantStyles[variant]} ${className}`}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {children}
      </button>
    )
  },
)
