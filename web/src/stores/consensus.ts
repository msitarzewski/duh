import { create } from 'zustand'
import { ConsensusWebSocket } from '@/api/websocket'
import type {
  WSEvent,
  WSPhaseStart,
  ConsensusPhase,
  ModelSelectionOptions,
} from '@/api/types'

export type ConsensusStatus = 'idle' | 'connecting' | 'streaming' | 'complete' | 'error'

export interface ChallengeEntry {
  model: string
  content: string
}

export interface RoundData {
  round: number
  proposer: string | null
  proposal: string | null
  challengers: string[]
  challenges: ChallengeEntry[]
  reviser: string | null
  revision: string | null
  confidence: number | null
  rigor: number | null
  dissent: string | null
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

  // Actions
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
  }
}

export const useConsensusStore = create<ConsensusState>((set, get) => ({
  status: 'idle',
  error: null,
  currentPhase: null,
  currentRound: 0,
  rounds: [],
  question: null,
  decision: null,
  confidence: null,
  rigor: null,
  dissent: null,
  cost: null,
  threadId: null,

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
    set({
      status: 'idle',
      error: null,
      currentPhase: null,
      currentRound: 0,
      rounds: [],
      question: null,
      decision: null,
      confidence: null,
      rigor: null,
      dissent: null,
      cost: null,
      threadId: null,
    })
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
      if (event.phase === 'PROPOSE') update.proposal = event.content ?? null
      else if (event.phase === 'REVISE') update.revision = event.content ?? null

      set({ rounds: updateRound(state.rounds, idx, { ...round, ...update }) })
      break
    }

    case 'challenge': {
      const found = getRound(state.rounds, state.currentRound)
      if (!found) break
      const [round, idx] = found

      set({
        rounds: updateRound(state.rounds, idx, {
          challenges: [...round.challenges, { model: event.model, content: event.content }],
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
      })
      break
    }

    case 'error': {
      set({ status: 'error', error: event.message })
      break
    }
  }
}
