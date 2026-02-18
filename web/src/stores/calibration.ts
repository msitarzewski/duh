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

  // Actions
  fetchCalibration: () => Promise<void>
  setCategory: (category: string | null) => void
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

  fetchCalibration: async () => {
    set({ loading: true, error: null })
    try {
      const { category } = get()
      const params: { category?: string } = {}
      if (category) params.category = category

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
}))
