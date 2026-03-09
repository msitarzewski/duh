import { create } from 'zustand'
import { api } from '@/api/client'
import type { CalibrationBucket } from '@/api/types'

interface CalibrationState {
  buckets: CalibrationBucket[]
  totalDecisions: number
  totalWithOutcomes: number
  overallAccuracy: number
  ece: number
  loading: boolean
  error: string | null

  // Filters
  category: string | null
  since: string | null
  until: string | null

  // Actions
  fetchCalibration: () => Promise<void>
  setCategory: (category: string | null) => void
  setSince: (since: string | null) => void
  setUntil: (until: string | null) => void
}

export const useCalibrationStore = create<CalibrationState>((set, get) => ({
  buckets: [],
  totalDecisions: 0,
  totalWithOutcomes: 0,
  overallAccuracy: 0,
  ece: 0,
  loading: false,
  error: null,

  category: null,
  since: null,
  until: null,

  fetchCalibration: async () => {
    set({ loading: true, error: null })
    try {
      const { category, since, until } = get()
      const params: { category?: string; since?: string; until?: string } = {}
      if (category) params.category = category
      if (since) params.since = since
      if (until) params.until = until

      const data = await api.calibration(params)
      set({
        buckets: data.buckets,
        totalDecisions: data.total_decisions,
        totalWithOutcomes: data.total_with_outcomes,
        overallAccuracy: data.overall_accuracy,
        ece: data.ece,
        loading: false,
      })
    } catch (e) {
      set({ error: (e as Error).message, loading: false })
    }
  },

  setCategory: (category) => {
    set({ category })
  },

  setSince: (since) => {
    set({ since })
  },

  setUntil: (until) => {
    set({ until })
  },
}))
