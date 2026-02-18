import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { ModelBadge } from '@/components/consensus/ModelBadge'
import { ConfidenceMeter } from '@/components/consensus/ConfidenceMeter'
import { CostTicker } from '@/components/consensus/CostTicker'
import { StreamingText } from '@/components/consensus/StreamingText'

// ── ModelBadge ────────────────────────────────────────────

describe('ModelBadge', () => {
  it('renders model name', () => {
    render(<ModelBadge model="anthropic:claude-3" />)
    expect(screen.getByText('anthropic:claude-3')).toBeInTheDocument()
  })

  it('uses cyan variant for anthropic', () => {
    const { container } = render(<ModelBadge model="anthropic:claude-3" />)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-primary)]')
  })

  it('uses green variant for openai', () => {
    const { container } = render(<ModelBadge model="openai:gpt-4" />)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-green)]')
  })

  it('uses amber variant for google', () => {
    const { container } = render(<ModelBadge model="google:gemini" />)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-amber)]')
  })

  it('uses red variant for mistral', () => {
    const { container } = render(<ModelBadge model="mistral:large" />)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-red)]')
  })

  it('falls back to default variant for unknown provider', () => {
    const { container } = render(<ModelBadge model="unknown:model" />)
    const span = container.firstChild as HTMLElement
    expect(span.className).toContain('text-[var(--color-text-secondary)]')
  })
})

// ── ConfidenceMeter ───────────────────────────────────────

