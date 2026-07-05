import { Component } from 'react'
import type { ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { hasError: boolean; error?: Error }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen bg-[#fdf6ee] select-none">
          <svg className="w-16 h-16 mb-4 text-gray-300" viewBox="0 0 80 80" fill="none">
            <ellipse cx="40" cy="43" rx="22" ry="28" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
            <circle cx="31" cy="36" r="3" fill="currentColor" opacity="0.4" />
            <circle cx="49" cy="36" r="3" fill="currentColor" opacity="0.4" />
            <path d="M34 50 Q40 44 46 50" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" />
          </svg>
          <p className="text-base font-medium text-gray-400 mb-1">出了点问题</p>
          <p className="text-sm text-gray-400 mb-4">页面渲染出错，试试刷新</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-sm bg-[#f59e6b] text-white rounded-lg hover:brightness-110 transition-all"
          >
            刷新页面
          </button>
          {this.state.error && (
            <details className="mt-4 max-w-md text-xs text-gray-400 text-center">
              <summary className="cursor-pointer hover:text-gray-300">错误详情</summary>
              <pre className="mt-2 p-2 bg-[#1a1a30]/50 rounded overflow-auto">{this.state.error.message}</pre>
            </details>
          )}
        </div>
      )
    }
    return this.props.children
  }
}
