import { useState, useMemo } from 'react'
import type { Message } from '../../types'

interface MessageBubbleProps {
  message: Message
  isStreaming?: boolean
  onEdit?: (messageId: string, currentContent: string) => void
  onBranch?: (messageId: string) => void
}

const FILE_REF_RE = /^\[([📄📝📊📎])\s+(.+?)\]\s*（(.+?)）/

// Lightweight Markdown renderer — handles common patterns without external deps
function MarkdownContent({ text }: { text: string }) {
  const html = useMemo(() => {
    // Escape HTML special chars first (but preserve intentional markdown)
    let h = (text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    // Code blocks (```...```)
    h = h.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold (**text**)
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // Italic (*text*)
    h = h.replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // Line breaks: double newline → paragraph
    const paragraphs = h.split(/\n\n+/)
    h = paragraphs.map(p => {
      p = p.trim()
      if (!p) return ''
      // Unordered list items
      if (p.startsWith('- ') || p.startsWith('* ')) {
        const items = p.split(/\n/).map(line => {
          const li = line.replace(/^[-*]\s+/, '').trim()
          return li ? `<li>${li}</li>` : ''
        }).filter(Boolean).join('')
        return `<ul>${items}</ul>`
      }
      // Single newline within paragraph → <br>
      p = p.replace(/\n(?!\n)/g, '<br>')
      return `<p>${p}</p>`
    }).filter(Boolean).join('')
    return h
  }, [text])

  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

function ToolCallBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-start pl-4">
      <div className="max-w-[80%] glass-card px-3 py-2.5">
        <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mb-1.5">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <path d="M9 8l6 4-6 4V8z" />
          </svg>
          工具调用结果
        </div>
        <pre className="text-xs text-gray-400 whitespace-pre-wrap font-mono leading-relaxed">
          {content}
        </pre>
      </div>
    </div>
  )
}

function FileRefBadge({ match }: { match: RegExpMatchArray }) {
  return (
    <div className="flex items-center gap-1.5 text-xs mb-2 px-2.5 py-1.5 rounded-lg bg-black/10 border border-white/10">
      <span>{match[1]}</span>
      <span className="font-medium truncate max-w-[180px] text-gray-200">{match[2]}</span>
      <span className="text-gray-500">{match[3]}</span>
    </div>
  )
}

export function MessageBubble({ message, isStreaming, onEdit, onBranch }: MessageBubbleProps) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'
  const hasImages = isUser && message.images && message.images.length > 0

  if (isTool) {
    return <ToolCallBubble content={message.content} />
  }

  const fileRefMatch = isUser && message.content.match(FILE_REF_RE)

  const handleStartEdit = () => {
    setEditText(message.content)
    setEditing(true)
  }

  const handleCancelEdit = () => {
    setEditing(false)
    setEditText('')
  }

  const handleSaveEdit = () => {
    if (editText.trim() && editText !== message.content) {
      onEdit?.(message.id, editText)
    }
    setEditing(false)
  }

  return (
    <div className={`group flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
          isUser
            ? 'bg-accent text-[#0d0d1a] rounded-br-md'
            : 'glass-sm text-black rounded-bl-md'
        }`}
      >
        {!isUser && isStreaming && (
          <div className="flex items-center gap-1 text-[10px] text-gray-400 mb-1 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-[#4fc3f7]" />
            思考中
          </div>
        )}

        {isUser && hasImages && (
          <div className="flex flex-wrap gap-2 mb-2">
            {message.images!.map((img, i) => (
              <img
                key={i}
                src={img}
                alt={`上传图片 ${i + 1}`}
                className="w-24 h-24 object-cover rounded-lg border border-white/20"
              />
            ))}
          </div>
        )}

        {fileRefMatch && <FileRefBadge match={fileRefMatch} />}

        {editing ? (
          <div>
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={3}
              className="w-full bg-[#0d0d1a]/30 border border-[#2a2a4a] rounded px-2 py-1.5 text-sm text-[#0d0d1a] outline-none focus:border-[#4a4a7a] resize-none"
            />
            <div className="flex gap-2 mt-2 justify-end">
              <button
                onClick={handleCancelEdit}
                className="px-2.5 py-1 text-xs rounded bg-[#2a2a4a]/50 text-gray-400 hover:bg-[#3a3a5a] transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-2.5 py-1 text-xs rounded text-white transition-colors disabled:opacity-40"
                style={{ backgroundColor: 'var(--accent)' }}
                disabled={!editText.trim()}
              >
                保存并重新生成
              </button>
            </div>
          </div>
        ) : (
          <div className="text-sm leading-relaxed break-words">
            {isUser ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : (
              <MarkdownContent text={message.content} />
            )}
            {isStreaming && <span className="inline-block w-0.5 h-4 bg-[#4fc3f7] ml-0.5 animate-pulse align-text-bottom" />}
          </div>
        )}
      </div>

      {/* Action buttons — visible on hover when not streaming */}
      {!isStreaming && !editing && (
        <div className={`flex items-start gap-1 pt-2 px-1 opacity-0 group-hover:opacity-100 transition-opacity ${isUser ? 'order-first' : ''}`}>
          {/* Edit button — user messages only, hide if has images */}
          {isUser && !hasImages && onEdit && (
            <button
              onClick={handleStartEdit}
              className="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-gray-300 hover:bg-[#1e1e3a] transition-colors"
              title="编辑消息"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
              </svg>
            </button>
          )}
          {/* Branch button — all messages */}
          {onBranch && (
            <button
              onClick={() => onBranch(message.id)}
              className="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-gray-300 hover:bg-[#1e1e3a] transition-colors"
              title="从此处创建分支"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="6" y1="3" x2="6" y2="15" />
                <circle cx="18" cy="6" r="3" />
                <circle cx="6" cy="18" r="3" />
                <path d="M18 9a9 9 0 0 1-9 9" />
              </svg>
            </button>
          )}
        </div>
      )}
    </div>
  )
}