describe('ConfidenceMeter', () => {
  it('renders percentage text', () => {
    render(<ConfidenceMeter value={0.85} />)
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('renders 0% for value 0', () => {
    render(<ConfidenceMeter value={0} />)
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('renders 100% for value 1', () => {
    render(<ConfidenceMeter value={1} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('renders SVG with correct size', () => {
    const { container } = render(<ConfidenceMeter value={0.5} size={100} />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
    expect(svg?.getAttribute('width')).toBe('100')
    expect(svg?.getAttribute('height')).toBe('100')
  })

  it('renders two circles (background and progress)', () => {
    const { container } = render(<ConfidenceMeter value={0.75} />)
    const circles = container.querySelectorAll('circle')
    expect(circles.length).toBe(2)
  })

  it('applies red color for low confidence (<0.5)', () => {
    render(<ConfidenceMeter value={0.3} />)
    const text = screen.getByText('30%')
    expect(text.style.color).toBe('var(--color-red)')
  })

  it('applies amber color for medium confidence (0.5-0.7)', () => {
    render(<ConfidenceMeter value={0.6} />)
    const text = screen.getByText('60%')
    expect(text.style.color).toBe('var(--color-amber)')
  })

  it('applies primary color for good confidence (0.7-0.9)', () => {
    render(<ConfidenceMeter value={0.8} />)
    const text = screen.getByText('80%')
    expect(text.style.color).toBe('var(--color-primary)')
  })

  it('applies green color for high confidence (>=0.9)', () => {
    render(<ConfidenceMeter value={0.95} />)
    const text = screen.getByText('95%')
    expect(text.style.color).toBe('var(--color-green)')
  })
})

// ── CostTicker ────────────────────────────────────────────

describe('CostTicker', () => {
  it('renders null when cost is null', () => {
    const { container } = render(<CostTicker cost={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders cost with 4 decimal places', () => {
    render(<CostTicker cost={0.1234} />)
    expect(screen.getByText('0.1234')).toBeInTheDocument()
  })

  it('renders dollar sign', () => {
    render(<CostTicker cost={0.05} />)
    expect(screen.getByText('$')).toBeInTheDocument()
  })

  it('formats small costs correctly', () => {
    render(<CostTicker cost={0.001} />)
    expect(screen.getByText('0.0010')).toBeInTheDocument()
  })

  it('formats zero cost', () => {
    render(<CostTicker cost={0} />)
    expect(screen.getByText('0.0000')).toBeInTheDocument()
  })
})

// ── StreamingText ─────────────────────────────────────────

describe('StreamingText', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with empty text and cursor', () => {
    const { container } = render(<StreamingText text="Hello world" />)
    // Initially displays empty string + cursor
    const spans = container.querySelectorAll('span')
    expect(spans.length).toBeGreaterThan(0)
  })

  it('reveals text character by character', () => {
    render(<StreamingText text="Hi" speed={10} />)

    // Advance by one tick (1000/10 = 100ms per char)
    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(screen.getByText('H', { exact: false })).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(screen.getByText('Hi', { exact: false })).toBeInTheDocument()
  })

  it('calls onComplete when finished', () => {
    const onComplete = vi.fn()
    render(<StreamingText text="AB" speed={10} onComplete={onComplete} />)

    // 2 chars at speed 10 = 200ms
    act(() => {
      vi.advanceTimersByTime(200)
    })

    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('hides cursor when done', () => {
    const { container } = render(<StreamingText text="X" speed={1000} />)

    // Advance past the single character
    act(() => {
      vi.advanceTimersByTime(2)
    })

    // The cursor span has animate-cursor-blink class
    const cursor = container.querySelector('.animate-cursor-blink')
    expect(cursor).toBeNull()
  })

  it('applies custom className', () => {
    const { container } = render(<StreamingText text="Hello" className="my-class" />)
    const outerSpan = container.firstChild as HTMLElement
    expect(outerSpan.className).toContain('my-class')
  })

  it('resets when text prop changes', () => {
    const { rerender } = render(<StreamingText text="First" speed={10} />)

    act(() => {
      vi.advanceTimersByTime(500) // Enough to reveal "First"
    })

    rerender(<StreamingText text="Second" speed={10} />)

    // After rerender, text resets — should be streaming "Second" from the beginning
    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(screen.getByText('S', { exact: false })).toBeInTheDocument()
  })
})

// ── Export Markdown Generation ───────────────────────────

describe('generateExportMarkdown', () => {
  // Lazy import to avoid pulling in store/websocket at module level
  let generateExportMarkdown: typeof import('@/components/consensus/ConsensusComplete').generateExportMarkdown

  beforeAll(async () => {
    const mod = await import('@/components/consensus/ConsensusComplete')
    generateExportMarkdown = mod.generateExportMarkdown
  })

  const rounds = [
    {
      round: 1,
      proposer: 'anthropic:claude-3',
      proposal: 'Use PostgreSQL.',
      challengers: ['openai:gpt-4'],
      challenges: [{ model: 'openai:gpt-4', content: 'SQLite is simpler.' }],
      reviser: 'anthropic:claude-3',
      revision: 'Use SQLite for v0.1.',
      confidence: 0.85,
      dissent: 'PostgreSQL for scale.',
    },
  ]

  it('generates decision-only markdown', () => {
    const md = generateExportMarkdown(
      'Best database?',
      'Use SQLite.',
      0.85,
      'PostgreSQL for scale.',
      0.003,
      rounds,
      'decision',
      true,
    )

    expect(md).toContain('# Consensus: Best database?')
    expect(md).toContain('## Decision')
    expect(md).toContain('Use SQLite.')
    expect(md).toContain('Confidence: 85%')
    expect(md).toContain('## Dissent')
    expect(md).toContain('PostgreSQL for scale.')
    expect(md).not.toContain('## Consensus Process')
    expect(md).not.toContain('### Round')
  })

  it('generates full report markdown', () => {
    const md = generateExportMarkdown(
      'Best database?',
      'Use SQLite.',
      0.85,
      'PostgreSQL for scale.',
      0.003,
      rounds,
      'full',
      true,
    )

    expect(md).toContain('# Consensus: Best database?')
    expect(md).toContain('## Decision')
    expect(md).toContain('## Consensus Process')
    expect(md).toContain('### Round 1')
    expect(md).toContain('#### Proposal (anthropic:claude-3)')
    expect(md).toContain('#### Challenges')
    expect(md).toContain('**openai:gpt-4**: SQLite is simpler.')
    expect(md).toContain('#### Revision (anthropic:claude-3)')
  })

  it('suppresses dissent when includeDissent is false', () => {
    const md = generateExportMarkdown(
      'Best database?',
      'Use SQLite.',
      0.85,
      'PostgreSQL for scale.',
      0.003,
      rounds,
      'decision',
      false,
    )

    expect(md).toContain('## Decision')
    expect(md).not.toContain('## Dissent')
    expect(md).not.toContain('PostgreSQL for scale.')
  })

  it('includes cost in footer', () => {
    const md = generateExportMarkdown(
      'Question',
      'Answer',
      0.9,
      null,
      0.0512,
      [],
      'decision',
      true,
    )

    expect(md).toContain('Cost: $0.0512')
  })

  it('handles null question', () => {
    const md = generateExportMarkdown(
      null,
      'Answer',
      0.9,
      null,
      null,
      [],
      'decision',
      true,
    )

    expect(md).toContain('# Consensus: Unknown')
  })
})
