import { create } from 'zustand'
import { ConsensusWebSocket } from '@/api/websocket'
import { api } from '@/api/client'
import type {
  WSEvent,
  WSPhaseStart,
  ConsensusPhase,
  ClarifyingQuestion,
  ModelSelectionOptions,
  Citation,
} from '@/api/types'

export type ConsensusStatus = 'idle' | 'connecting' | 'streaming' | 'complete' | 'error' | 'refining'

export interface ChallengeEntry {
  model: string
  content: string
  truncated?: boolean
  error?: boolean
  citations?: Citation[] | null
}

export interface RoundData {
  round: number
  proposer: string | null
  proposal: string | null
  proposalCitations?: Citation[] | null
  challengers: string[]
  challenges: ChallengeEntry[]
  reviser: string | null
  revision: string | null
  confidence: number | null
  rigor: number | null
  dissent: string | null
  truncated: string[]
}

interface ConsensusState {
  // Connection
  status: ConsensusStatus
  error: string | null

  // Current phase
  currentPhase: ConsensusPhase | null
  currentRound: number

  // Round data
  rounds: RoundData[]

  // Final result
  question: string | null
  decision: string | null
  confidence: number | null
  rigor: number | null
  dissent: string | null
  cost: number | null
  threadId: string | null
  overview: string | null

  // Refinement
  clarifyingQuestions: ClarifyingQuestion[]
  clarificationAnswers: Record<number, string>
  pendingRounds: number
  pendingProtocol: string
  pendingModelSelection: ModelSelectionOptions | undefined

  // Actions
  submitQuestion: (question: string, rounds?: number, protocol?: string, modelSelection?: ModelSelectionOptions) => void
  answerClarification: (index: number, answer: string) => void
  submitClarifications: () => void
  skipRefinement: () => void
  startConsensus: (question: string, rounds?: number, protocol?: string, modelSelection?: ModelSelectionOptions) => void
  reset: () => void
  disconnect: () => void
}

const ws = new ConsensusWebSocket()

function createEmptyRound(round: number): RoundData {
  return {
    round,
    proposer: null,
    proposal: null,
    challengers: [],
    challenges: [],
    reviser: null,
    revision: null,
    confidence: null,
    rigor: null,
    dissent: null,
    truncated: [],
  }
}

const initialState = {
  status: 'idle' as ConsensusStatus,
  error: null as string | null,
  currentPhase: null as ConsensusPhase | null,
  currentRound: 0,
  rounds: [] as RoundData[],
  question: null as string | null,
  decision: null as string | null,
  confidence: null as number | null,
  rigor: null as number | null,
  dissent: null as string | null,
  cost: null as number | null,
  threadId: null as string | null,
  overview: null as string | null,
  clarifyingQuestions: [] as ClarifyingQuestion[],
  clarificationAnswers: {} as Record<number, string>,
  pendingRounds: 3,
  pendingProtocol: 'consensus',
  pendingModelSelection: undefined as ModelSelectionOptions | undefined,
}

export const useConsensusStore = create<ConsensusState>((set, get) => ({
  ...initialState,

  submitQuestion: async (question, rounds = 3, protocol = 'consensus', modelSelection?) => {
    set({
      ...initialState,
      status: 'refining',
      question,
      pendingRounds: rounds,
      pendingProtocol: protocol,
      pendingModelSelection: modelSelection,
    })

    try {
      const result = await api.refine(question)
      if (result.needs_refinement && result.questions.length > 0) {
        set({ clarifyingQuestions: result.questions })
      } else {
        get().startConsensus(question, rounds, protocol, modelSelection)
      }
    } catch {
      // Refinement failed — proceed directly to consensus
      get().startConsensus(question, rounds, protocol, modelSelection)
    }
  },

  answerClarification: (index, answer) => {
    set((state) => ({
      clarificationAnswers: { ...state.clarificationAnswers, [index]: answer },
    }))
  },

  submitClarifications: async () => {
    const state = get()
    const { question, clarifyingQuestions, clarificationAnswers } = state
    if (!question) return

    set({ status: 'refining', clarifyingQuestions: [], clarificationAnswers: {} })

    const clarifications = clarifyingQuestions.map((q, i) => ({
      question: q.question,
      answer: clarificationAnswers[i] || '',
    }))

    try {
      const result = await api.enrich(question, clarifications)
      get().startConsensus(
        result.enriched_question,
        state.pendingRounds,
        state.pendingProtocol,
        state.pendingModelSelection,
      )
    } catch {
      // Enrichment failed — use original question
      get().startConsensus(
        question,
        state.pendingRounds,
        state.pendingProtocol,
        state.pendingModelSelection,
      )
    }
  },

  skipRefinement: () => {
    const state = get()
    if (state.question) {
      get().startConsensus(
        state.question,
        state.pendingRounds,
        state.pendingProtocol,
        state.pendingModelSelection,
      )
    }
  },

  startConsensus: (question, rounds = 3, protocol = 'consensus', modelSelection?) => {
    set({
      status: 'connecting',
      error: null,
      currentPhase: null,
      currentRound: 0,
      rounds: [],
      question,
      decision: null,
      confidence: null,
      rigor: null,
      dissent: null,
      cost: null,
      threadId: null,
      overview: null,
      clarifyingQuestions: [],
      clarificationAnswers: {},
    })

    ws.connect({
      question,
      rounds,
      protocol,
      modelSelection,
      onStatusChange: (wsStatus) => {
        if (wsStatus === 'connected') {
          set({ status: 'streaming' })
        } else if (wsStatus === 'error') {
          set({ status: 'error', error: 'WebSocket connection failed' })
        }
      },
      onEvent: (event: WSEvent) => {
        const state = get()
        handleEvent(event, state, set)
      },
      onError: () => {
        set({ status: 'error', error: 'WebSocket error' })
      },
    })
  },

  reset: () => {
    ws.close()
    set(initialState)
  },

  disconnect: () => {
    ws.close()
  },
}))

