import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Disclosure } from '@/components/shared/Disclosure'
import { PhaseCard } from '@/components/consensus/PhaseCard'
import { DissentBanner } from '@/components/consensus/DissentBanner'
import { TurnCard } from '@/components/threads/TurnCard'
import type { Turn } from '@/api/types'

// ── DissentBanner ────────────────────────────────────────

describe('DissentBanner', () => {
  it('renders DISSENT label', () => {
    render(<DissentBanner dissent="Some dissent text" />)
    expect(screen.getByText('DISSENT')).toBeInTheDocument()
  })

  it('renders dissent content', () => {
    render(<DissentBanner dissent="Alternative approach recommended" />)
    expect(screen.getByText('Alternative approach recommended')).toBeInTheDocument()
  })

  it('extracts model name from [model:name]: prefix', () => {
    render(<DissentBanner dissent="[google:gemini-3-flash]: Use a different strategy" />)
    expect(screen.getByText('google:gemini-3-flash')).toBeInTheDocument()
    expect(screen.getByText('Use a different strategy')).toBeInTheDocument()
  })

  it('handles dissent without model prefix', () => {
    render(<DissentBanner dissent="Plain dissent without model" />)
    expect(screen.getByText('Plain dissent without model')).toBeInTheDocument()
  })

  it('is collapsible via Disclosure', () => {
    render(<DissentBanner dissent="[openai:gpt-4]: Collapsible content" />)
    // Content is visible by default
    expect(screen.getByText('Collapsible content')).toBeInTheDocument()
    // Click DISSENT header to collapse
    fireEvent.click(screen.getByText('DISSENT'))
    expect(screen.queryByText('Collapsible content')).toBeNull()
  })
})

// ── Disclosure (shared primitive) ────────────────────────

