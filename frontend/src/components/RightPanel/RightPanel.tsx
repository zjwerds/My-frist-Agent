import { useState, useEffect, useRef } from 'react'
import type { RightView } from '../../types'
import { ChatView } from './ChatView'
import { ApiConfigView } from './ApiConfigView'

interface RightPanelProps {
  view: RightView
  conversationId: string | null
  onBackToChat: () => void
  onMessageComplete: () => void
  onUsage?: (usage: { prompt_tokens: number; completion_tokens: number; cache_hit_tokens: number }) => void
  onNewConversation?: () => Promise<import('../../types').Conversation>
  temperature: number
  onSwitchConversation?: (conv: import('../../types').Conversation & { messages: import('../../types').Message[] }) => void
  currentProjectPath?: string | null
}

export function RightPanel({ view, conversationId, onBackToChat, onMessageComplete, onUsage, onNewConversation, temperature, onSwitchConversation, currentProjectPath }: RightPanelProps) {
  const [mountedView, setMountedView] = useState<RightView>(view)
  const [animating, setAnimating] = useState(false)
  const prevView = useRef<RightView>(view)

  useEffect(() => {
    if (prevView.current !== view) {
      setAnimating(true)
      const timer = setTimeout(() => {
        setMountedView(view)
        prevView.current = view
        requestAnimationFrame(() => setAnimating(false))
      }, 120)
      return () => clearTimeout(timer)
    }
    prevView.current = view
    setMountedView(view)
  }, [view])

  const fadeStyle: React.CSSProperties = animating
    ? { opacity: 0, transform: 'translateY(4px)', transition: 'opacity 0.12s ease, transform 0.12s ease' }
    : { opacity: 1, transform: 'translateY(0)', transition: 'opacity 0.2s ease, transform 0.2s ease' }

  return (
    <div className="flex-1 flex flex-col h-full glass overflow-hidden" style={fadeStyle}>
      <div style={{ display: mountedView === 'chat' ? '' : 'none', height: '100%' }}>
        <ChatView conversationId={conversationId} onMessageComplete={onMessageComplete} onUsage={onUsage} onNewConversation={onNewConversation} temperature={temperature} onSwitchConversation={onSwitchConversation} currentProjectPath={currentProjectPath} />
      </div>
      {mountedView === 'api-config' && <ApiConfigView onBackToChat={onBackToChat} onSaved={onMessageComplete} />}
    </div>
  )
}
