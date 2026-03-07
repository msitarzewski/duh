import type {
  AskRequest,
  AskResponse,
  AuthStatusResponse,
  CalibrationResponse,
  CostResponse,
  DecisionSpaceResponse,
  FeedbackRequest,
  FeedbackResponse,
  ForgotPasswordRequest,
  ForgotPasswordResponse,
  HealthResponse,
  LoginRequest,
  ModelsResponse,
  RecallResponse,
  RegisterRequest,
  ResetPasswordRequest,
  ResetPasswordResponse,
  ThreadDetail,
  ThreadListResponse,
  TokenResponse,
  UserInfo,
} from './types'
import { ApiError } from './types'

const BASE = '/api'
const TOKEN_KEY = 'duh_token'

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    return { Authorization: `Bearer ${token}` }
  }
  return {}
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...options?.headers,
    },
    ...options,
  })

  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
    }
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
  // Auth
  login(body: LoginRequest): Promise<TokenResponse> {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  register(body: RegisterRequest): Promise<TokenResponse> {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  me(): Promise<UserInfo> {
    return request('/auth/me')
  },

  authStatus(): Promise<AuthStatusResponse> {
    return request('/auth/status')
  },

  forgotPassword(body: ForgotPasswordRequest): Promise<ForgotPasswordResponse> {
    return request('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  resetPassword(body: ResetPasswordRequest): Promise<ResetPasswordResponse> {
    return request('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  // Health
  health(): Promise<HealthResponse> {
    return request('/health')
  },

  // Consensus
  ask(body: AskRequest): Promise<AskResponse> {
    return request('/ask', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  // Threads
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

  calibration(params?: {
    category?: string
    since?: string
    until?: string
  }): Promise<CalibrationResponse> {
    const qs = new URLSearchParams()
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v != null) qs.set(k, String(v))
      }
    }
    const suffix = qs.toString() ? `?${qs}` : ''
    return request(`/calibration${suffix}`)
  },

  getShare(shareToken: string): Promise<ThreadDetail> {
    return request(`/share/${encodeURIComponent(shareToken)}`)
  },
}