describe('Disclosure', () => {
  it('shows children when defaultOpen=true', () => {
    render(
      <Disclosure header={<span>Header</span>} defaultOpen>
        <p>Content</p>
      </Disclosure>
    )
    expect(screen.getByText('Content')).toBeInTheDocument()
  })

  it('hides children when defaultOpen=false', () => {
    render(
      <Disclosure header={<span>Header</span>} defaultOpen={false}>
        <p>Hidden</p>
      </Disclosure>
    )
    expect(screen.queryByText('Hidden')).toBeNull()
  })

  it('toggles on header click', () => {
    render(
      <Disclosure header={<span>Toggle</span>} defaultOpen={false}>
        <p>Body</p>
      </Disclosure>
    )
    expect(screen.queryByText('Body')).toBeNull()
    fireEvent.click(screen.getByText('Toggle'))
    expect(screen.getByText('Body')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Toggle'))
    expect(screen.queryByText('Body')).toBeNull()
  })

  it('stays open when forceOpen=true regardless of clicks', () => {
    render(
      <Disclosure header={<span>Forced</span>} defaultOpen={false} forceOpen>
        <p>Always visible</p>
      </Disclosure>
    )
    expect(screen.getByText('Always visible')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Forced'))
    expect(screen.getByText('Always visible')).toBeInTheDocument()
  })

  it('renders chevron that rotates when open', () => {
    const { container } = render(
      <Disclosure header={<span>H</span>} defaultOpen>
        <p>C</p>
      </Disclosure>
    )
    const chevron = container.querySelector('svg')
    expect(chevron?.className).toContain('rotate-90')
  })

  it('chevron does not rotate when closed', () => {
    const { container } = render(
      <Disclosure header={<span>H</span>} defaultOpen={false}>
        <p>C</p>
      </Disclosure>
    )
    const chevron = container.querySelector('svg')
    expect(chevron?.className).not.toContain('rotate-90')
  })
})

// ── PhaseCard collapsible ────────────────────────────────

describe('PhaseCard collapsible', () => {
  it('renders content when not collapsible', () => {
    render(<PhaseCard phase="PROPOSE" content="Some proposal" />)
    expect(screen.getByText('Some proposal')).toBeInTheDocument()
  })

  it('hides content when collapsible and defaultOpen=false', () => {
    render(
      <PhaseCard phase="PROPOSE" content="Hidden proposal" collapsible defaultOpen={false} />
    )
    expect(screen.queryByText('Hidden proposal')).toBeNull()
  })

  it('shows content when collapsible and defaultOpen=true', () => {
    render(
      <PhaseCard phase="PROPOSE" content="Visible proposal" collapsible defaultOpen />
    )
    expect(screen.getByText('Visible proposal')).toBeInTheDocument()
  })

  it('toggles content on header click', () => {
    render(
      <PhaseCard phase="PROPOSE" content="Toggle me" collapsible defaultOpen={false} />
    )
    expect(screen.queryByText('Toggle me')).toBeNull()
    fireEvent.click(screen.getByText('PROPOSE'))
    expect(screen.getByText('Toggle me')).toBeInTheDocument()
  })

  it('forces open when isActive regardless of defaultOpen', () => {
    const { container } = render(
      <PhaseCard phase="PROPOSE" content="Active content" collapsible defaultOpen={false} isActive />
    )
    // Active overrides collapsed state — content div is rendered (StreamingText starts empty)
    const contentDiv = container.querySelector('.text-sm')
    expect(contentDiv).toBeInTheDocument()
  })

  it('renders individual challengers as separate disclosures', () => {
    const challenges = [
      { model: 'openai:gpt-4', content: 'Challenge A' },
      { model: 'google:gemini', content: 'Challenge B' },
    ]
    render(<PhaseCard phase="CHALLENGE" challenges={challenges} />)
    // Both model badges rendered
    expect(screen.getByText('openai:gpt-4')).toBeInTheDocument()
    expect(screen.getByText('google:gemini')).toBeInTheDocument()
    // Both contents visible (not collapsible by default)
    expect(screen.getByText('Challenge A')).toBeInTheDocument()
    expect(screen.getByText('Challenge B')).toBeInTheDocument()
  })

  it('individual challengers are collapsed when phase is collapsible', () => {
    const challenges = [
      { model: 'openai:gpt-4', content: 'Challenge A' },
    ]
    render(<PhaseCard phase="CHALLENGE" challenges={challenges} collapsible defaultOpen />)
    // Phase is open but individual challenges start collapsed
    expect(screen.queryByText('Challenge A')).toBeNull()
    // Click the model badge to expand
    fireEvent.click(screen.getByText('openai:gpt-4'))
    expect(screen.getByText('Challenge A')).toBeInTheDocument()
  })
})

// ── TurnCard collapsible ─────────────────────────────────

function makeTurn(overrides: Partial<Turn> = {}): Turn {
  return {
    round_number: 1,
    state: 'PROPOSE',
    contributions: [
      { model_ref: 'anthropic:claude', role: 'proposer', content: 'Proposal text', input_tokens: 100, output_tokens: 200, cost_usd: 0.01 },
    ],
    decision: null,
    ...overrides,
  }
}

describe('TurnCard collapsible', () => {
  it('renders contributions when not collapsible', () => {
    render(<TurnCard turn={makeTurn()} />)
    expect(screen.getByText('Proposal text')).toBeInTheDocument()
  })

  it('hides content when collapsible and defaultOpen=false', () => {
    render(<TurnCard turn={makeTurn()} collapsible defaultOpen={false} />)
    expect(screen.queryByText('Proposal text')).toBeNull()
  })

  it('toggles round open on header click, contributions still collapsed', () => {
    render(<TurnCard turn={makeTurn()} collapsible defaultOpen={false} />)
    expect(screen.queryByText('proposer')).toBeNull()
    fireEvent.click(screen.getByText('ROUND 1'))
    // Round opens — contribution headers visible but content still collapsed
    expect(screen.getByText('proposer')).toBeInTheDocument()
    expect(screen.queryByText('Proposal text')).toBeNull()
    // Click contribution to expand
    fireEvent.click(screen.getByText('proposer'))
    expect(screen.getByText('Proposal text')).toBeInTheDocument()
  })

  it('shows confidence preview when collapsed with decision', () => {
    const turn = makeTurn({
      decision: { content: 'Decision', confidence: 0.85, rigor: 0.78, dissent: null },
    })
    render(<TurnCard turn={turn} collapsible defaultOpen={false} />)
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('individual contributions are collapsible when turn is collapsible', () => {
    const turn = makeTurn()
    render(<TurnCard turn={turn} collapsible defaultOpen />)
    // Contribution starts collapsed
    expect(screen.queryByText('Proposal text')).toBeNull()
    // Click the contribution header to expand
    fireEvent.click(screen.getByText('proposer'))
    expect(screen.getByText('Proposal text')).toBeInTheDocument()
  })
})

// ── ConsensusNav ─────────────────────────────────────────

// Mock the consensus store
const mockStoreState = {
  status: 'idle' as string,
  rounds: [] as Array<{
    round: number
    proposer: string | null
    proposal: string | null
    challengers: string[]
    challenges: Array<{ model: string; content: string }>
    reviser: string | null
    revision: string | null
    confidence: number | null
    rigor: number | null
    dissent: string | null
  }>,
  currentRound: 0,
  currentPhase: null as string | null,
}

vi.mock('@/stores/consensus', () => ({
  useConsensusStore: () => mockStoreState,
}))

const { ConsensusNav } = await import('@/components/consensus/ConsensusNav')

describe('ConsensusNav', () => {
  beforeEach(() => {
    mockStoreState.status = 'idle'
    mockStoreState.rounds = []
    mockStoreState.currentRound = 0
    mockStoreState.currentPhase = null
  })

  it('returns null when no rounds', () => {
    const { container } = render(<ConsensusNav />)
    expect(container.firstChild).toBeNull()
  })

  it('renders PROGRESS header when rounds exist', () => {
    mockStoreState.status = 'streaming'
    mockStoreState.rounds = [{
      round: 1, proposer: 'anthropic:claude', proposal: 'Test',
      challengers: [], challenges: [], reviser: null, revision: null,
      confidence: null, rigor: null, dissent: null,
    }]
    mockStoreState.currentRound = 1
    mockStoreState.currentPhase = 'PROPOSE'

    render(<ConsensusNav />)
    expect(screen.getByText('PROGRESS')).toBeInTheDocument()
  })

  it('renders round labels', () => {
    mockStoreState.status = 'streaming'
    mockStoreState.rounds = [
      {
        round: 1, proposer: 'a:b', proposal: 'P', challengers: ['c:d'],
        challenges: [{ model: 'c:d', content: 'Ch' }], reviser: 'a:b', revision: 'R',
        confidence: null, rigor: null, dissent: null,
      },
      {
        round: 2, proposer: 'a:b', proposal: null,
        challengers: [], challenges: [], reviser: null, revision: null,
        confidence: null, rigor: null, dissent: null,
      },
    ]
    mockStoreState.currentRound = 2
    mockStoreState.currentPhase = 'PROPOSE'

    render(<ConsensusNav />)
    expect(screen.getByText('ROUND 1')).toBeInTheDocument()
    expect(screen.getByText('ROUND 2')).toBeInTheDocument()
  })

  it('renders individual challenger model names instead of CHALLENGE', () => {
    mockStoreState.status = 'complete'
    mockStoreState.rounds = [{
      round: 1, proposer: 'a:b', proposal: 'P',
      challengers: ['openai:gpt-4', 'google:gemini'],
      challenges: [
        { model: 'openai:gpt-4', content: 'C1' },
        { model: 'google:gemini', content: 'C2' },
      ],
      reviser: 'a:b', revision: 'R',
      confidence: 0.85, rigor: 0.78, dissent: null,
    }]

    render(<ConsensusNav />)
    // Individual model names shown (short form)
    expect(screen.getByText('gpt-4')).toBeInTheDocument()
    expect(screen.getByText('gemini')).toBeInTheDocument()
    // No generic CHALLENGE label
    expect(screen.queryByText('CHALLENGE')).toBeNull()
  })

  it('shows challenger names from challengers list when challenges not yet received', () => {
    mockStoreState.status = 'streaming'
    mockStoreState.rounds = [{
      round: 1, proposer: 'a:b', proposal: 'P',
      challengers: ['openai:gpt-4'],
      challenges: [],
      reviser: null, revision: null,
      confidence: null, rigor: null, dissent: null,
    }]
    mockStoreState.currentRound = 1
    mockStoreState.currentPhase = 'CHALLENGE'

    render(<ConsensusNav />)
    expect(screen.getByText('gpt-4')).toBeInTheDocument()
  })

  it('renders DECISION entry at top when complete', () => {
    mockStoreState.status = 'complete'
    mockStoreState.rounds = [{
      round: 1, proposer: 'a:b', proposal: 'P', challengers: ['c:d'],
      challenges: [{ model: 'c:d', content: 'Ch' }], reviser: 'a:b', revision: 'R',
      confidence: 0.85, rigor: 0.78, dissent: null,
    }]

    render(<ConsensusNav />)
    expect(screen.getByText('DECISION')).toBeInTheDocument()
  })

  it('does not render DECISION entry when streaming', () => {
    mockStoreState.status = 'streaming'
    mockStoreState.rounds = [{
      round: 1, proposer: 'a:b', proposal: 'P',
      challengers: [], challenges: [], reviser: null, revision: null,
      confidence: null, rigor: null, dissent: null,
    }]
    mockStoreState.currentRound = 1
    mockStoreState.currentPhase = 'PROPOSE'

    render(<ConsensusNav />)
    expect(screen.queryByText('DECISION')).toBeNull()
  })

  it('calls scrollIntoView on nav click', () => {
    const scrollMock = vi.fn()
    const fakeEl = { scrollIntoView: scrollMock } as unknown as HTMLElement
    vi.spyOn(document, 'getElementById').mockReturnValue(fakeEl)

    mockStoreState.status = 'streaming'
    mockStoreState.rounds = [{
      round: 1, proposer: 'a:b', proposal: 'P',
      challengers: [], challenges: [], reviser: null, revision: null,
      confidence: null, rigor: null, dissent: null,
    }]
    mockStoreState.currentRound = 1
    mockStoreState.currentPhase = 'PROPOSE'

    render(<ConsensusNav />)
    fireEvent.click(screen.getByText('ROUND 1'))

    expect(document.getElementById).toHaveBeenCalledWith('consensus-round-1')
    expect(scrollMock).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })

    vi.restoreAllMocks()
  })

  it('renders PROPOSE and REVISE entries for populated phases', () => {
    mockStoreState.status = 'streaming'
    mockStoreState.rounds = [{
      round: 1, proposer: 'a:b', proposal: 'P',
      challengers: ['c:d'], challenges: [{ model: 'c:d', content: 'Ch' }],
      reviser: 'a:b', revision: 'R',
      confidence: null, rigor: null, dissent: null,
    }]
    mockStoreState.currentRound = 1
    mockStoreState.currentPhase = 'REVISE'

    render(<ConsensusNav />)
    expect(screen.getByText('PROPOSE')).toBeInTheDocument()
    expect(screen.getByText('REVISE')).toBeInTheDocument()
  })
})
