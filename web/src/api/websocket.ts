import type { ModelSelectionOptions, WSEvent } from './types'

export type WSStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'closed'

export interface ConsensusWSOptions {
  question: string
  rounds?: number
  protocol?: string
  modelSelection?: ModelSelectionOptions
  onEvent: (event: WSEvent) => void
  onStatusChange?: (status: WSStatus) => void
  onError?: (error: Event | string) => void
}

export class ConsensusWebSocket {
  private ws: WebSocket | null = null
  private status: WSStatus = 'idle'

  connect(options: ConsensusWSOptions): void {
    this.close()

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/ask`

    this.setStatus('connecting', options.onStatusChange)

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.setStatus('connected', options.onStatusChange)
      const payload: Record<string, unknown> = {
        question: options.question,
        rounds: options.rounds ?? 3,
        protocol: options.protocol ?? 'consensus',
      }
      if (options.modelSelection?.panel?.length) {
        payload.panel = options.modelSelection.panel
      }
      if (options.modelSelection?.proposer) {
        payload.proposer = options.modelSelection.proposer
      }
      if (options.modelSelection?.challengers?.length) {
        payload.challengers = options.modelSelection.challengers
      }
      this.ws!.send(JSON.stringify(payload))
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSEvent
        options.onEvent(data)
      } catch {
        console.error('[duh] Failed to parse WS message:', event.data)
      }
    }

    this.ws.onerror = (event) => {
      this.setStatus('error', options.onStatusChange)
      options.onError?.(event)
    }

    this.ws.onclose = () => {
      this.setStatus('closed', options.onStatusChange)
      this.ws = null
    }
  }

  close(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
      this.status = 'idle'
    }
  }

  getStatus(): WSStatus {
    return this.status
  }

  private setStatus(status: WSStatus, callback?: (s: WSStatus) => void): void {
    this.status = status
    callback?.(status)
  }
}
