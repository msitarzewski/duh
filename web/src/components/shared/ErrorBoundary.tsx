import { Component, type ErrorInfo, type ReactNode } from 'react'
import { GlassPanel } from './GlassPanel'
import { GlowButton } from './GlowButton'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[duh] Component error:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <GlassPanel className="m-4" glow="subtle">
          <div className="flex flex-col items-center gap-4 py-8">
            <div className="text-[var(--color-red)] font-mono text-sm">
              SYSTEM ERROR
            </div>
            <p className="text-[var(--color-text-secondary)] text-sm max-w-md text-center">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <GlowButton
              variant="ghost"
              size="sm"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Retry
            </GlowButton>
          </div>
        </GlassPanel>
      )
    }

    return this.props.children
  }
}
