import { useState, useRef, useEffect, useCallback } from 'react'
import { uploadAndParseFile } from '../../api/client'

interface FileAttachment {
  file: File
  name: string
  size: number
  status: 'pending' | 'uploading' | 'done' | 'error'
  text?: string
  error?: string
}

interface ChatInputProps {
  onSend: (text: string, images?: string[]) => void
  isLoading: boolean
  disabled?: boolean
  onCancel?: () => void
}

const MAX_IMAGES = 5
const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const MAX_FILE_SIZE = 50 * 1024 * 1024
const FILE_SIZE_LIMITS: Record<string, number> = {
  pdf: 50 * 1024 * 1024,
  docx: 20 * 1024 * 1024,
  doc: 20 * 1024 * 1024,
  xlsx: 20 * 1024 * 1024,
  xls: 20 * 1024 * 1024,
}

const DOCUMENT_TYPES = new Set(['pdf', 'docx', 'doc', 'xlsx', 'xls'])
const ALLOWED_EXTENSIONS = 'image/*,.pdf,.docx,.doc,.xlsx,.xls'

function getFileExt(name: string): string {
  const i = name.lastIndexOf('.')
  return i > 0 ? name.slice(i + 1).toLowerCase() : ''
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function FileTypeIcon({ ext }: { ext: string }) {
  const color = ext === 'pdf' ? '#ef4444' : ext.startsWith('doc') ? '#3b82f6' : ext.startsWith('xls') ? '#22c55e' : '#a0a0b0'
  return (
    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" />
      <polyline points="14 2 14 8 20 8" stroke="currentColor" />
      <line x1="9" y1="13" x2="15" y2="13" stroke="currentColor" />
      <line x1="12" y1="10" x2="12" y2="16" stroke="currentColor" />
    </svg>
  )
}

export function ChatInput({ onSend, isLoading, disabled, onCancel }: ChatInputProps) {
  const [text, setText] = useState('')
  const [images, setImages] = useState<string[]>([])
  const [attachments, setAttachments] = useState<FileAttachment[]>([])
  const [dragOver, setDragOver] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Message history for ↑/↓ navigation ────────────────────────────
  const [messageHistory, setMessageHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)  // -1 = new message
  const savedTextRef = useRef('')

  // Track the current value for history navigation
  const textRef = useRef(text)
  textRef.current = text

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isLoading])

  const addImage = useCallback((file: File) => {
    if (!file.type.startsWith('image/')) return false
    if (file.size > MAX_IMAGE_SIZE) {
      alert('单张图片不能超过 10MB')
      return true
    }
    const reader = new FileReader()
    reader.onload = (e) => {
      const result = e.target?.result as string
      if (result) {
        setImages((prev) => {
          if (prev.length >= MAX_IMAGES) {
            alert(`最多上传 ${MAX_IMAGES} 张图片`)
            return prev
          }
          return [...prev, result]
        })
      }
    }
    reader.readAsDataURL(file)
    return true
  }, [])

  const removeImage = useCallback((index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const addAttachment = useCallback((file: File) => {
    const ext = getFileExt(file.name)
    if (!DOCUMENT_TYPES.has(ext)) return false
    const maxSize = FILE_SIZE_LIMITS[ext] || MAX_FILE_SIZE
    if (file.size > maxSize) {
      alert(`${ext.toUpperCase()} 文件不能超过 ${Math.floor(maxSize / 1024 / 1024)}MB`)
      return true
    }
    setAttachments((prev) => [...prev, { file, name: file.name, size: file.size, status: 'pending' }])
    return true
  }, [])

  const removeAttachment = useCallback((index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const handleFiles = useCallback((files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      const ext = getFileExt(file.name)
      if (file.type.startsWith('image/')) {
        addImage(file)
      } else if (DOCUMENT_TYPES.has(ext)) {
        addAttachment(file)
      }
    }
  }, [addImage, addAttachment])

  const handleSubmit = async () => {
    if ((!text.trim() && images.length === 0 && attachments.length === 0) || isLoading || disabled) return

    let finalText = text.trim()

    const pending = attachments.filter((a) => a.status === 'pending')
    if (pending.length > 0) {
      const fileBlocks: string[] = []

      setAttachments((prev) => prev.map((a) => (a.status === 'pending' ? { ...a, status: 'uploading' as const } : a)))

      for (const att of pending) {
        try {
          const result = await uploadAndParseFile(att.file)
          setAttachments((prev) =>
            prev.map((a) => (a.file === att.file ? { ...a, status: 'done' as const, text: result.text } : a)),
          )

          const meta = result.pages
            ? `（共 ${result.pages} 页，${result.size} 字）`
            : result.rows
              ? `（${result.sheets} 个 Sheet，${result.rows} 行，${result.size} 字）`
              : result.paragraphs
                ? `（${result.paragraphs} 段，${result.size} 字）`
                : `（${result.size} 字）`
          const header = `[${getFileExt(att.name).toUpperCase()} ${att.name}] ${meta}`
          fileBlocks.push(`${header}\n${'─'.repeat(32)}\n${result.text}`)
          if (result.warning) {
            fileBlocks.push(`> ${result.warning}`)
          }
        } catch (err: any) {
          setAttachments((prev) =>
            prev.map((a) => (a.file === att.file ? { ...a, status: 'error' as const, error: err.message || '解析失败' } : a)),
          )
        }
      }

      if (fileBlocks.length > 0) {
        finalText = fileBlocks.join('\n\n') + (finalText ? '\n\n' + finalText : '')
      }
    }

    onSend(finalText, images)
    setText('')
    setImages([])
    setAttachments([])
    // Save to message history for ↑ navigation (avoid duplicates)
    setMessageHistory(prev => prev[prev.length - 1] === finalText ? prev : [...prev, finalText])
    setHistoryIndex(-1)
    savedTextRef.current = ''
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
      return
    }

    // ↑/↓ navigate message history
    if (e.key === 'ArrowUp' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      if (messageHistory.length === 0) return
      const newIndex = historyIndex === -1
        ? messageHistory.length - 1
        : Math.max(0, historyIndex - 1)
      if (historyIndex === -1) {
        savedTextRef.current = textRef.current
      }
      setHistoryIndex(newIndex)
      setText(messageHistory[newIndex])
      return
    }
    if (e.key === 'ArrowDown' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault()
      if (historyIndex === -1) return  // already at the bottom
      const newIndex = historyIndex + 1
      if (newIndex >= messageHistory.length) {
        setHistoryIndex(-1)
        setText(savedTextRef.current)
        savedTextRef.current = ''
      } else {
        setHistoryIndex(newIndex)
        setText(messageHistory[newIndex])
      }
      return
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }
  const handleDragLeave = () => {
    setDragOver(false)
  }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = Array.from(e.clipboardData.items)
    const imageItems = items.filter((item) => item.type.startsWith('image/'))
    for (const item of imageItems) {
      const file = item.getAsFile()
      if (file) addImage(file)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    handleFiles(files)
    e.target.value = ''
  }

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 120) + 'px'
    }
  }, [text])

  return (
    <div
      className={`px-4 py-3 transition-all duration-200 ${
        dragOver ? 'ring-2 ring-[#4fc3f7] bg-accent-dim rounded-lg mx-2 mb-2' : ''
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="max-w-4xl mx-auto">
        {/* Image previews */}
        {images.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3 px-1">
            {images.map((img, i) => (
              <div key={i} className="relative group">
                <img
                  src={img}
                  alt={`图片 ${i + 1}`}
                  className="w-16 h-16 object-cover rounded-lg border border-white/10"
                />
                <button
                  type="button"
                  onClick={() => removeImage(i)}
                  className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 rounded-full text-white text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all hover:bg-red-600 shadow-lg"
                >
                  <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                    <line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* File attachment chips */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-3 px-1">
            {attachments.map((att, i) => (
              <div
                key={i}
                className={`flex items-center gap-1.5 text-xs rounded-lg px-2.5 py-1.5 border transition-colors ${
                  att.status === 'error'
                    ? 'bg-red-500/10 border-red-500/20 text-red-400'
                    : att.status === 'done'
                      ? 'bg-green-500/10 border-green-500/20 text-gray-300'
                      : 'bg-white/5 border-white/10 text-gray-400'
                }`}
              >
                <FileTypeIcon ext={getFileExt(att.name)} />
                <span className="max-w-[120px] truncate">{att.name}</span>
                <span className="text-[10px] opacity-50">{formatSize(att.size)}</span>
                {att.status === 'uploading' && (
                  <svg className="w-3 h-3 animate-spin text-[#4fc3f7]" fill="none" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
                    <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" opacity="0.6" />
                  </svg>
                )}
                {att.status === 'done' && (
                  <svg className="w-3 h-3 text-green-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
                {att.status === 'error' && (
                  <svg className="w-3 h-3 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                )}
                <button
                  type="button"
                  onClick={() => removeAttachment(i)}
                  className="ml-0.5 text-gray-500 hover:text-red-400 transition-colors"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Input row */}
        <div className="flex items-end gap-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isLoading || disabled}
            className="p-2 text-gray-400 hover:text-gray-200 disabled:opacity-30 transition-colors rounded-lg hover:bg-white/5"
            title="上传图片或文件"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_EXTENSIONS}
            multiple
            className="hidden"
            onChange={handleFileSelect}
          />

          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={disabled ? '请先新建对话' : '输入消息，粘贴图片或文件... (Enter 发送, Shift+Enter 换行)'}
            disabled={isLoading || disabled}
            rows={1}
            className="flex-1 bg-white/70 backdrop-blur-sm text-black rounded-xl px-4 py-2.5 text-sm placeholder-gray-400 resize-none outline-none focus:ring-1 focus:ring-[#4fc3f7] disabled:opacity-50 transition-all border border-white/20 focus:border-[#4fc3f7]/50 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          />
          <button
            onClick={isLoading && onCancel ? onCancel : handleSubmit}
            disabled={(!isLoading && !text.trim() && images.length === 0 && attachments.length === 0) || (isLoading ? false : disabled)}
            className="px-4 py-2.5 bg-accent text-[#0d0d1a] rounded-xl text-sm font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-all hover:brightness-110 active:scale-95 flex items-center gap-1"
          >
            {isLoading ? (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19V5m0 0l-7 7m7-7l7 7" />
              </svg>
            )}
          </button>
        </div>

        {/* Hint text */}
        {(images.length > 0 || attachments.length > 0) && (
          <div className="mt-1.5 text-[10px] text-gray-500 px-1 flex gap-3">
            {images.length > 0 && <span>{images.length}/{MAX_IMAGES} 张图片</span>}
            {attachments.length > 0 && (
              <span>
                {attachments.length} 个文件
                {attachments.some(a => a.status === 'pending') && ' (点击发送自动解析)'}
                {attachments.some(a => a.status === 'error') && ' (有文件解析失败)'}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
