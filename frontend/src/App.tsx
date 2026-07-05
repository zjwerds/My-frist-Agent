import { useState, useEffect, useCallback } from 'react'
import type { RightView, Conversation } from './types'
import { Sidebar } from './components/Sidebar/Sidebar'
import { RightPanel } from './components/RightPanel/RightPanel'
import { FileViewer } from './components/RightPanel/FileViewer'
import { MenuBar } from './components/MenuBar/MenuBar'
import { apisApi, historyApi, filesApi } from './api/client'

const STORAGE_THEME = 'color-theme'
const STORAGE_BG = 'bg-image'
const STORAGE_CONVERSATION = 'active-conversation-id'
const STORAGE_PROJECT = 'current-project-path'

export default function App() {
  const [rightView, setRightView] = useState<RightView>('chat')
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [currentProjectPath, setCurrentProjectPath] = useState<string | null>(null)
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null)
  const [theme, setTheme] = useState('warm')
  const [bgImage, setBgImage] = useState<string | null>(null)
  const [hasApiKey, setHasApiKey] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [temperature, setTemperature] = useState(0.5)

  useEffect(() => {
    const savedTheme = localStorage.getItem(STORAGE_THEME) || 'warm'
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

  // Check API config status on mount and after config changes
  useEffect(() => {
    apisApi.list().then((configs) => {
      setHasApiKey(configs.length > 0 && configs[0].api_key.length > 0)
    }).catch(() => setHasApiKey(false))
  }, [refreshKey])

  const handleThemeChange = (newTheme: string) => {
    setTheme(newTheme)
    localStorage.setItem(STORAGE_THEME, newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
  }

  const handleBgUpload = (dataUrl: string) => {
    setBgImage(dataUrl)
    localStorage.setItem(STORAGE_BG, dataUrl)
  }

  const handleBgRemove = () => {
    setBgImage(null)
    localStorage.removeItem(STORAGE_BG)
  }

  const handleMessageComplete = () => setRefreshKey((k) => k + 1)
  const handleUsage = (usage: { prompt_tokens: number; completion_tokens: number; cache_hit_tokens: number }) => {
    console.log('[usage]', usage)
  }
  const handleSelectApi = () => setRightView('api-config')
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

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden">
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
        onSelectApi={handleSelectApi}
        onApiConfigSaved={handleMessageComplete}
        onOpenFile={() => handleOpenFile('')}
        hasApiKey={hasApiKey}
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
      <div
        className="flex flex-1 overflow-hidden"
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
        <RightPanel
          view={rightView}
          conversationId={activeConversationId}
          onBackToChat={handleBackToChat}
          onMessageComplete={handleMessageComplete}
          onUsage={handleUsage}
          onNewConversation={handleNewConversation}
          temperature={temperature}
          onSwitchConversation={handleSwitchConversation}
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
