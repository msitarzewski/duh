import type {
  AskRequest,
  AskResponse,
  CostResponse,
  DecisionSpaceResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  ModelsResponse,
  RecallResponse,
  ThreadDetail,
  ThreadListResponse,
} from './types'
import { ApiError } from './types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(res.status, detail)
  }

  return res.json() as Promise<T>
}

// ── Endpoints ─────────────────────────────────────────────

export const api = {
  health(): Promise<HealthResponse> {
    return request('/health')
  },

  ask(body: AskRequest): Promise<AskResponse> {
    return request('/ask', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  listThreads(params?: {
    status?: string
    limit?: number
    offset?: number
  }): Promise<ThreadListResponse> {
    const qs = new URLSearchParams()
    if (params?.status) qs.set('status', params.status)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const suffix = qs.toString() ? `?${qs}` : ''
    return request(`/threads${suffix}`)
  },

  getThread(threadId: string): Promise<ThreadDetail> {
    return request(`/threads/${encodeURIComponent(threadId)}`)
  },

  recall(query: string, limit = 10): Promise<RecallResponse> {
    const qs = new URLSearchParams({ query, limit: String(limit) })
    return request(`/recall?${qs}`)
  },

  feedback(body: FeedbackRequest): Promise<FeedbackResponse> {
    return request('/feedback', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  models(): Promise<ModelsResponse> {
    return request('/models')
  },

  cost(): Promise<CostResponse> {
    return request('/cost')
  },

  decisionSpace(params?: {
    category?: string
    genus?: string
    outcome?: string
    confidence_min?: number
    confidence_max?: number
    since?: string
    until?: string
    search?: string
  }): Promise<DecisionSpaceResponse> {
    const qs = new URLSearchParams()
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
    }
    const suffix = qs.toString() ? `?${qs}` : ''
    return request(`/decisions/space${suffix}`)
  },

  getShare(shareToken: string): Promise<ThreadDetail> {
    return request(`/share/${encodeURIComponent(shareToken)}`)
  },
}
