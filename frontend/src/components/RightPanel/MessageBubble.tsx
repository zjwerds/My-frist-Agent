import { useState, useMemo } from 'react'
import type { Message } from '../../types'
import { filesApi } from '../../api/client'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface MessageBubbleProps {
  message: Message
  isStreaming?: boolean
  onEdit?: (messageId: string, currentContent: string) => void
  onBranch?: (messageId: string) => void
  currentProjectPath?: string | null
}

const FILE_REF_RE = /^\[([📄📝📊📎])\s+(.+?)\]\s*（(.+?)）/

// ── Code Block Toolbar ──
interface CodeBlockToolbarProps {
  code: string
  language: string
  currentProjectPath?: string | null
}

function CodeBlockToolbar({ code, language, currentProjectPath }: CodeBlockToolbarProps) {
  const [copied, setCopied] = useState(false)
  const [saving, setSaving] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSaveFile = async () => {
    if (!currentProjectPath) return
    // Infer extension from language, default .txt
    const extMap: Record<string, string> = {
      python: '.py', javascript: '.js', typescript: '.ts', jsx: '.jsx', tsx: '.tsx',
      html: '.html', css: '.css', json: '.json', markdown: '.md', md: '.md',
      yaml: '.yml', toml: '.toml', ini: '.ini', sql: '.sql', bash: '.sh', sh: '.sh',
      shell: '.sh', powershell: '.ps1', rust: '.rs', go: '.go', java: '.java',
      c: '.c', 'c++': '.cpp', 'c#': '.cs', ruby: '.rb', php: '.php',
      xml: '.xml', csv: '.csv', txt: '.txt',
    }
    const ext = extMap[language] || '.txt'
    // Generate a unique filename
    const timestamp = Date.now().toString(36)
    const filename = `code_${timestamp}${ext}`

    setSaving(true)
    try {
      await filesApi.createFile(filename, code, currentProjectPath)
      setSaving(false)
    } catch {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center justify-between px-4 py-1.5 glass-sm border-b border-white/10 rounded-t-2xl">
      <span className="text-[10px] text-gray-500 uppercase">{language}</span>
      <div className="flex items-center gap-1">
        {currentProjectPath && (
          <button
            onClick={handleSaveFile}
            disabled={saving}
            className="flex items-center gap-1 px-2 py-0.5 text-[10px] text-gray-400 hover:text-white bg-white/10 hover:bg-white/20 rounded-2xl transition-colors disabled:opacity-50"
            title="保存到项目文件夹"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z" />
              <polyline points="17 21 17 13 7 13 7 21" />
              <polyline points="7 3 7 8 15 8" />
            </svg>
            {saving ? '保存中...' : '保存为文件'}
          </button>
        )}
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 text-[10px] text-gray-400 hover:text-white bg-white/10 hover:bg-white/20 rounded-2xl transition-colors"
          title="复制代码"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <rect x="9" y="9" width="13" height="13" rx="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" />
          </svg>
          {copied ? '已复制' : '复制'}
        </button>
      </div>
    </div>
  )
}

// ── Parse message content into segments: text | code block ──
interface CodeSegment {
  type: 'code'
  language: string
  code: string
}

interface TextSegment {
  type: 'text'
  html: string
}

type Segment = TextSegment | CodeSegment

function parseSegments(text: string): Segment[] {
  const segments: Segment[] = []
  const codeBlockRe = /```(\w*)\n([\s\S]*?)```/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = codeBlockRe.exec(text)) !== null) {
    // Text before this code block
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index)
      segments.push({ type: 'text', html: renderMarkdownToHtml(before) })
    }
    // Code block
    segments.push({
      type: 'code',
      language: match[1] || 'txt',
      code: match[2],
    })
    lastIndex = match.index + match[0].length
  }

  // Remaining text
  if (lastIndex < text.length) {
    segments.push({ type: 'text', html: renderMarkdownToHtml(text.slice(lastIndex)) })
  }

  return segments
}

