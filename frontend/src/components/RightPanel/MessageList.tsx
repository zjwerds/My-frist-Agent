import { useRef, useEffect } from 'react'
import type { Message } from '../../types'
import { MessageBubble } from './MessageBubble'

interface MessageListProps {
  messages: Message[]
  streamingContent: string
  isLoading: boolean
  toolStatus: string | null
  onEdit?: (messageId: string, currentContent: string) => void
  onBranch?: (messageId: string) => void
  currentProjectPath?: string | null
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full select-none">
      <svg className="w-20 h-20 mb-4 text-gray-600/50" viewBox="0 0 80 80" fill="none">
        {/* Egg body */}
        <ellipse cx="40" cy="43" rx="22" ry="28" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
        {/* Egg white highlight */}
        <ellipse cx="40" cy="43" rx="22" ry="28" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
        {/* Eyes */}
        <circle cx="31" cy="36" r="3" fill="currentColor" opacity="0.6" />
        <circle cx="49" cy="36" r="3" fill="currentColor" opacity="0.6" />
        {/* Smile */}
        <path d="M34 47 Q40 53 46 47" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        {/* Blush */}
        <circle cx="26" cy="43" r="4.5" fill="currentColor" opacity="0.12" />
        <circle cx="54" cy="43" r="4.5" fill="currentColor" opacity="0.12" />
      </svg>
      <p className="text-base font-medium text-gray-500 mb-1">煎蛋Agent</p>
      <p className="text-sm text-gray-600">选择一个对话或开始新对话</p>
    </div>
  )
}

export function MessageList({ messages, streamingContent, isLoading, toolStatus, onEdit, onBranch, currentProjectPath }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streamingContent ? 'auto' : 'smooth' })
  }, [messages, streamingContent, toolStatus])

  return (
    <div className="h-full overflow-y-auto hide-scrollbar px-4 py-4 space-y-4">
      {messages.length === 0 && !isLoading && !streamingContent && (
        <EmptyState />
      )}

      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onEdit={onEdit} onBranch={onBranch} currentProjectPath={currentProjectPath} />
      ))}

      {/* Streaming message */}
      {streamingContent && (
        <MessageBubble
          message={{
            id: 'streaming',
            role: 'assistant',
            content: streamingContent,
            created_at: '',
          }}
          isStreaming
          currentProjectPath={currentProjectPath}
        />
      )}

      {/* Loading indicator */}
      {isLoading && !streamingContent && (
        <div className="flex items-center gap-2 text-gray-400 text-sm pl-4">
          <div className="flex gap-1.5">
            <span className="w-1.5 h-1.5 bg-[#4fc3f7] rounded-full animate-bounce" style={{ animationDelay: '0ms', animationDuration: '0.8s' }} />
            <span className="w-1.5 h-1.5 bg-[#4fc3f7] rounded-full animate-bounce" style={{ animationDelay: '200ms', animationDuration: '0.8s' }} />
            <span className="w-1.5 h-1.5 bg-[#4fc3f7] rounded-full animate-bounce" style={{ animationDelay: '400ms', animationDuration: '0.8s' }} />
          </div>
        </div>
      )}

      {/* Tool status */}
      {toolStatus && (
        <div className="flex items-center gap-2 text-xs text-gray-500 pl-4 py-1">
          <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
            <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" opacity="0.6" />
          </svg>
          <span>{toolStatus}</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
