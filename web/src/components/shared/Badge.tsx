interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'cyan' | 'amber' | 'red' | 'green'
  size?: 'sm' | 'md'
  className?: string
}

const variantStyles = {
  default: 'bg-[var(--color-surface)] text-[var(--color-text-secondary)] border-[var(--color-border)]',
  cyan: 'bg-[rgba(0,212,255,0.1)] text-[var(--color-primary)] border-[rgba(0,212,255,0.2)]',
  amber: 'bg-[rgba(255,184,0,0.1)] text-[var(--color-amber)] border-[rgba(255,184,0,0.2)]',
  red: 'bg-[rgba(255,59,79,0.1)] text-[var(--color-red)] border-[rgba(255,59,79,0.2)]',
  green: 'bg-[rgba(0,255,136,0.1)] text-[var(--color-green)] border-[rgba(0,255,136,0.2)]',
}

const sizeStyles = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-xs',
}

export function Badge({ children, variant = 'default', size = 'sm', className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center font-mono font-medium border rounded-full animate-scale-in ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
    >
      {children}
    </span>
  )
}
