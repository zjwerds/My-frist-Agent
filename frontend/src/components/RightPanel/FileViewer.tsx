import { useState, useEffect, useRef, useCallback } from 'react'
import { filesApi } from '../../api/client'
import type { FileContent } from '../../types'

interface FileViewerProps {
  filePath: string | null
  onClose: () => void
  currentProjectPath?: string | null
}

const MIN_WIDTH = 220
const MAX_WIDTH_RATIO = 0.6
const CLOSE_THRESHOLD = 120
const DEFAULT_WIDTH = 420

export function FileViewer({ filePath, onClose, currentProjectPath }: FileViewerProps) {
  const [data, setData] = useState<FileContent | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const isDragging = useRef(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const mouseMoveHandler = useRef<((ev: MouseEvent) => void) | null>(null)
  const mouseUpHandler = useRef<((ev: MouseEvent) => void) | null>(null)

  // Fetch file content when path changes
  useEffect(() => {
    if (!filePath) return
    setLoading(true)
    setError('')
    setData(null)
    filesApi.readFile(filePath, currentProjectPath || undefined)
      .then(setData)
      .catch((err) => setError(err.message || '读取失败'))
      .finally(() => setLoading(false))
  }, [filePath])

  const cleanupDrag = useCallback(() => {
    isDragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    if (mouseMoveHandler.current) {
      document.removeEventListener('mousemove', mouseMoveHandler.current)
      mouseMoveHandler.current = null
    }
    if (mouseUpHandler.current) {
      document.removeEventListener('mouseup', mouseUpHandler.current)
      mouseUpHandler.current = null
    }
  }, [])

  // Cleanup drag listeners on unmount
  useEffect(() => {
    return () => cleanupDrag()
  }, [cleanupDrag])

  // Drag-to-resize handler
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    const startX = e.clientX
    const startWidth = width

    const handleMouseMove = (ev: MouseEvent) => {
      if (!isDragging.current) return
      // Delta: positive = drag left (wider), negative = drag right (narrower)
      const delta = startX - ev.clientX
      const newWidth = startWidth + delta

      if (newWidth < CLOSE_THRESHOLD) {
        onClose()
        cleanupDrag()
        return
      }
      setWidth(Math.max(MIN_WIDTH, Math.min(newWidth, window.innerWidth * MAX_WIDTH_RATIO)))
    }

    const handleMouseUp = () => {
      cleanupDrag()
    }

    mouseMoveHandler.current = handleMouseMove
    mouseUpHandler.current = handleMouseUp
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [width, onClose, cleanupDrag])

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  if (!filePath) return null

  const renderBinaryInfo = (data: FileContent) => {
    if (data.binary_type === 'image') {
      return (
        <div className="flex flex-col items-center justify-center h-full text-center px-6">
          <svg className="w-16 h-16 text-[#4fc3f7]/60 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
          </svg>
          <p className="text-sm text-gray-400 mb-2">图片文件</p>
          <p className="text-xs text-gray-500">可将此图片发送给 AI 助手进行分析</p>
        </div>
      )
    }
    if (data.binary_type === 'document') {
      return (
        <div className="flex flex-col items-center justify-center h-full text-center px-6">
          <svg className="w-16 h-16 text-yellow-500/60 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <p className="text-sm text-gray-400 mb-2">文档文件</p>
          <p className="text-xs text-gray-500">上传到对话后，AI 将自动读取文档中的文字内容</p>
        </div>
      )
    }
    return null
  }

  return (
    <div
      ref={panelRef}
      className="flex h-full shrink-0"
      style={{ width }}
    >
      {/* Drag handle */}
      <div
        className="w-1.5 cursor-col-resize hover:bg-[#4fc3f7]/40 active:bg-[#4fc3f7]/60 shrink-0 transition-colors relative -ml-1.5 z-10"
        onMouseDown={handleMouseDown}
      >
        <div className="absolute inset-y-0 -left-1 -right-1" />
      </div>

      {/* Panel content */}
      <div className="flex-1 flex flex-col min-w-0 border-l border-[#2a2a4a] bg-[#1a1a30]/90 backdrop-blur-sm">
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[#2a2a4a] shrink-0">
          <button
            onClick={onClose}
            className="p-1 text-gray-500 hover:text-gray-200 hover:bg-[#2a2a4a] rounded transition-colors"
            title="关闭面板 (拖拽到最右也可关闭)"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          {data && (
            <>
              <span className="text-sm font-medium text-gray-200 truncate flex-1">{data.name}</span>
              <span className="text-[10px] text-gray-500 whitespace-nowrap">
                {formatSize(data.size)}{data.binary ? '' : ` · ${data.lines} 行`}
              </span>
              {data.truncated && (
                <span className="text-[10px] text-yellow-400 whitespace-nowrap">已截断</span>
              )}
            </>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-3">
          {loading ? (
            <div className="text-sm text-gray-500 text-center py-8">加载中...</div>
          ) : error ? (
            <div className="text-sm text-red-400 text-center py-8">{error}</div>
          ) : data ? (
            data.binary ? renderBinaryInfo(data) : (
            <pre className="text-sm text-gray-200 font-mono whitespace-pre-wrap break-all leading-relaxed">
              {data.content || <span className="text-gray-500">(空文件)</span>}
            </pre>
            )
          ) : (
            <div className="text-sm text-gray-500 text-center py-8">选择文件以查看内容</div>
          )}
        </div>
      </div>
    </div>
  )
}