function getRound(rounds: RoundData[], roundNum: number): [RoundData, number] | null {
  const idx = rounds.findIndex((r) => r.round === roundNum)
  if (idx < 0) return null
  return [rounds[idx] as RoundData, idx]
}

function updateRound(rounds: RoundData[], idx: number, update: Partial<RoundData>): RoundData[] {
  const copy = [...rounds]
  copy[idx] = { ...(copy[idx] as RoundData), ...update }
  return copy
}

function handleEvent(
  event: WSEvent,
  state: ConsensusState,
  set: (partial: Partial<ConsensusState>) => void,
): void {
  switch (event.type) {
    case 'phase_start': {
      const e = event as WSPhaseStart
      const roundNum = e.round
      let rounds = [...state.rounds]

      if (!rounds.find((r) => r.round === roundNum)) {
        rounds = [...rounds, createEmptyRound(roundNum)]
      }

      const found = getRound(rounds, roundNum)
      if (!found) break
      const [round, idx] = found

      const update: Partial<RoundData> = {}
      if (e.phase === 'PROPOSE') update.proposer = e.model ?? null
      else if (e.phase === 'CHALLENGE') update.challengers = e.models ?? []
      else if (e.phase === 'REVISE') update.reviser = e.model ?? null

      rounds = updateRound(rounds, idx, { ...round, ...update })
      set({ currentPhase: e.phase, currentRound: roundNum, rounds })
      break
    }

    case 'phase_complete': {
      const found = getRound(state.rounds, state.currentRound)
      if (!found) break
      const [round, idx] = found

      const update: Partial<RoundData> = {}
      if (event.phase === 'PROPOSE') {
        update.proposal = event.content ?? null
        update.proposalCitations = event.citations ?? null
        if (event.truncated) update.truncated = [...round.truncated, 'PROPOSE']
      } else if (event.phase === 'REVISE') {
        update.revision = event.content ?? null
        if (event.truncated) update.truncated = [...round.truncated, 'REVISE']
      }

      set({ rounds: updateRound(state.rounds, idx, { ...round, ...update }) })
      break
    }

    case 'challenge': {
      const found = getRound(state.rounds, state.currentRound)
      if (!found) break
      const [round, idx] = found

      const truncatedUpdate = event.truncated ? [...round.truncated, `CHALLENGE:${event.model}`] : round.truncated
      set({
        rounds: updateRound(state.rounds, idx, {
          challenges: [...round.challenges, { model: event.model, content: event.content, truncated: event.truncated, citations: event.citations }],
          truncated: truncatedUpdate,
        }),
      })
      break
    }

    case 'challenge_error': {
      const found = getRound(state.rounds, state.currentRound)
      if (!found) break
      const [round, idx] = found

      set({
        rounds: updateRound(state.rounds, idx, {
          challenges: [...round.challenges, { model: event.model, content: 'Challenge failed', error: true }],
        }),
      })
      break
    }

    case 'commit': {
      const found = getRound(state.rounds, state.currentRound)
      if (!found) break
      const [, idx] = found

      set({
        currentPhase: 'COMMIT' as ConsensusPhase,
        rounds: updateRound(state.rounds, idx, {
          confidence: event.confidence,
          rigor: event.rigor,
          dissent: event.dissent,
        }),
      })
      break
    }

    case 'complete': {
      set({
        status: 'complete',
        decision: event.decision,
        confidence: event.confidence,
        rigor: event.rigor,
        dissent: event.dissent,
        cost: event.cost,
        threadId: event.thread_id ?? null,
        overview: event.overview ?? null,
      })
      break
    }

    case 'error': {
      set({ status: 'error', error: event.message })
      break
    }
  }
}
