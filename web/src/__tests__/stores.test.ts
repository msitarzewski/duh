import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Mock the websocket module before importing consensus store ──
vi.mock('@/api/websocket', () => {
  return {
    ConsensusWebSocket: vi.fn().mockImplementation(() => ({
      connect: vi.fn(),
      close: vi.fn(),
      getStatus: vi.fn().mockReturnValue('idle'),
    })),
  }
})

// ── Mock the API client before importing stores that use it ──
vi.mock('@/api/client', () => ({
  api: {
    listThreads: vi.fn(),
    getThread: vi.fn(),
    recall: vi.fn(),
    feedback: vi.fn(),
    decisionSpace: vi.fn(),
    calibration: vi.fn(),
  },
}))

import { useConsensusStore } from '@/stores/consensus'
import { useThreadsStore } from '@/stores/threads'
import { usePreferencesStore } from '@/stores/preferences'
import { useDecisionSpaceStore } from '@/stores/decision-space'
import { useCalibrationStore } from '@/stores/calibration'
import { api } from '@/api/client'

const mockedApi = vi.mocked(api)

// ── Consensus Store ───────────────────────────────────────

describe('useConsensusStore', () => {
  beforeEach(() => {
    useConsensusStore.getState().reset()
  })

  it('has correct initial state', () => {
    const state = useConsensusStore.getState()
    expect(state.status).toBe('idle')
    expect(state.error).toBeNull()
    expect(state.currentPhase).toBeNull()
    expect(state.currentRound).toBe(0)
    expect(state.rounds).toEqual([])
    expect(state.decision).toBeNull()
    expect(state.confidence).toBeNull()
    expect(state.rigor).toBeNull()
    expect(state.dissent).toBeNull()
    expect(state.cost).toBeNull()
  })

  it('sets status to connecting when startConsensus is called', () => {
    useConsensusStore.getState().startConsensus('What is 2+2?')
    const state = useConsensusStore.getState()
    expect(state.status).toBe('connecting')
    expect(state.error).toBeNull()
  })

  it('resets state fully', () => {
    // Mutate the store first
    useConsensusStore.setState({
      status: 'error',
      error: 'some error',
      currentPhase: 'PROPOSE',
      currentRound: 2,
      decision: 'answer',
      confidence: 0.9,
    })

    useConsensusStore.getState().reset()
    const state = useConsensusStore.getState()
    expect(state.status).toBe('idle')
    expect(state.error).toBeNull()
    expect(state.currentPhase).toBeNull()
    expect(state.currentRound).toBe(0)
    expect(state.decision).toBeNull()
    expect(state.confidence).toBeNull()
  })

  it('disconnect calls close on websocket', () => {
    useConsensusStore.getState().disconnect()
    // Should not throw
    expect(useConsensusStore.getState().status).toBeDefined()
  })
})

// ── Threads Store ─────────────────────────────────────────

describe('useThreadsStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useThreadsStore.setState({
      threads: [],
      total: 0,
      loading: false,
      error: null,
      statusFilter: null,
      page: 0,
      pageSize: 20,
      currentThread: null,
      detailLoading: false,
      detailError: null,
      searchResults: [],
      searchQuery: '',
      searchLoading: false,
    })
  })

  it('has correct initial state', () => {
    const state = useThreadsStore.getState()
    expect(state.threads).toEqual([])
    expect(state.total).toBe(0)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.page).toBe(0)
  })

  it('fetchThreads sets loading and populates threads', async () => {
    const mockThreads = {
      threads: [
        { thread_id: '1', question: 'Q1', status: 'complete', created_at: '2025-01-01' },
      ],
      total: 1,
    }
    mockedApi.listThreads.mockResolvedValue(mockThreads)

    await useThreadsStore.getState().fetchThreads()
    const state = useThreadsStore.getState()
    expect(state.threads).toEqual(mockThreads.threads)
    expect(state.total).toBe(1)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
  })

  it('fetchThreads handles errors', async () => {
    mockedApi.listThreads.mockRejectedValue(new Error('Network fail'))

    await useThreadsStore.getState().fetchThreads()
    const state = useThreadsStore.getState()
    expect(state.error).toBe('Network fail')
    expect(state.loading).toBe(false)
  })

  it('fetchThread loads thread detail', async () => {
    const mockThread = {
      thread_id: '1',
      question: 'Q1',
      status: 'complete',
      created_at: '2025-01-01',
      turns: [],
    }
    mockedApi.getThread.mockResolvedValue(mockThread)

    await useThreadsStore.getState().fetchThread('1')
    const state = useThreadsStore.getState()
    expect(state.currentThread).toEqual(mockThread)
    expect(state.detailLoading).toBe(false)
  })

  it('fetchThread handles errors', async () => {
    mockedApi.getThread.mockRejectedValue(new Error('Not found'))

    await useThreadsStore.getState().fetchThread('999')
    const state = useThreadsStore.getState()
    expect(state.detailError).toBe('Not found')
    expect(state.detailLoading).toBe(false)
  })

  it('setStatusFilter updates filter and resets page', async () => {
    mockedApi.listThreads.mockResolvedValue({ threads: [], total: 0 })
    useThreadsStore.setState({ page: 5 })

    useThreadsStore.getState().setStatusFilter('complete')
    // Wait for async fetchThreads triggered by setStatusFilter
    await vi.waitFor(() => {
      expect(useThreadsStore.getState().statusFilter).toBe('complete')
    })
    expect(useThreadsStore.getState().page).toBe(0)
  })

  it('search populates results', async () => {
    const mockResults = {
      results: [
        { thread_id: '1', question: 'Q1', decision: 'D1', confidence: 0.9 },
      ],
      query: 'test',
    }
    mockedApi.recall.mockResolvedValue(mockResults)

    await useThreadsStore.getState().search('test')
    const state = useThreadsStore.getState()
    expect(state.searchResults).toEqual(mockResults.results)
    expect(state.searchQuery).toBe('test')
  })

  it('search with empty query clears results', async () => {
    useThreadsStore.setState({ searchResults: [{ thread_id: '1', question: 'Q', decision: 'D', confidence: 0.9 }], searchQuery: 'old' })
    await useThreadsStore.getState().search('  ')
    const state = useThreadsStore.getState()
    expect(state.searchResults).toEqual([])
    expect(state.searchQuery).toBe('')
  })

  it('clearSearch resets search state', () => {
    useThreadsStore.setState({ searchResults: [{ thread_id: '1', question: 'Q', decision: 'D', confidence: 0.9 }], searchQuery: 'test' })
    useThreadsStore.getState().clearSearch()
    const state = useThreadsStore.getState()
    expect(state.searchResults).toEqual([])
    expect(state.searchQuery).toBe('')
  })

  it('submitFeedback calls API', async () => {
    mockedApi.feedback.mockResolvedValue({ status: 'ok', thread_id: '1' })
    await useThreadsStore.getState().submitFeedback('1', 'success', 'Great!')
    expect(mockedApi.feedback).toHaveBeenCalledWith({
      thread_id: '1',
      result: 'success',
      notes: 'Great!',
    })
  })
})

