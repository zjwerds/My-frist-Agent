import { useState, useCallback, useRef, useEffect } from 'react'
import { ProjectExplorer } from './ProjectExplorer'
import { StatsSection } from './StatsSection'

interface SidebarProps {
  onOpenFile: (path: string) => void
  currentProjectPath?: string | null
  onSelectProject: (path: string) => void
  onCreateProject: (name: string) => Promise<string>
  refreshKey?: number
}

const MIN_WIDTH = 180
const MAX_WIDTH = 500
const DEFAULT_WIDTH = 280
const STORAGE_KEY = 'sidebar-width'

export function Sidebar({
  onOpenFile,
  currentProjectPath,
  onSelectProject,
  onCreateProject,
  refreshKey,
}: SidebarProps) {
  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Number(saved))) : DEFAULT_WIDTH
  })
  const isDragging = useRef(false)
  const mouseMoveHandler = useRef<((ev: MouseEvent) => void) | null>(null)
  const mouseUpHandler = useRef<((ev: MouseEvent) => void) | null>(null)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(width))
  }, [width])

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

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    const startX = e.clientX
    const startWidth = width

    const handleMouseMove = (ev: MouseEvent) => {
      if (!isDragging.current) return
      const delta = ev.clientX - startX
      setWidth(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, startWidth + delta)))
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
  }, [width, cleanupDrag])

  // Cleanup drag listeners on unmount
  useEffect(() => {
    return () => {
      cleanupDrag()
    }
  }, [cleanupDrag])

  return (
    <div className="flex shrink-0 h-full" style={{ width }}>
      <div className="flex-1 flex flex-col h-full min-w-0 glass border-r border-white/40">
        {/* Main content - Project Explorer fills available space */}
        <div className="flex-1 overflow-y-auto p-2">
          <ProjectExplorer
            onOpenFile={onOpenFile}
            currentProjectPath={currentProjectPath}
            onSelectProject={onSelectProject}
            onCreateProject={onCreateProject}
            refreshKey={refreshKey}
          />
        </div>

        {/* Stats at the bottom */}
        <div className="border-t border-white/10">
          <StatsSection />
        </div>
      </div>

      {/* Drag handle */}
      <div
        className="w-1.5 cursor-col-resize hover:bg-[#4fc3f7]/40 active:bg-[#4fc3f7]/60 shrink-0 transition-colors relative z-10"
        onMouseDown={handleMouseDown}
      >
        <div className="absolute inset-y-0 -left-1 -right-1" />
      </div>
    </div>
  )
}
