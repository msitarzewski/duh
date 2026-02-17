import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ConsensusWebSocket } from '@/api/websocket'
import type { ConsensusWSOptions } from '@/api/websocket'

// Unmock the websocket module so we test the real implementation
vi.unmock('@/api/websocket')

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  url: string
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  readyState = MockWebSocket.CONNECTING
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new Event('close') as CloseEvent)
  })
  send = vi.fn()

  constructor(url: string) {
    this.url = url
    // Store instance for test access
    MockWebSocket.lastInstance = this
  }

  static lastInstance: MockWebSocket | null = null

  // Helper to simulate server events
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  simulateMessage(data: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }))
  }

  simulateError() {
    this.onerror?.(new Event('error'))
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.(new Event('close') as CloseEvent)
  }
}

beforeEach(() => {
  MockWebSocket.lastInstance = null
  vi.stubGlobal('WebSocket', MockWebSocket)
  // Mock window.location for URL construction
  Object.defineProperty(globalThis, 'window', {
    value: {
      location: {
        protocol: 'http:',
        host: 'localhost:3000',
      },
    },
    writable: true,
    configurable: true,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function createOptions(overrides: Partial<ConsensusWSOptions> = {}): ConsensusWSOptions {
  return {
    question: 'Test question',
    rounds: 3,
    protocol: 'consensus',
    onEvent: vi.fn(),
    onStatusChange: vi.fn(),
    onError: vi.fn(),
    ...overrides,
  }
}

describe('ConsensusWebSocket', () => {
  it('creates a WebSocket connection with correct URL', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    expect(instance.url).toBe('ws://localhost:3000/ws/ask')
  })

  it('uses wss: protocol for https pages', () => {
    Object.defineProperty(globalThis, 'window', {
      value: {
        location: {
          protocol: 'https:',
          host: 'example.com',
        },
      },
      writable: true,
      configurable: true,
    })

    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    expect(instance.url).toBe('wss://example.com/ws/ask')
  })

  it('sets status to connecting on connect', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    expect(options.onStatusChange).toHaveBeenCalledWith('connecting')
    expect(ws.getStatus()).toBe('connecting')
  })

  it('sets status to connected and sends config on open', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    instance.simulateOpen()

    expect(options.onStatusChange).toHaveBeenCalledWith('connected')
    expect(ws.getStatus()).toBe('connected')
    expect(instance.send).toHaveBeenCalledWith(JSON.stringify({
      question: 'Test question',
      rounds: 3,
      protocol: 'consensus',
    }))
  })

  it('uses default rounds and protocol in sent config', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions({ rounds: undefined, protocol: undefined })
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    instance.simulateOpen()

    expect(instance.send).toHaveBeenCalledWith(JSON.stringify({
      question: 'Test question',
      rounds: 3,
      protocol: 'consensus',
    }))
  })

  it('parses incoming messages and calls onEvent', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    instance.simulateOpen()

    const event = { type: 'phase_start', phase: 'PROPOSE', model: 'gpt-4', round: 1 }
    instance.simulateMessage(event)

    expect(options.onEvent).toHaveBeenCalledWith(event)
  })

  it('handles JSON parse errors gracefully', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    instance.simulateOpen()

    // Send invalid JSON
    instance.onmessage?.(new MessageEvent('message', { data: 'not json{' }))

    expect(options.onEvent).not.toHaveBeenCalled()
    expect(consoleSpy).toHaveBeenCalled()
    consoleSpy.mockRestore()
  })

  it('sets error status and calls onError on WebSocket error', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    instance.simulateError()

    expect(options.onStatusChange).toHaveBeenCalledWith('error')
    expect(options.onError).toHaveBeenCalled()
    expect(ws.getStatus()).toBe('error')
  })

  it('sets closed status on WebSocket close', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    instance.simulateOpen()
    instance.simulateClose()

    expect(options.onStatusChange).toHaveBeenCalledWith('closed')
    expect(ws.getStatus()).toBe('closed')
  })

  it('close() closes existing connection', () => {
    const ws = new ConsensusWebSocket()
    const options = createOptions()
    ws.connect(options)

    const instance = MockWebSocket.lastInstance!
    ws.close()

    expect(instance.close).toHaveBeenCalled()
    expect(ws.getStatus()).toBe('idle')
  })

  it('close() is safe to call when no connection', () => {
    const ws = new ConsensusWebSocket()
    expect(() => ws.close()).not.toThrow()
    expect(ws.getStatus()).toBe('idle')
  })

  it('closes previous connection when connect is called again', () => {
    const ws = new ConsensusWebSocket()
    const options1 = createOptions()
    ws.connect(options1)

    const firstInstance = MockWebSocket.lastInstance!

    const options2 = createOptions({ question: 'New question' })
    ws.connect(options2)

    expect(firstInstance.close).toHaveBeenCalled()
  })

  it('getStatus returns idle initially', () => {
    const ws = new ConsensusWebSocket()
    expect(ws.getStatus()).toBe('idle')
  })
})
