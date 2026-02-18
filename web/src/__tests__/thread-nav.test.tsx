import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { ThreadDetail } from '@/api/types'

// Mock the threads store
let mockThread: ThreadDetail | null = null

vi.mock('@/stores/threads', () => ({
  useThreadsStore: (selector?: (s: { currentThread: ThreadDetail | null }) => unknown) => {
    const state = { currentThread: mockThread }
    return selector ? selector(state) : state
  },
}))

// Must import after mock
const { ThreadNav } = await import('@/components/threads/ThreadNav')

function makeThread(turns: ThreadDetail['turns'], status = 'complete'): ThreadDetail {
  return {
    thread_id: 'test-thread-id',
    question: 'Test question?',
    status,
    created_at: '2025-01-01T00:00:00Z',
    turns,
  }
}

describe('ThreadNav', () => {
  beforeEach(() => {
    mockThread = null
  })

  it('returns null when no thread', () => {
    const { container } = render(<ThreadNav />)
    expect(container.firstChild).toBeNull()
  })

  it('returns null when thread has no turns', () => {
    mockThread = makeThread([])
    const { container } = render(<ThreadNav />)
    expect(container.firstChild).toBeNull()
  })

  it('renders ROUNDS header when turns exist', () => {
    mockThread = makeThread([{
      round_number: 1, state: 'PROPOSE',
      contributions: [], decision: null,
    }])

    render(<ThreadNav />)
    expect(screen.getByText('ROUNDS')).toBeInTheDocument()
  })

  it('renders round buttons', () => {
    mockThread = makeThread([
      { round_number: 1, state: 'PROPOSE', contributions: [], decision: null },
      { round_number: 2, state: 'REVISE', contributions: [], decision: null },
    ])

    render(<ThreadNav />)
    expect(screen.getByText('ROUND 1')).toBeInTheDocument()
    expect(screen.getByText('ROUND 2')).toBeInTheDocument()
  })

  it('renders DECISION entry at top when thread is complete with decision', () => {
    mockThread = makeThread([{
      round_number: 1, state: 'PROPOSE', contributions: [],
      decision: { content: 'Decision', confidence: 0.9, rigor: 0.8, dissent: null },
    }], 'complete')

    render(<ThreadNav />)
    expect(screen.getByText('DECISION')).toBeInTheDocument()
    expect(screen.getByText('FEEDBACK')).toBeInTheDocument()
  })

  it('does not render DECISION or FEEDBACK entry when thread is active', () => {
    mockThread = makeThread([{
      round_number: 1, state: 'PROPOSE', contributions: [], decision: null,
    }], 'active')

    render(<ThreadNav />)
    expect(screen.queryByText('DECISION')).toBeNull()
    expect(screen.queryByText('FEEDBACK')).toBeNull()
  })

  it('shows confidence percentage for rounds with decisions', () => {
    mockThread = makeThread([{
      round_number: 1, state: 'PROPOSE', contributions: [],
      decision: { content: 'D', confidence: 0.92, rigor: 0.85, dissent: null },
    }])

    render(<ThreadNav />)
    expect(screen.getByText('92%')).toBeInTheDocument()
  })

  it('calls scrollIntoView on round click', () => {
    const scrollMock = vi.fn()
    const fakeEl = { scrollIntoView: scrollMock } as unknown as HTMLElement
    vi.spyOn(document, 'getElementById').mockReturnValue(fakeEl)

    mockThread = makeThread([{
      round_number: 1, state: 'PROPOSE', contributions: [], decision: null,
    }])

    render(<ThreadNav />)
    fireEvent.click(screen.getByText('ROUND 1'))

    expect(document.getElementById).toHaveBeenCalledWith('thread-round-1')
    expect(scrollMock).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })

    vi.restoreAllMocks()
  })
})
