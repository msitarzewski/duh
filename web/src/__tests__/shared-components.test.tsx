import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GlassPanel } from '@/components/shared/GlassPanel'
import { GlowButton } from '@/components/shared/GlowButton'
import { Badge } from '@/components/shared/Badge'
import { Skeleton } from '@/components/shared/Skeleton'
import { ErrorBoundary } from '@/components/shared/ErrorBoundary'

// ── GlassPanel ────────────────────────────────────────────

describe('GlassPanel', () => {
  it('renders children', () => {
    render(<GlassPanel>Hello</GlassPanel>)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('applies default variant and padding classes', () => {
    const { container } = render(<GlassPanel>Content</GlassPanel>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('p-5') // md padding default
    expect(div.className).toContain('bg-[var(--glass-bg)]') // default variant
  })

  it('applies raised variant', () => {
    const { container } = render(<GlassPanel variant="raised">Content</GlassPanel>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('bg-[var(--color-bg-raised)]')
  })

  it('applies interactive variant with hover styles', () => {
    const { container } = render(<GlassPanel variant="interactive">Content</GlassPanel>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('cursor-pointer')
    expect(div.className).toContain('hover:bg-[var(--color-surface-hover)]')
  })

  it('applies glow styles', () => {
    const { container } = render(<GlassPanel glow="strong">Content</GlassPanel>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('shadow-[0_0_30px_rgba(0,212,255,0.12)]')
  })

  it('applies custom className', () => {
    const { container } = render(<GlassPanel className="my-custom">Content</GlassPanel>)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('my-custom')
  })

  it('applies no padding when padding="none"', () => {
    const { container } = render(<GlassPanel padding="none">Content</GlassPanel>)
    const div = container.firstChild as HTMLElement
    // Should not have p-3, p-5, or p-7
    expect(div.className).not.toContain('p-3')
    expect(div.className).not.toContain('p-5')
    expect(div.className).not.toContain('p-7')
  })

  it('forwards ref', () => {
    const ref = { current: null as HTMLDivElement | null }
    render(<GlassPanel ref={ref}>Content</GlassPanel>)
    expect(ref.current).toBeInstanceOf(HTMLElement)
  })
})

// ── GlowButton ────────────────────────────────────────────

describe('GlowButton', () => {
  it('renders children', () => {
    render(<GlowButton>Click me</GlowButton>)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })

  it('handles click events', () => {
    const onClick = vi.fn()
    render(<GlowButton onClick={onClick}>Click</GlowButton>)
    fireEvent.click(screen.getByRole('button'))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('is disabled when disabled prop is true', () => {
    render(<GlowButton disabled>Disabled</GlowButton>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('is disabled when loading is true', () => {
    render(<GlowButton loading>Loading</GlowButton>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('shows spinner when loading', () => {
    const { container } = render(<GlowButton loading>Loading</GlowButton>)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
    expect(svg?.className.baseVal ?? svg?.getAttribute('class')).toContain('animate-spin')
  })

  it('applies primary variant styles by default', () => {
    render(<GlowButton>Primary</GlowButton>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-[var(--color-primary)]')
  })

  it('applies ghost variant styles', () => {
    render(<GlowButton variant="ghost">Ghost</GlowButton>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('bg-transparent')
  })

  it('applies danger variant styles', () => {
    render(<GlowButton variant="danger">Danger</GlowButton>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('text-[var(--color-red)]')
  })

  it('applies size classes', () => {
    render(<GlowButton size="lg">Large</GlowButton>)
    const btn = screen.getByRole('button')
    expect(btn.className).toContain('px-6')
    expect(btn.className).toContain('text-base')
  })

  it('forwards ref', () => {
    const ref = { current: null as HTMLButtonElement | null }
    render(<GlowButton ref={ref}>Btn</GlowButton>)
    expect(ref.current).toBeInstanceOf(HTMLElement)
    expect(ref.current?.tagName).toBe('BUTTON')
  })
})

// ── Badge ─────────────────────────────────────────────────

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>tag</Badge>)
    expect(screen.getByText('tag')).toBeInTheDocument()
  })

  it('applies default variant', () => {
    const { container } = render(<Badge>default</Badge>)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-text-secondary)]')
  })

  it('applies cyan variant', () => {
    const { container } = render(<Badge variant="cyan">cyan</Badge>)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-primary)]')
  })

  it('applies amber variant', () => {
    const { container } = render(<Badge variant="amber">amber</Badge>)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-amber)]')
  })

  it('applies size classes', () => {
    const { container } = render(<Badge size="md">medium</Badge>)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('px-2')
    expect(span.className).toContain('text-xs')
  })

  it('passes custom className', () => {
    const { container } = render(<Badge className="extra">badge</Badge>)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('extra')
  })
})

// ── Skeleton ──────────────────────────────────────────────

describe('Skeleton', () => {
  it('renders a div with animate-shimmer', () => {
    const { container } = render(<Skeleton />)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('animate-shimmer')
  })

  it('applies text variant by default', () => {
    const { container } = render(<Skeleton />)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('h-4')
    expect(div.className).toContain('rounded')
  })

  it('applies circle variant', () => {
    const { container } = render(<Skeleton variant="circle" />)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('rounded-full')
  })

  it('applies rect variant', () => {
    const { container } = render(<Skeleton variant="rect" />)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('rounded-[var(--radius-sm)]')
  })

  it('applies custom width and height via style', () => {
    const { container } = render(<Skeleton width="100px" height="50px" />)
    const div = container.firstChild as HTMLElement
    expect(div.style.width).toBe('100px')
    expect(div.style.height).toBe('50px')
  })

  it('applies custom className', () => {
    const { container } = render(<Skeleton className="w-full" />)
    const div = container.firstChild as HTMLElement
    expect(div.className).toContain('w-full')
  })
})

// ── ErrorBoundary ─────────────────────────────────────────

describe('ErrorBoundary', () => {
  // Suppress React error logging during boundary tests
  const originalError = console.error
  beforeEach(() => {
    console.error = vi.fn()
  })
  afterEach(() => {
    console.error = originalError
  })

  function ThrowingComponent({ message }: { message: string }): React.ReactNode {
    throw new Error(message)
  }

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Safe content</div>
      </ErrorBoundary>,
    )
    expect(screen.getByText('Safe content')).toBeInTheDocument()
  })

  it('displays error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent message="Test error" />
      </ErrorBoundary>,
    )
    expect(screen.getByText('SYSTEM ERROR')).toBeInTheDocument()
    expect(screen.getByText('Test error')).toBeInTheDocument()
  })

  it('displays custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom fallback</div>}>
        <ThrowingComponent message="fail" />
      </ErrorBoundary>,
    )
    expect(screen.getByText('Custom fallback')).toBeInTheDocument()
    expect(screen.queryByText('SYSTEM ERROR')).not.toBeInTheDocument()
  })

  it('resets error state when Retry button is clicked', () => {
    let shouldThrow = true

    function MaybeThrow() {
      if (shouldThrow) throw new Error('Conditional error')
      return <div>Recovered</div>
    }

    render(
      <ErrorBoundary>
        <MaybeThrow />
      </ErrorBoundary>,
    )
    expect(screen.getByText('SYSTEM ERROR')).toBeInTheDocument()

    shouldThrow = false
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(screen.getByText('Recovered')).toBeInTheDocument()
  })
})
