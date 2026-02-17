import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { api } from '@/api/client'
import { ApiError } from '@/api/types'

// We need the REAL api module here, so unmock it
vi.unmock('@/api/client')

const mockFetch = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch)
})

afterEach(() => {
  vi.restoreAllMocks()
})

function jsonResponse(data: unknown, status = 200, statusText = 'OK') {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(data),
  } as Response)
}

function errorResponse(status: number, detail?: string) {
  const body = detail ? { detail } : undefined
  return Promise.resolve({
    ok: false,
    status,
    statusText: 'Error',
    json: body ? () => Promise.resolve(body) : () => Promise.reject(new Error('no json')),
  } as Response)
}

describe('api.health', () => {
  it('calls /api/health', async () => {
    mockFetch.mockReturnValue(jsonResponse({ status: 'ok' }))
    const result = await api.health()
    expect(result).toEqual({ status: 'ok' })
    expect(mockFetch).toHaveBeenCalledWith('/api/health', expect.objectContaining({
      headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
    }))
  })
})

describe('api.ask', () => {
  it('sends POST with body', async () => {
    const response = { decision: 'Yes', confidence: 0.9, dissent: null, cost: 0.01, thread_id: '1', protocol_used: 'consensus' }
    mockFetch.mockReturnValue(jsonResponse(response))

    const result = await api.ask({ question: 'Is it raining?' })
    expect(result).toEqual(response)
    expect(mockFetch).toHaveBeenCalledWith('/api/ask', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ question: 'Is it raining?' }),
    }))
  })
})

describe('api.listThreads', () => {
  it('builds query string from params', async () => {
    mockFetch.mockReturnValue(jsonResponse({ threads: [], total: 0 }))
    await api.listThreads({ status: 'complete', limit: 10, offset: 20 })

    const calledUrl = mockFetch.mock.calls[0]![0] as string
    expect(calledUrl).toContain('status=complete')
    expect(calledUrl).toContain('limit=10')
    expect(calledUrl).toContain('offset=20')
  })

  it('calls without query string when no params', async () => {
    mockFetch.mockReturnValue(jsonResponse({ threads: [], total: 0 }))
    await api.listThreads()

    const calledUrl = mockFetch.mock.calls[0]![0] as string
    expect(calledUrl).toBe('/api/threads')
  })
})

describe('api.getThread', () => {
  it('fetches thread by id', async () => {
    const thread = { thread_id: 'abc', question: 'Q', status: 'complete', created_at: '', turns: [] }
    mockFetch.mockReturnValue(jsonResponse(thread))

    const result = await api.getThread('abc')
    expect(result).toEqual(thread)
    expect(mockFetch.mock.calls[0]![0]).toBe('/api/threads/abc')
  })

  it('encodes thread id', async () => {
    mockFetch.mockReturnValue(jsonResponse({ thread_id: 'a/b', question: '', status: '', created_at: '', turns: [] }))
    await api.getThread('a/b')
    expect(mockFetch.mock.calls[0]![0]).toBe('/api/threads/a%2Fb')
  })
})

describe('api.recall', () => {
  it('sends query and limit as query params', async () => {
    mockFetch.mockReturnValue(jsonResponse({ results: [], query: 'test' }))
    await api.recall('test', 5)

    const calledUrl = mockFetch.mock.calls[0]![0] as string
    expect(calledUrl).toContain('query=test')
    expect(calledUrl).toContain('limit=5')
  })
})

describe('api.feedback', () => {
  it('sends POST with feedback body', async () => {
    mockFetch.mockReturnValue(jsonResponse({ status: 'ok', thread_id: '1' }))
    await api.feedback({ thread_id: '1', result: 'success', notes: 'Great' })

    expect(mockFetch).toHaveBeenCalledWith('/api/feedback', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ thread_id: '1', result: 'success', notes: 'Great' }),
    }))
  })
})

describe('api.models', () => {
  it('fetches models list', async () => {
    const response = { models: [], total: 0 }
    mockFetch.mockReturnValue(jsonResponse(response))
    const result = await api.models()
    expect(result).toEqual(response)
    expect(mockFetch.mock.calls[0]![0]).toBe('/api/models')
  })
})

describe('api.cost', () => {
  it('fetches cost data', async () => {
    const response = { total_cost: 0.5, total_input_tokens: 1000, total_output_tokens: 500, by_model: [] }
    mockFetch.mockReturnValue(jsonResponse(response))
    const result = await api.cost()
    expect(result).toEqual(response)
    expect(mockFetch.mock.calls[0]![0]).toBe('/api/cost')
  })
})

describe('api.decisionSpace', () => {
  it('builds query string from params', async () => {
    mockFetch.mockReturnValue(jsonResponse({ decisions: [], axes: { categories: [], genera: [] }, total: 0 }))
    await api.decisionSpace({ category: 'tech', confidence_min: 0.5 })

    const calledUrl = mockFetch.mock.calls[0]![0] as string
    expect(calledUrl).toContain('category=tech')
    expect(calledUrl).toContain('confidence_min=0.5')
  })

  it('calls without query string when no params', async () => {
    mockFetch.mockReturnValue(jsonResponse({ decisions: [], axes: { categories: [], genera: [] }, total: 0 }))
    await api.decisionSpace()

    const calledUrl = mockFetch.mock.calls[0]![0] as string
    expect(calledUrl).toBe('/api/decisions/space')
  })
})

describe('api.getShare', () => {
  it('fetches shared thread by token', async () => {
    const thread = { thread_id: 'abc', question: 'Q', status: 'complete', created_at: '', turns: [] }
    mockFetch.mockReturnValue(jsonResponse(thread))
    const result = await api.getShare('tok123')
    expect(result).toEqual(thread)
    expect(mockFetch.mock.calls[0]![0]).toBe('/api/share/tok123')
  })
})

describe('error handling', () => {
  it('throws ApiError with detail from JSON body', async () => {
    mockFetch.mockReturnValue(errorResponse(404, 'Thread not found'))

    await expect(api.getThread('missing')).rejects.toThrow(ApiError)
    try {
      await api.getThread('missing')
    } catch (e) {
      const err = e as ApiError
      expect(err.status).toBe(404)
      expect(err.detail).toBe('Thread not found')
    }
  })

  it('falls back to statusText when no JSON body', async () => {
    mockFetch.mockReturnValue(errorResponse(500))

    await expect(api.health()).rejects.toThrow(ApiError)
    try {
      await api.health()
    } catch (e) {
      const err = e as ApiError
      expect(err.status).toBe(500)
      expect(err.detail).toBe('Error')
    }
  })
})