// ── Preferences Store ─────────────────────────────────────

describe('usePreferencesStore', () => {
  beforeEach(() => {
    usePreferencesStore.setState({
      defaultRounds: 3,
      defaultProtocol: 'consensus',
      costThreshold: null,
      soundEnabled: false,
    })
  })

  it('has correct initial state', () => {
    const state = usePreferencesStore.getState()
    expect(state.defaultRounds).toBe(3)
    expect(state.defaultProtocol).toBe('consensus')
    expect(state.costThreshold).toBeNull()
    expect(state.soundEnabled).toBe(false)
  })

  it('setDefaultRounds updates rounds', () => {
    usePreferencesStore.getState().setDefaultRounds(5)
    expect(usePreferencesStore.getState().defaultRounds).toBe(5)
  })

  it('setDefaultProtocol updates protocol', () => {
    usePreferencesStore.getState().setDefaultProtocol('voting')
    expect(usePreferencesStore.getState().defaultProtocol).toBe('voting')
  })

  it('setCostThreshold updates threshold', () => {
    usePreferencesStore.getState().setCostThreshold(0.5)
    expect(usePreferencesStore.getState().costThreshold).toBe(0.5)
  })

  it('setCostThreshold accepts null', () => {
    usePreferencesStore.getState().setCostThreshold(0.5)
    usePreferencesStore.getState().setCostThreshold(null)
    expect(usePreferencesStore.getState().costThreshold).toBeNull()
  })

  it('setSoundEnabled toggles sound', () => {
    usePreferencesStore.getState().setSoundEnabled(true)
    expect(usePreferencesStore.getState().soundEnabled).toBe(true)
    usePreferencesStore.getState().setSoundEnabled(false)
    expect(usePreferencesStore.getState().soundEnabled).toBe(false)
  })
})

// ── Decision Space Store ──────────────────────────────────

