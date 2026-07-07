import { useState, useEffect, useCallback } from 'react'
import type { RightView, Conversation } from './types'
import { Sidebar } from './components/Sidebar/Sidebar'
import { RightPanel } from './components/RightPanel/RightPanel'
import { FileViewer } from './components/RightPanel/FileViewer'
import { MenuBar } from './components/MenuBar/MenuBar'
import { historyApi, filesApi, skillsApi, checkBackendHealth } from './api/client'

const STORAGE_THEME = 'color-theme'
const STORAGE_BG = 'bg-image'
const STORAGE_CONVERSATION = 'active-conversation-id'
const STORAGE_PROJECT = 'current-project-path'

export default function App() {
  const [rightView, setRightView] = useState<RightView>('chat')
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [currentProjectPath, setCurrentProjectPath] = useState<string | null>(null)
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null)
  const [theme, setTheme] = useState('theme1')
  const [bgImage, setBgImage] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [temperature, setTemperature] = useState(0.5)
  const [backendOk, setBackendOk] = useState(false)
  const [backendStarting, setBackendStarting] = useState(true)
  const [startupTimeout, setStartupTimeout] = useState(false)
  const [showSkillReminder, setShowSkillReminder] = useState(false)

  useEffect(() => {
    const savedTheme = localStorage.getItem(STORAGE_THEME) || 'theme1'
    const savedBg = localStorage.getItem(STORAGE_BG)
    const savedProject = localStorage.getItem(STORAGE_PROJECT)
    setTheme(savedTheme)
    document.documentElement.setAttribute('data-theme', savedTheme)
    if (savedBg) {
      setBgImage(savedBg)
    }
    if (savedProject) {
      setCurrentProjectPath(savedProject)
    }

    // Restore last active conversation
    const savedConvId = localStorage.getItem(STORAGE_CONVERSATION)
    if (savedConvId) {
      historyApi.get(savedConvId).then((data: any) => {
        if (data && data.id) {
          setActiveConversationId(data.id)
        }
      }).catch(() => {
        // conversation was deleted, ignore
        localStorage.removeItem(STORAGE_CONVERSATION)
      })
    }
  }, [])

  // Backend health check — fast poll during startup, slow poll after
  useEffect(() => {
    let confirmTimer: ReturnType<typeof setTimeout> | null = null

    const check = () => checkBackendHealth().then((ok) => {
      if (ok) {
        setBackendOk(true)
        if (backendStarting) setBackendStarting(false)
      } else if (!backendStarting) {
        // Backend was running, now appears down.
        // The watchdog may restart it within 1-2 seconds,
        // so confirm before showing the red banner (avoid flicker).
        if (confirmTimer === null) {
          confirmTimer = setTimeout(() => {
            confirmTimer = null
            checkBackendHealth().then((ok2) => {
              if (!ok2) setBackendOk(false)
            })
          }, 2500)
        }
      }
    })
    check()
    const interval = backendStarting ? 1000 : 5000
    const id = setInterval(check, interval)

    return () => {
      clearInterval(id)
      if (confirmTimer !== null) clearTimeout(confirmTimer)
    }
  }, [backendStarting])

  // IPC health listener — registered once on mount, independent of polling lifecycle
  // Only sets ok=true (recovery); defers ok=false to polling (which has confirmation delay)
  useEffect(() => {
    const electronAPI = (window as unknown as { electronAPI?: { onBackendHealth?: (cb: (ok: boolean) => void) => () => void } }).electronAPI
    if (electronAPI?.onBackendHealth) {
      return electronAPI.onBackendHealth((ok: boolean) => {
        if (ok) {
          setBackendOk(true)
          if (backendStarting) setBackendStarting(false)
        }
        // When IPC says false — let the polling handle it
        // (polling has a 2.5s confirmation guard to avoid watchdog flicker)
      })
    }
  }, [])

  // Startup timeout — show error after 30s of waiting
  useEffect(() => {
    if (!backendStarting) return
    const id = setTimeout(() => setStartupTimeout(true), 30000)
    return () => clearTimeout(id)
  }, [backendStarting])

  // Check skill status after backend is ready
  useEffect(() => {
    if (!backendOk) return
    if (localStorage.getItem('skill-reminder-dismissed')) return
    skillsApi.list().then((skills) => {
      const hasEnabled = skills.some((s) => s.enabled)
      if (!hasEnabled) setShowSkillReminder(true)
    }).catch(() => {})
  }, [backendOk])

  const handleThemeChange = (newTheme: string) => {
    setTheme(newTheme)
    localStorage.setItem(STORAGE_THEME, newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  const handleBgUpload = (dataUrl: string) => {
    setBgImage(dataUrl)
    localStorage.setItem(STORAGE_BG, dataUrl)
    document.documentElement.setAttribute('data-bg', 'true')
  }

  const handleBgRemove = () => {
    setBgImage(null)
    localStorage.removeItem(STORAGE_BG)
    document.documentElement.removeAttribute('data-bg')
  }

  const handleMessageComplete = () => setRefreshKey((k) => k + 1)
  const handleUsage = (_usage: { prompt_tokens: number; completion_tokens: number; cache_hit_tokens: number }) => {
    // usage logged server-side; no-op in production
  }
  const handleBackToChat = () => setRightView('chat')
  const handleOpenFile = (path: string) => {
    setActiveFilePath(path)
  }
  const handleCloseFile = () => {
    setActiveFilePath(null)
  }

  const handleSelectProject = useCallback((path: string) => {
    setCurrentProjectPath(path)
    localStorage.setItem(STORAGE_PROJECT, path)
    setActiveFilePath(null)
  }, [])

  const handleCreateProject = useCallback(async (name: string): Promise<string> => {
    const result = await filesApi.createDir(name, currentProjectPath || undefined)
    return result.path
  }, [currentProjectPath])

  const handleNewConversation = useCallback(async () => {
    const conv = await historyApi.create(currentProjectPath || undefined)
    setActiveConversationId(conv.id)
    return conv
  }, [currentProjectPath])

  // Persist active conversation to localStorage
  useEffect(() => {
    if (activeConversationId) {
      localStorage.setItem(STORAGE_CONVERSATION, activeConversationId)
    }
  }, [activeConversationId])

  const handleSelectConversation = (conv: Conversation) => {
    setActiveConversationId(conv.id)
    setRightView('chat')
  }

  const handleDeleteConversation = (id: string) => {
    if (activeConversationId === id) setActiveConversationId(null)
  }

  const handleTemperatureChange = (value: number) => {
    setTemperature(value)
  }

  const handleSwitchConversation = useCallback((conv: any) => {
    setActiveConversationId(conv.id)
    setRightView('chat')
  }, [])

  // ── Full-screen loading overlay during initial backend startup ──────────
  if (backendStarting && !backendOk) {
    return (
      <div className="flex items-center justify-center h-screen w-screen app-bg" style={{ fontFamily: 'system-ui, sans-serif' }}>
        <div className="flex flex-col items-center gap-4">
          <svg width="48" height="48" viewBox="0 0 80 80" fill="none" className="text-gray-500 animate-pulse">
            <ellipse cx="40" cy="43" rx="22" ry="28" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="31" cy="36" r="3" fill="currentColor" />
            <circle cx="49" cy="36" r="3" fill="currentColor" />
            <path d="M34 47 Q40 53 46 47" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span className="text-sm text-gray-500">
            {startupTimeout
              ? '后端启动超时，请检查程序是否被安全软件拦截'
              : '正在启动后端服务...'}
          </span>
          {!startupTimeout && <span className="w-4 h-4 border-2 border-gray-600 border-t-transparent rounded-full animate-spin" />}
          {startupTimeout && (
            <button
              onClick={() => {
                setStartupTimeout(false)
                setBackendStarting(true)
                checkBackendHealth().then((ok) => {
                  setBackendOk(ok)
                  if (ok) setBackendStarting(false)
                  else setStartupTimeout(true)
                })
              }}
              className="px-4 py-1.5 text-xs bg-[#f59e6b] text-white rounded hover:bg-[#e08a55] transition-colors"
            >
              重试
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden app-bg">
      <MenuBar
        theme={theme}
        onThemeChange={handleThemeChange}
        currentProjectPath={currentProjectPath}
        onNewConversation={(conv) => {
          if (conv) {
            setActiveConversationId(conv.id)
          } else {
            setActiveConversationId(null)
          }
          setRightView('chat')
        }}
        onApiConfigSaved={handleMessageComplete}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        refreshKey={refreshKey}
        onBgUpload={handleBgUpload}
        onBgRemove={handleBgRemove}
        hasBg={!!bgImage}
        temperature={temperature}
        onTemperatureChange={handleTemperatureChange}
      />
      {/* Skill reminder banner */}
      {showSkillReminder && (
        <div className="flex items-center gap-3 px-4 py-2 glass-sm border-b border-white/10 text-sm">
          <span className="text-xs text-gray-300">
            💡 你还没有启用任何技能。前往 <strong>工具 → 技能管理</strong> 选择你需要的技能以获得更好体验
          </span>
          <button
            onClick={() => {
              localStorage.setItem('skill-reminder-dismissed', 'true')
              setShowSkillReminder(false)
            }}
            className="ml-auto text-[10px] text-gray-500 hover:text-white transition-colors shrink-0"
          >
            不再提示
          </button>
          <button
            onClick={() => setShowSkillReminder(false)}
            className="text-gray-500 hover:text-white transition-colors shrink-0"
            title="关闭"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}
      <div
        className="flex flex-1 overflow-hidden relative"
        style={{
          backgroundColor: bgImage ? undefined : 'var(--bg)',
          backgroundImage: bgImage ? `url(${bgImage})` : undefined,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <Sidebar
          onOpenFile={handleOpenFile}
          currentProjectPath={currentProjectPath}
          onSelectProject={handleSelectProject}
          onCreateProject={handleCreateProject}
        />
        {!backendOk && (
          <div className="absolute top-0 left-0 right-0 z-40 flex items-center justify-center gap-2 py-2 bg-red-500/70 backdrop-blur-[20px] text-white text-xs">
            <span>⚠️ 后端服务未连接，请检查 <code className="px-1 bg-white/10 rounded">deepseek-agent-backend.exe</code> 是否正在运行</span>
            <button
              onClick={() => checkBackendHealth().then(setBackendOk)}
              className="px-2 py-0.5 bg-white/20 rounded hover:bg-white/30 transition-colors"
            >
              重试
            </button>
          </div>
        )}
        <RightPanel
          view={rightView}
          conversationId={activeConversationId}
          onBackToChat={handleBackToChat}
          onMessageComplete={handleMessageComplete}
          onUsage={handleUsage}
          onNewConversation={handleNewConversation}
          temperature={temperature}
          onSwitchConversation={handleSwitchConversation}
          currentProjectPath={currentProjectPath}
        />
        {activeFilePath && (
          <FileViewer
            filePath={activeFilePath}
            onClose={handleCloseFile}
            currentProjectPath={currentProjectPath}
          />
        )}
      </div>
    </div>
  )
}
