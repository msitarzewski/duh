import { create } from 'zustand'
import { api } from '@/api/client'
import type { ThreadSummary, ThreadDetail, RecallResult } from '@/api/types'

interface ThreadsState {
  // List
  threads: ThreadSummary[]
  total: number
  loading: boolean
  error: string | null
  statusFilter: string | null
  page: number
  pageSize: number

  // Detail
  currentThread: ThreadDetail | null
  detailLoading: boolean
  detailError: string | null

  // Search
  searchResults: RecallResult[]
  searchQuery: string
  searchLoading: boolean

  // Actions
  fetchThreads: () => Promise<void>
  fetchThread: (id: string) => Promise<void>
  setStatusFilter: (status: string | null) => void
  setPage: (page: number) => void
  search: (query: string) => Promise<void>
  clearSearch: () => void
  submitFeedback: (threadId: string, result: 'success' | 'failure' | 'partial', notes?: string) => Promise<void>
}

export const useThreadsStore = create<ThreadsState>((set, get) => ({
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

  fetchThreads: async () => {
    const { statusFilter, page, pageSize } = get()
    set({ loading: true, error: null })
    try {
      const data = await api.listThreads({
        status: statusFilter ?? undefined,
        limit: pageSize,
        offset: page * pageSize,
      })
      set({ threads: data.threads, total: data.total, loading: false })
    } catch (e) {
      set({ error: (e as Error).message, loading: false })
    }
  },

  fetchThread: async (id) => {
    set({ detailLoading: true, detailError: null, currentThread: null })
    try {
      const data = await api.getThread(id)
      set({ currentThread: data, detailLoading: false })
    } catch (e) {
      set({ detailError: (e as Error).message, detailLoading: false })
    }
  },

  setStatusFilter: (status) => {
    set({ statusFilter: status, page: 0 })
    get().fetchThreads()
  },

  setPage: (page) => {
    set({ page })
    get().fetchThreads()
  },

  search: async (query) => {
    if (!query.trim()) {
      set({ searchResults: [], searchQuery: '' })
      return
    }
    set({ searchLoading: true, searchQuery: query })
    try {
      const data = await api.recall(query)
      set({ searchResults: data.results, searchLoading: false })
    } catch {
      set({ searchLoading: false })
    }
  },

  clearSearch: () => {
    set({ searchResults: [], searchQuery: '' })
  },

  submitFeedback: async (threadId, result, notes) => {
    await api.feedback({ thread_id: threadId, result, notes })
  },
}))