// ── Render markdown text to HTML (same logic as before, extracted) ──
function renderMarkdownToHtml(text: string): string {
  let h = (text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Inline code (must be before other inline formatting)
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Bold
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // Italic
  h = h.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  // Line breaks → paragraphs
  const paragraphs = h.split(/\n\n+/)
  h = paragraphs.map(p => {
    p = p.trim()
    if (!p) return ''
    if (p.startsWith('- ') || p.startsWith('* ')) {
      const items = p.split(/\n/).map(line => {
        const li = line.replace(/^[-*]\s+/, '').trim()
        return li ? `<li>${li}</li>` : ''
      }).filter(Boolean).join('')
      return `<ul>${items}</ul>`
    }
    p = p.replace(/\n(?!\n)/g, '<br>')
    return `<p>${p}</p>`
  }).filter(Boolean).join('')
  return h
}

// ── Markdown content renderer (text-only segments) ──
function MarkdownSegment({ html }: { html: string }) {
  return <span dangerouslySetInnerHTML={{ __html: html }} />
}

// ── Tool call bubble ──
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

// ── File reference badge ──
function FileRefBadge({ match }: { match: RegExpMatchArray }) {
  return (
    <div className="flex items-center gap-1.5 text-xs mb-2 px-2.5 py-1.5 rounded-2xl bg-white/10 border border-white/10">
      <span>{match[1]}</span>
      <span className="font-medium truncate max-w-[180px] text-gray-200">{match[2]}</span>
      <span className="text-gray-500">{match[3]}</span>
    </div>
  )
}

// ── Main MessageBubble ──
export function MessageBubble({ message, isStreaming, onEdit, onBranch, currentProjectPath }: MessageBubbleProps) {
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const isUser = message.role === 'user'
  const isTool = message.role === 'tool'
  const hasImages = isUser && message.images && message.images.length > 0

  const segments = useMemo(
    () => !isUser && !isTool ? parseSegments(message.content) : [],
    [isUser, isTool, message.content]
  )

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
              className="w-full bg-white/20 backdrop-blur-[40px] border border-white/20 rounded-2xl px-2 py-1.5 text-sm text-[#0d0d1a] outline-none focus:border-white/40 resize-none"
            />
            <div className="flex gap-2 mt-2 justify-end">
              <button
                onClick={handleCancelEdit}
                className="px-2.5 py-1 text-xs rounded-2xl bg-white/10 text-gray-400 hover:bg-white/20 transition-colors"
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
            ) : segments.length > 0 ? (
              <div className="space-y-3">
                {segments.map((seg, i) =>
                  seg.type === 'code' ? (
                    <div key={i} className="my-1.5 rounded-2xl overflow-hidden border border-white/10">
                      <CodeBlockToolbar
                        code={seg.code}
                        language={seg.language}
                        currentProjectPath={currentProjectPath}
                      />
                      <SyntaxHighlighter
                        language={seg.language || 'text'}
                        style={oneDark}
                        customStyle={{
                          margin: 0,
                          padding: '12px 16px',
                          fontSize: '12px',
                          lineHeight: '1.6',
                          background: '#0d0d1a',
                          borderRadius: 0,
                        }}
                        codeTagProps={{ style: { fontFamily: 'inherit' } }}
                        showLineNumbers={seg.code.split('\n').length > 5}
                      >
                        {seg.code}
                      </SyntaxHighlighter>
                    </div>
                  ) : (
                    <MarkdownSegment key={i} html={seg.html} />
                  )
                )}
              </div>
            ) : (
              <MarkdownSegment html={renderMarkdownToHtml(message.content)} />
            )}
            {isStreaming && <span className="inline-block w-0.5 h-4 bg-[#4fc3f7] ml-0.5 animate-pulse align-text-bottom" />}
          </div>
        )}
      </div>

      {/* Action buttons — visible on hover when not streaming */}
      {!isStreaming && !editing && (
        <div className={`flex items-start gap-1 pt-2 px-1 opacity-0 group-hover:opacity-100 transition-opacity ${isUser ? 'order-first' : ''}`}>
          {isUser && !hasImages && onEdit && (
            <button
              onClick={handleStartEdit}
              className="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-gray-300 hover:bg-white/10 transition-colors"
              title="编辑消息"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
              </svg>
            </button>
          )}
          {onBranch && (
            <button
              onClick={() => onBranch(message.id)}
              className="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-gray-300 hover:bg-white/10 transition-colors"
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
