import { useState, useEffect, useRef } from 'react'
import type { Conversation } from '../../types'
import { historyApi } from '../../api/client'

interface ConversationPopoverProps {
  activeConversationId: string | null
  currentProjectPath?: string | null
  onSelect: (conv: Conversation) => void
  onNewConversation: (conv: Conversation) => void
  onDeleteConversation?: (id: string) => void
  refreshKey: number
}

export function ConversationPopover({
  activeConversationId,
  currentProjectPath,
  onSelect,
  onNewConversation,
  onDeleteConversation,
  refreshKey,
}: ConversationPopoverProps) {
  const [open, setOpen] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const popoverRef = useRef<HTMLDivElement>(null)

  const loadConversations = () => {
    historyApi.list(currentProjectPath || undefined).then(setConversations).catch(console.error)
  }

  // Load on mount, when refreshKey changes, or when project changes
  useEffect(() => {
    if (refreshKey > 0 || conversations.length === 0 || open) loadConversations()
  }, [refreshKey, currentProjectPath])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open])

  const handleNew = async () => {
    try {
      const conv = await historyApi.create(currentProjectPath || undefined)
      setConversations((prev) => [conv, ...prev])
      onNewConversation(conv)
      setOpen(false)
    } catch (err) {
      console.error('Failed to create conversation:', err)
    }
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    try {
      await historyApi.delete(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      onDeleteConversation?.(id)
    } catch (err) {
      console.error('Failed to delete conversation:', err)
    }
  }

  return (
    <div ref={popoverRef} className="relative">
      {/* History icon button */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${
          open ? 'bg-[#2a2a4a] text-white' : 'text-gray-400 hover:bg-[#1a1a30] hover:text-gray-200'
        }`}
        title="对话历史"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3C7 3 4 6 4 9.5c0 2.5 1 4.5 2.5 6S9.5 18 12 18s3.5-.8 5-2.5 2.5-3.5 2.5-6c0-3.5-2.5-6.5-7.5-6.5z" />
          <circle cx="12" cy="9" r="2.5" fill="currentColor" opacity="0.35" stroke="none" />
          <polyline points="12 8 12 10 13 11" strokeWidth="1.5" />
        </svg>
      </button>

      {/* Popover dropdown */}
      {open && (
        <div
          className="absolute top-full right-0 z-50 w-[280px] mt-1 overflow-hidden"
          style={{
            background: '#1a1a30',
            border: '1px solid #2a2a4a',
            borderRadius: '8px',
          }}
        >
          {/* New Conversation button */}
          <button
            onClick={handleNew}
            className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-gray-300 hover:bg-[#2a2a4a] hover:text-white border-b border-[#2a2a4a] transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            新建对话
          </button>

          {/* Conversation list */}
          <div className="max-h-[260px] overflow-y-auto hide-scrollbar">
            {conversations.length === 0 && (
              <div className="px-3 py-6 text-xs text-gray-500 text-center">
                暂无对话
              </div>
            )}
            {conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => { onSelect(conv); setOpen(false) }}
                className={`group flex items-center justify-between px-3 py-2 cursor-pointer text-sm transition-colors ${
                  activeConversationId === conv.id
                    ? 'bg-[#2a2a5a] text-white'
                    : 'text-gray-400 hover:bg-[#1e1e3a] hover:text-gray-200'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="truncate text-xs">{conv.title}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">
                    {new Date(conv.created_at).toLocaleDateString('zh-CN')}
                  </div>
                </div>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="p-1 rounded text-gray-500 hover:bg-[#3a3a5a] hover:text-red-400 transition-colors shrink-0"
                  title="删除"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
