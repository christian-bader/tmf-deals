import { Component, type ReactNode } from 'react'

type Props = { children: ReactNode }
type State = { error: Error | null }

export class PageErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: unknown): State {
    return { error: error instanceof Error ? error : new Error(String(error)) }
  }

  componentDidCatch(error: unknown, info: React.ErrorInfo) {
    console.error('PageErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-left">
          <h3 className="text-sm font-semibold text-red-800">Something went wrong</h3>
          <p className="mt-2 font-mono text-[13px] text-red-700">
            {this.state.error.message}
          </p>
          {this.state.error.stack && (
            <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-red-600">
              {this.state.error.stack}
            </pre>
          )}
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-4 rounded-lg bg-red-600 px-3 py-2 text-[13px] font-medium text-white hover:bg-red-700"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
