import { useState, useEffect, useCallback, useRef } from 'react'
import { filesApi } from '../../api/client'
import type { FileEntry } from '../../types'

interface ProjectExplorerProps {
  onOpenFile: (path: string) => void
  currentProjectPath?: string | null
  onSelectProject: (path: string) => void
  onCreateProject: (name: string) => Promise<string>
  refreshKey?: number
}

function FolderIcon() {
  return (
    <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" strokeWidth="1.5" strokeLinecap="round">
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
    </svg>
  )
}

function FileIcon({ ext, name }: { ext: string; name?: string }) {
  const colorMap: Record<string, string> = {
    '.py': '#3572a5', '.ts': '#3178c6', '.tsx': '#3178c6', '.js': '#f7df1e', '.jsx': '#f7df1e',
    '.json': '#5a5a7a', '.md': '#4fc3f7', '.txt': '#a0a0b0',
    '.html': '#e44d26', '.css': '#1572b6', '.xml': '#e44d26',
    '.yaml': '#6b5a6b', '.yml': '#6b5a6b', '.toml': '#6b5a6b', '.ini': '#6b5a6b',
    '.csv': '#22c55e', '.sql': '#eab308',
    '.sh': '#4ade80', '.bat': '#4ade80',
    '.png': '#e8a838', '.jpg': '#e8a838', '.jpeg': '#e8a838', '.gif': '#e8a838', '.webp': '#e8a838', '.svg': '#e8a838', '.ico': '#e8a838',
    '.pdf': '#f40f02', '.docx': '#2b5797', '.doc': '#2b5797', '.xlsx': '#217346', '.xls': '#217346',
    '.pptx': '#d04526', '.ppt': '#d04526',
    '.zip': '#a0a0b0', '.tar': '#a0a0b0', '.gz': '#a0a0b0', '.rar': '#a0a0b0', '.7z': '#a0a0b0',
    '.mp4': '#8e44ad', '.avi': '#8e44ad', '.mov': '#8e44ad', '.mkv': '#8e44ad',
    '.mp3': '#8e44ad', '.wav': '#8e44ad', '.flac': '#8e44ad',
  }
  const color = colorMap[ext] || '#a0a0b0'
  const nameLower = (name || '').toLowerCase()

  if (nameLower === 'dockerfile' || nameLower.endsWith('.dockerfile')) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="#2496ed" strokeWidth="1.5">
        <rect x="3" y="7" width="18" height="13" rx="1.5" />
        <path d="M7 14h2v2H7zM10 12h2v4h-2zM13 10h2v6h-2zM16 11h2v5h-2z" />
      </svg>
    )
  }

  if (nameLower === '.gitignore' || nameLower === '.gitattributes' || nameLower === '.gitmodules') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="#f05032" strokeWidth="1.5">
        <path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 01-.3-.94L3 8.28V6c0-.55.45-1 1-1h1l1.76-2.77a.82.82 0 011.44 0L10 5h4l1.76-2.77a.82.82 0 011.44 0L19 5h1c.55 0 1 .45 1 1v2.28l1.95 5.17a.84.84 0 01-.3.94z" fill="#f05032" stroke="none" />
        <circle cx="12" cy="12" r="2" fill="white" stroke="none" />
      </svg>
    )
  }

  // ── Image files ──
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.bmp'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <rect x="2" y="3" width="20" height="18" rx="2" />
        <circle cx="8.5" cy="9" r="2" fill={color} stroke="none" />
        <path d="M21 15l-5-5L6 21" />
        <path d="M15 15l3-3 4 4" />
      </svg>
    )
  }

  // ── Audio ──
  if (['.mp3', '.wav', '.flac', '.aac', '.ogg'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
      </svg>
    )
  }

  // ── Video ──
  if (['.mp4', '.avi', '.mov', '.mkv', '.webm'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <polygon points="10 9 16 12 10 15" fill={color} stroke="none" />
      </svg>
    )
  }

  // ── Archives ──
  if (['.zip', '.tar', '.gz', '.rar', '.7z'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M21 8v10a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2h7l4 4z" />
        <path d="M9 12h6" /><path d="M12 9v6" />
      </svg>
    )
  }

  // ── PDF ──
  if (ext === '.pdf') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <text x="6" y="17" fontSize="7" fill={color} stroke="none" fontWeight="bold">PDF</text>
      </svg>
    )
  }

  // ── Office documents ──
  if (['.docx', '.doc'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <text x="6" y="17" fontSize="7" fill={color} stroke="none" fontWeight="bold">W</text>
      </svg>
    )
  }

  if (['.xlsx', '.xls'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <text x="6" y="17" fontSize="7" fill={color} stroke="none" fontWeight="bold">X</text>
      </svg>
    )
  }

  if (['.pptx', '.ppt'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <text x="6" y="17" fontSize="7" fill={color} stroke="none" fontWeight="bold">P</text>
      </svg>
    )
  }

  // ── Python ──
  if (ext === '.py') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M12.5 1C7.5 1 6.5 3.5 6.5 5v2h6v1.5H5C2.5 8.5 1 10 1 13s1 5 4 5h2v-2.5c0-2 2-3.5 4-3.5h5c2 0 3.5-1.5 3.5-3.5V5c0-2-2-4-5.5-4h-1.5z" />
        <path d="M12.5 15c-5 0-5.5 2-5.5 4v1.5c0 2 2 3.5 5 3.5h3c3 0 4-1.5 4-3.5V19c0-2-2-4-6.5-4z" />
      </svg>
    )
  }

  // ── JavaScript ──
  if (['.js', '.jsx', '.mjs', '.cjs'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <rect x="2" y="2" width="20" height="20" rx="2" />
        <path d="M14 15c0 2 1.5 3 3 3s3-1 3-3-1.5-3-3-3-3-1-3-3 1.5-3 3-3 3 1 3 3" />
        <path d="M7 17V10c0-1 .5-2 2-2s2 1 2 2v7" />
      </svg>
    )
  }

  // ── TypeScript ──
  if (['.ts', '.tsx', '.mts', '.cts'].includes(ext)) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <rect x="2" y="2" width="20" height="20" rx="2" />
        <path d="M8 17V8M5 8h6" />
        <path d="M15 14c0 1.5 1 2 2 2s2-.5 2-2-1-2-2-2-2-1-2-2 1-2 2-2 2 .5 2 2" />
      </svg>
    )
  }

  // ── HTML ──
  if (ext === '.html') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M4 3l1.5 18L12 22l6.5-1L20 3H4z" />
        <path d="M8 8h8l-.5 5.5L12 15l-3.5-1.5" />
        <path d="M6 11h1.5" />
      </svg>
    )
  }

  // ── CSS ──
  if (ext === '.css') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M4 3l1.5 18L12 22l6.5-1L20 3H4z" />
        <path d="M16 8H8l.5 3H15l-.5 5L12 17l-2.5-1" />
      </svg>
    )
  }

  // ── SQL / Database ──
  if (ext === '.sql') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <ellipse cx="12" cy="5" rx="9" ry="3" />
        <path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5" />
        <path d="M3 12c0 1.7 4 3 9 3s9-1.3 9-3" />
      </svg>
    )
  }

  // ── CSV / Table ──
  if (ext === '.csv') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
      </svg>
    )
  }

  // ── Markdown ──
  if (ext === '.md') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <path d="M6 16V8l2.5 3L11 8v8" />
        <path d="M13 8v8l3-3 3 3V8" />
      </svg>
    )
  }

  // ── Shell / Terminal ──
  if (['.sh', '.bat', '.ps1', '.zsh', '.bash'].includes(ext) || nameLower === 'makefile') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M4 17l4-8-4-4" />
        <path d="M12 5h8" />
        <path d="M8 19h12" />
      </svg>
    )
  }

  // ── Config / Settings ──
  if (['.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'].includes(ext) || nameLower.startsWith('.env')) {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>
    )
  }

  // ── Text ──
  if (ext === '.txt') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="13" y2="17" />
      </svg>
    )
  }

  // ── XML ──
  if (ext === '.xml') {
    return (
      <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M8 14l2 2-2 2" />
        <path d="M12 18h4" />
      </svg>
    )
  }

  // ── Generic file (fallback) ──
  return (
    <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface TreeNodeProps {
  entry: FileEntry
  expandedDirs: Set<string>
  dirCache: Record<string, FileEntry[]>
  onToggle: (dirPath: string) => void
  onOpenFile: (path: string) => void
  onDelete: (entry: FileEntry) => void
  depth: number
}

function TreeNode({ entry, expandedDirs, dirCache, onToggle, onOpenFile, onDelete, depth }: TreeNodeProps) {
  const isDir = entry.type === 'dir'
  const isExpanded = isDir && expandedDirs.has(entry.path)
  const children = isDir && isExpanded ? (dirCache[entry.path] || []) : []
  const isLoading = isDir && isExpanded && !dirCache[entry.path]

  const handleClick = () => {
    if (isDir) onToggle(entry.path)
    else onOpenFile(entry.path)
  }

  return (
    <>
      <button
        onClick={handleClick}
        className="w-full flex items-center gap-1.5 px-3 py-1 text-xs text-gray-300 hover:text-white hover:bg-white/10 rounded-2xl transition-colors text-left group"
        title={entry.path}
        style={{ paddingLeft: `${12 + depth * 14}px` }}
      >
        {isDir ? (
          <svg className={`w-3 h-3 shrink-0 text-gray-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        ) : (
          <span className="w-3 shrink-0" />
        )}
        {isDir ? <FolderIcon /> : <FileIcon ext={entry.ext} name={entry.name} />}
        <span className="truncate flex-1">{entry.name}</span>
        {!isDir && (
          <span className="text-[9px] text-gray-600 flex-shrink-0">{formatSize(entry.size)}</span>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(entry) }}
          className="opacity-0 group-hover:opacity-100 p-0.5 text-gray-600 hover:text-red-400 transition-all shrink-0"
          title={isDir ? '删除文件夹' : '删除文件'}
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </button>
      {isExpanded && (
        <div className="space-y-0.5">
          {isLoading ? (
            <div className="text-[10px] text-gray-600 text-center py-0.5" style={{ paddingLeft: `${24 + depth * 14}px` }}>加载中...</div>
          ) : children.length === 0 ? (
            <div className="text-[10px] text-gray-600 py-0.5" style={{ paddingLeft: `${24 + depth * 14}px` }}>空目录</div>
          ) : (
            children.map((child) => (
              <TreeNode
                key={child.path}
                entry={child}
                expandedDirs={expandedDirs}
                dirCache={dirCache}
                onToggle={onToggle}
                onOpenFile={onOpenFile}
                onDelete={onDelete}
                depth={depth + 1}
              />
            ))
          )}
        </div>
      )}
    </>
  )
}

const electronAPI = (window as unknown as { electronAPI?: { openDirectory?: () => Promise<string | null> } }).electronAPI

export function ProjectExplorer({ onOpenFile, currentProjectPath, onSelectProject, onCreateProject, refreshKey }: ProjectExplorerProps) {
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set())
  const [dirCache, setDirCache] = useState<Record<string, FileEntry[]>>({})
  const [collapsed, setCollapsed] = useState(false)
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [creatingProject, setCreatingProject] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<FileEntry | null>(null)
  const [deleting, setDeleting] = useState(false)

  // ── Drag & drop ──────────────────────────────────────────────────
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'link'
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    // Electron exposes the full file system path via File.path
    const fsPath = (file as any).path as string | undefined
    if (fsPath) {
      onSelectProject(fsPath)
    } else {
      setError('拖放功能仅在桌面客户端可用')
    }
  }, [onSelectProject])

  // ── Create file/folder ────────────────────────────────────────────
  const [creating, setCreating] = useState<'file' | 'folder' | null>(null)
  const [newItemName, setNewItemName] = useState('')
  const newItemInputRef = useRef<HTMLInputElement>(null)

  const handleCreateSubmit = async () => {
    if (!newItemName.trim() || !currentProjectPath || !creating) return
    try {
      if (creating === 'folder') {
        await filesApi.createDir(newItemName.trim(), currentProjectPath)
      } else {
        await filesApi.createFile(newItemName.trim(), '', currentProjectPath)
      }
      setCreating(null)
      setNewItemName('')
      const res = await filesApi.listDir('.', currentProjectPath)
      setEntries(res.entries)
      setDirCache({})
      setExpandedDirs(new Set())
      setError('')
    } catch (err: any) {
      setError(err.message || '创建失败')
    }
  }

  const handleCreateCancel = () => {
    setCreating(null)
    setNewItemName('')
  }

  const handleDelete = useCallback(async (entry: FileEntry) => {
    if (!currentProjectPath) return
    // Immediate soft delete for empty directories; confirm for files and non-empty dirs
    if (entry.type === 'dir') {
      setDeleteTarget(entry)
      return
    }
    // File: confirm then delete
    if (!window.confirm(`确认删除文件「${entry.name}」？\n此操作不可撤销。`)) return
    setDeleting(true)
    try {
      await filesApi.deleteFile(entry.path, currentProjectPath)
      // Refresh root directory
      const res = await filesApi.listDir('.', currentProjectPath)
      setEntries(res.entries)
      setDirCache({})
      setExpandedDirs(new Set())
    } catch (err: any) {
      setError(err.message || '删除失败')
    } finally {
      setDeleting(false)
    }
  }, [currentProjectPath])

  const confirmDeleteDir = useCallback(async () => {
    if (!deleteTarget || !currentProjectPath) return
    setDeleting(true)
    setDeleteTarget(null)
    try {
      await filesApi.deleteFile(deleteTarget.path, currentProjectPath)
      const res = await filesApi.listDir('.', currentProjectPath)
      setEntries(res.entries)
      setDirCache({})
      setExpandedDirs(new Set())
    } catch (err: any) {
      setError(err.message || '删除失败')
    } finally {
      setDeleting(false)
    }
  }, [deleteTarget, currentProjectPath])

  useEffect(() => {
    if (creating) newItemInputRef.current?.focus()
  }, [creating])

  // Load root directory when project changes
  useEffect(() => {
    if (currentProjectPath) {
      setLoading(true)
      setError('')
      setExpandedDirs(new Set())
      setDirCache({})
      filesApi.listDir('.', currentProjectPath).then((res) => {
        setEntries(res.entries)
      }).catch((err: any) => {
        setError(err.message || '加载失败')
      }).finally(() => {
        setLoading(false)
      })
    } else {
      setEntries([])
      setExpandedDirs(new Set())
      setDirCache({})
    }
  }, [currentProjectPath, refreshKey])

  const handleOpenFolder = async () => {
    if (electronAPI?.openDirectory) {
      const dir = await electronAPI.openDirectory()
      if (dir) onSelectProject(dir)
    } else {
      const dir = window.prompt('请输入项目文件夹路径:', '')
      if (dir) onSelectProject(dir)
    }
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return
    setCreatingProject(true)
    try {
      const createdPath = await onCreateProject(newProjectName.trim())
      setNewProjectName('')
      setShowNewProject(false)
      // If created without a parent root, the returned path is relative — resolve to absolute
      onSelectProject(createdPath)
    } catch (err: any) {
      setError(err.message || '创建项目失败')
    } finally {
      setCreatingProject(false)
    }
  }

  const toggleDir = useCallback(async (dirPath: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev)
      if (next.has(dirPath)) {
        next.delete(dirPath)
      } else {
        next.add(dirPath)
      }
      return next
    })

    // Fetch directory contents outside updater
    if (!dirCache[dirPath] && currentProjectPath) {
      try {
        const res = await filesApi.listDir(dirPath, currentProjectPath)
        setDirCache((cache) => ({ ...cache, [dirPath]: res.entries }))
      } catch {
        // ignore
      }
    }
  }, [dirCache, currentProjectPath])

  const handleFileOpen = (path: string) => {
    onOpenFile(path)
  }

  // --- No project selected state ---
  if (!currentProjectPath) {
    return (
      <div
        className={`rounded-2xl overflow-hidden pt-1 transition-colors ${dragOver ? 'ring-2 ring-[#4fc3f7] bg-white/10' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-center gap-2 px-3 py-1 text-sm font-medium text-gray-200">
          <FolderIcon />
          <span>资源管理器</span>
        </div>
        <div className="px-3 pt-3 pb-6 flex flex-col items-center gap-3">
          {showNewProject ? (
            <div className="flex flex-col gap-2 w-full">
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="输入项目文件夹名称"
                className="w-full px-3 py-1.5 text-xs bg-white/10 backdrop-blur-[40px] text-white border border-white/15 rounded-2xl outline-none focus:border-white/30"
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreateProject() }}
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreateProject}
                  disabled={creatingProject || !newProjectName.trim()}
                  className="flex-1 px-3 py-1.5 text-xs text-white bg-white/15 hover:bg-white/25 rounded-2xl transition-colors disabled:opacity-50"
                >
                  {creatingProject ? '创建中...' : '创建'}
                </button>
                <button
                  onClick={() => { setShowNewProject(false); setNewProjectName('') }}
                  className="px-3 py-1.5 text-xs text-gray-400 hover:text-white rounded-md transition-colors"
                >
                  取消
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={handleOpenFolder}
                  className="flex items-center gap-2 px-4 py-2 text-xs text-gray-200 bg-white/10 hover:bg-white/20 hover:text-white rounded-2xl transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  打开文件夹
                </button>
                <button
                  onClick={() => setShowNewProject(true)}
                  className="flex items-center gap-2 px-4 py-2 text-xs text-gray-400 hover:text-white transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  新建项目
                </button>
              </div>
              <span className="text-[10px] text-gray-500">或将文件夹拖放到此处</span>
            </div>
          )}
        </div>
      </div>
    )
  }

  // --- Project is open ---
  return (
    <div
      className={`rounded-2xl overflow-hidden pt-2 transition-colors ${dragOver ? 'ring-2 ring-[#4fc3f7] bg-white/10' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-200 hover:text-white transition-colors group"
      >
        <div className="flex items-center gap-2 min-w-0">
          <FolderIcon />
          <span className="truncate">{currentProjectPath.split(/[/\\]/).pop() || '资源管理器'}</span>
        </div>
        <svg
          className={`w-3 h-3 text-gray-500 shrink-0 transition-transform duration-200 ${collapsed ? '' : 'rotate-180'}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {!collapsed && (
        <div className="mt-0.5">
          {/* Project path bar */}
          <div className="flex items-center gap-1 px-2 mb-1">
            <button
              onClick={handleOpenFolder}
              className="p-0.5 text-gray-500 hover:text-white transition-colors shrink-0"
              title="切换项目"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
            </button>
            <span className="text-[10px] text-gray-400 truncate flex-1" title={currentProjectPath}>
              {currentProjectPath}
            </span>
            <button
              onClick={() => onSelectProject('')}
              className="p-0.5 text-gray-500 hover:text-red-400 transition-colors shrink-0"
              title="关闭当前文件夹"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4m7-2l5 5-5 5M16 3h-6" />
              </svg>
            </button>
            <button
              onClick={() => { setCreating('file'); setNewItemName('') }}
              className="p-0.5 text-gray-500 hover:text-[#4fc3f7] transition-colors shrink-0"
              title="新建文件"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="12" x2="12" y2="18" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
            </button>
            <button
              onClick={() => { setCreating('folder'); setNewItemName('') }}
              className="p-0.5 text-gray-500 hover:text-[#fbbf24] transition-colors shrink-0"
              title="新建文件夹"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
                <line x1="12" y1="10" x2="12" y2="16" />
                <line x1="9" y1="13" x2="15" y2="13" />
              </svg>
            </button>
            <button
              onClick={() => {
                if (currentProjectPath) {
                  filesApi.listDir('.', currentProjectPath).then((res) => {
                    setEntries(res.entries)
                    setDirCache({})
                    setExpandedDirs(new Set())
                    setError('')
                  }).catch((err: any) => setError(err.message || '刷新失败'))
                }
              }}
              className="p-0.5 text-gray-500 hover:text-white transition-colors shrink-0"
              title="刷新"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>

          {/* Inline create file/folder input */}
          {creating && (
            <div className="flex items-center gap-1 px-3 py-1 border-t border-white/10">
              {creating === 'folder' ? <FolderIcon /> : <FileIcon ext="" />}
              <input
                ref={newItemInputRef}
                type="text"
                value={newItemName}
                onChange={(e) => setNewItemName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateSubmit()
                  if (e.key === 'Escape') handleCreateCancel()
                }}
                placeholder={creating === 'folder' ? '文件夹名称' : '文件名 (如 main.py)'}
                className="flex-1 px-2 py-1 text-xs bg-white/10 backdrop-blur-[40px] text-white border border-white/15 rounded-2xl outline-none focus:border-[#4fc3f7] placeholder-gray-500"
              />
              <button
                onClick={handleCreateSubmit}
                disabled={!newItemName.trim()}
                className="px-2 py-1 text-[10px] text-white bg-white/15 hover:bg-white/25 rounded-2xl disabled:opacity-40 transition-colors"
              >
                确定
              </button>
              <button
                onClick={handleCreateCancel}
                className="px-2 py-1 text-[10px] text-gray-400 hover:text-white transition-colors"
              >
                取消
              </button>
            </div>
          )}

          {/* File list */}
          <div className="max-h-[300px] overflow-y-auto">
            {loading ? (
              <div className="px-3 py-2 text-xs text-gray-500 text-center">加载中...</div>
            ) : error ? (
              <div className="px-3 py-2 text-xs text-red-400 text-center">{error}</div>
            ) : entries.length === 0 ? (
              <div className="px-3 py-2 text-xs text-gray-500 text-center">空目录</div>
            ) : (
              <div className="space-y-0.5">
                {entries.map((entry) => (
                  <TreeNode
                    key={entry.path}
                    entry={entry}
                    expandedDirs={expandedDirs}
                    dirCache={dirCache}
                    onToggle={toggleDir}
                    onOpenFile={handleFileOpen}
                    onDelete={handleDelete}
                    depth={0}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      {deleteTarget && (
        <div className="px-3 py-2 border-t border-white/10">
          {deleting ? (
            <div className="text-xs text-gray-500 text-center">删除中...</div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="text-[11px] text-gray-300">
                确认删除 <span className="text-red-400 font-medium">{deleteTarget.name}</span> ？
                <div className="text-[10px] text-gray-500 mt-0.5">此操作不可撤销。</div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={confirmDeleteDir}
                  className="flex-1 px-2 py-1 text-[10px] text-white bg-red-500/80 hover:bg-red-500 rounded-2xl transition-colors"
                >
                  删除
                </button>
                <button
                  onClick={() => setDeleteTarget(null)}
                  className="px-3 py-1 text-[10px] text-gray-400 hover:text-white transition-colors"
                >
                  取消
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
