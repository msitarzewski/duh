interface SkeletonProps {
  className?: string
  variant?: 'text' | 'circle' | 'rect'
  width?: string
  height?: string
}

export function Skeleton({ className = '', variant = 'text', width, height }: SkeletonProps) {
  const base = 'animate-shimmer rounded'

  const variantStyles = {
    text: 'h-4 rounded',
    circle: 'rounded-full',
    rect: 'rounded-[var(--radius-sm)]',
  }

  return (
    <div
      className={`${base} ${variantStyles[variant]} ${className}`}
      style={{ width, height }}
    />
  )
}