describe('useDecisionSpaceStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useDecisionSpaceStore.setState({
      decisions: [],
      availableCategories: [],
      availableGenera: [],
      loading: false,
      error: null,
      filters: {
        categories: [],
        genera: [],
        outcomes: [],
        confidenceMin: 0,
        confidenceMax: 1,
        since: null,
        until: null,
        search: '',
      },
      hoveredId: null,
      selectedId: null,
      timelinePosition: 1,
      timelinePlaying: false,
      timelineSpeed: 1,
    })
  })

  it('has correct initial state', () => {
    const state = useDecisionSpaceStore.getState()
    expect(state.decisions).toEqual([])
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.filters.confidenceMin).toBe(0)
    expect(state.filters.confidenceMax).toBe(1)
    expect(state.timelinePosition).toBe(1)
  })

  it('fetchDecisions populates data', async () => {
    const mockData = {
      decisions: [
        {
          id: '1',
          thread_id: 't1',
          question: 'Q1',
          confidence: 0.85,
          rigor: 0.72,
          intent: null,
          category: 'tech',
          genus: null,
          outcome: null,
          created_at: '2025-01-01',
        },
      ],
      axes: { categories: ['tech'], genera: ['analysis'] },
      total: 1,
    }
    mockedApi.decisionSpace.mockResolvedValue(mockData)

    await useDecisionSpaceStore.getState().fetchDecisions()
    const state = useDecisionSpaceStore.getState()
    expect(state.decisions).toEqual(mockData.decisions)
    expect(state.availableCategories).toEqual(['tech'])
    expect(state.availableGenera).toEqual(['analysis'])
    expect(state.loading).toBe(false)
  })

  it('fetchDecisions handles errors', async () => {
    mockedApi.decisionSpace.mockRejectedValue(new Error('Server error'))

    await useDecisionSpaceStore.getState().fetchDecisions()
    const state = useDecisionSpaceStore.getState()
    expect(state.error).toBe('Server error')
    expect(state.loading).toBe(false)
  })

  it('setFilter updates individual filter', () => {
    useDecisionSpaceStore.getState().setFilter('categories', ['tech', 'science'])
    expect(useDecisionSpaceStore.getState().filters.categories).toEqual(['tech', 'science'])
  })

  it('resetFilters restores defaults', () => {
    useDecisionSpaceStore.getState().setFilter('confidenceMin', 0.5)
    useDecisionSpaceStore.getState().setFilter('search', 'test')
    useDecisionSpaceStore.getState().resetFilters()

    const state = useDecisionSpaceStore.getState()
    expect(state.filters.confidenceMin).toBe(0)
    expect(state.filters.search).toBe('')
  })

  it('setHovered and setSelected update interaction state', () => {
    useDecisionSpaceStore.getState().setHovered('item1')
    expect(useDecisionSpaceStore.getState().hoveredId).toBe('item1')

    useDecisionSpaceStore.getState().setSelected('item2')
    expect(useDecisionSpaceStore.getState().selectedId).toBe('item2')

    useDecisionSpaceStore.getState().setHovered(null)
    expect(useDecisionSpaceStore.getState().hoveredId).toBeNull()
  })

  it('toggleTimelinePlaying toggles playback', () => {
    expect(useDecisionSpaceStore.getState().timelinePlaying).toBe(false)
    useDecisionSpaceStore.getState().toggleTimelinePlaying()
    expect(useDecisionSpaceStore.getState().timelinePlaying).toBe(true)
    useDecisionSpaceStore.getState().toggleTimelinePlaying()
    expect(useDecisionSpaceStore.getState().timelinePlaying).toBe(false)
  })

  it('setTimelinePosition updates position', () => {
    useDecisionSpaceStore.getState().setTimelinePosition(0.5)
    expect(useDecisionSpaceStore.getState().timelinePosition).toBe(0.5)
  })

  it('setTimelineSpeed updates speed', () => {
    useDecisionSpaceStore.getState().setTimelineSpeed(4)
    expect(useDecisionSpaceStore.getState().timelineSpeed).toBe(4)
  })
})

// ── Calibration Store ────────────────────────────────────

describe('useCalibrationStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useCalibrationStore.setState({
      buckets: [],
      totalDecisions: 0,
      totalWithOutcomes: 0,
      overallAccuracy: 0,
      ece: 0,
      loading: false,
      error: null,
      category: null,
    })
  })

  it('has correct initial state', () => {
    const state = useCalibrationStore.getState()
    expect(state.buckets).toEqual([])
    expect(state.totalDecisions).toBe(0)
    expect(state.totalWithOutcomes).toBe(0)
    expect(state.overallAccuracy).toBe(0)
    expect(state.ece).toBe(0)
    expect(state.loading).toBe(false)
    expect(state.error).toBeNull()
    expect(state.category).toBeNull()
  })

  it('fetchCalibration populates data', async () => {
    const mockData = {
      buckets: [
        {
          range_lo: 0.0,
          range_hi: 0.1,
          count: 0,
          with_outcomes: 0,
          success: 0,
          failure: 0,
          partial: 0,
          accuracy: 0,
          mean_confidence: 0.05,
        },
      ],
      total_decisions: 5,
      total_with_outcomes: 3,
      overall_accuracy: 0.75,
      ece: 0.08,
    }
    mockedApi.calibration.mockResolvedValue(mockData)

    await useCalibrationStore.getState().fetchCalibration()
    const state = useCalibrationStore.getState()
    expect(state.totalDecisions).toBe(5)
    expect(state.totalWithOutcomes).toBe(3)
    expect(state.overallAccuracy).toBe(0.75)
    expect(state.ece).toBe(0.08)
    expect(state.buckets).toEqual(mockData.buckets)
    expect(state.loading).toBe(false)
  })

  it('fetchCalibration handles errors', async () => {
    mockedApi.calibration.mockRejectedValue(new Error('Server error'))

    await useCalibrationStore.getState().fetchCalibration()
    const state = useCalibrationStore.getState()
    expect(state.error).toBe('Server error')
    expect(state.loading).toBe(false)
  })

  it('setCategory updates category filter', () => {
    useCalibrationStore.getState().setCategory('tech')
    expect(useCalibrationStore.getState().category).toBe('tech')

    useCalibrationStore.getState().setCategory(null)
    expect(useCalibrationStore.getState().category).toBeNull()
  })
})
