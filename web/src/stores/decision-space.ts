import { create } from 'zustand'
import { api } from '@/api/client'
import type { SpaceDecision } from '@/api/types'

export interface SpaceFilters {
  categories: string[]
  genera: string[]
  outcomes: string[]
  confidenceMin: number
  confidenceMax: number
  since: string | null
  until: string | null
  search: string
}

interface DecisionSpaceState {
  // Data
  decisions: SpaceDecision[]
  availableCategories: string[]
  availableGenera: string[]
  loading: boolean
  error: string | null

  // Filters
  filters: SpaceFilters

  // Interaction
  hoveredId: string | null
  selectedId: string | null

  // Timeline
  timelinePosition: number // 0-1 progress
  timelinePlaying: boolean
  timelineSpeed: number // 1, 2, 4

  // Actions
  fetchDecisions: () => Promise<void>
  setFilter: <K extends keyof SpaceFilters>(key: K, value: SpaceFilters[K]) => void
  resetFilters: () => void
  setHovered: (id: string | null) => void
  setSelected: (id: string | null) => void
  setTimelinePosition: (pos: number) => void
  toggleTimelinePlaying: () => void
  setTimelineSpeed: (speed: number) => void
}

const defaultFilters: SpaceFilters = {
  categories: [],
  genera: [],
  outcomes: [],
  confidenceMin: 0,
  confidenceMax: 1,
  since: null,
  until: null,
  search: '',
}

export const useDecisionSpaceStore = create<DecisionSpaceState>((set) => ({
  decisions: [],
  availableCategories: [],
  availableGenera: [],
  loading: false,
  error: null,

  filters: { ...defaultFilters },

  hoveredId: null,
  selectedId: null,

  timelinePosition: 1,
  timelinePlaying: false,
  timelineSpeed: 1,

  fetchDecisions: async () => {
    set({ loading: true, error: null })
    try {
      const data = await api.decisionSpace()
      set({
        decisions: data.decisions,
        availableCategories: data.axes.categories,
        availableGenera: data.axes.genera,
        loading: false,
      })
    } catch (e) {
      set({ error: (e as Error).message, loading: false })
    }
  },

  setFilter: (key, value) => {
    set((state) => ({
      filters: { ...state.filters, [key]: value },
    }))
  },

  resetFilters: () => {
    set({ filters: { ...defaultFilters } })
  },

  setHovered: (id) => set({ hoveredId: id }),
  setSelected: (id) => set({ selectedId: id }),

  setTimelinePosition: (pos) => set({ timelinePosition: pos }),
  toggleTimelinePlaying: () => set((s) => ({ timelinePlaying: !s.timelinePlaying })),
  setTimelineSpeed: (speed) => set({ timelineSpeed: speed }),
}))
