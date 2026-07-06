import { useState, useEffect, useRef } from 'react'
import type { Conversation } from '../../types'
import { ConversationPopover } from '../ConversationPopover/ConversationPopover'
import { SkillsPopover } from '../SkillsPopover/SkillsPopover'
import { SettingsPopover } from '../SettingsPopover/SettingsPopover'
import { ApiConfigPopover } from '../ApiConfigPopover/ApiConfigPopover'

interface MenuItem {
  label: string
  action?: () => void
  divider?: boolean
}

type MenuId = 'file' | 'edit' | 'selection' | 'view' | 'run' | 'help'

interface TitleBarProps {
  theme: string
  onThemeChange: (theme: string) => void
  onNewConversation?: (conv?: Conversation) => void
  onSelectApi?: () => void
  onOpenFile?: () => void
  hasApiKey?: boolean
  onApiConfigSaved?: () => void
  // Conversation popover props
  activeConversationId?: string | null
  currentProjectPath?: string | null
  onSelectConversation?: (conv: Conversation) => void
  onDeleteConversation?: (id: string) => void
  refreshKey?: number
  // Settings popover props
  onBgUpload?: (dataUrl: string) => void
  onBgRemove?: () => void
  hasBg?: boolean
  // Temperature
  temperature?: number
  onTemperatureChange?: (value: number) => void
  // Backend health
  backendOk?: boolean
}

const electronAPI = (window as unknown as { electronAPI?: { minimize?: () => void; maximize?: () => void; close?: () => void; isMaximized?: () => Promise<boolean>; onMaximizeChange?: (cb: (maximized: boolean) => void) => () => void } }).electronAPI

export function MenuBar({ theme, onThemeChange, onNewConversation, onOpenFile, onApiConfigSaved, activeConversationId, currentProjectPath, onSelectConversation, onDeleteConversation, refreshKey, onBgUpload, onBgRemove, hasBg, temperature, onTemperatureChange }: TitleBarProps) {
  const [openMenu, setOpenMenu] = useState<MenuId | null>(null)
  const [isMaximized, setIsMaximized] = useState(false)
  const barRef = useRef<HTMLDivElement>(null)

  // Check initial maximized state
  useEffect(() => {
    if (electronAPI?.isMaximized) {
      electronAPI.isMaximized().then(setIsMaximized)
    }
  }, [])

  // Listen for maximize/unmaximize changes
  useEffect(() => {
    if (electronAPI?.onMaximizeChange) {
      const cleanup = electronAPI.onMaximizeChange(setIsMaximized)
      return cleanup
    }
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setOpenMenu(null)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const toggleMenu = (id: MenuId) => setOpenMenu(openMenu === id ? null : id)
  const closeMenu = () => setOpenMenu(null)

  // Window controls
  const handleMinimize = () => electronAPI?.minimize?.()
  const handleMaximize = () => electronAPI?.maximize?.()
  const handleClose = () => electronAPI?.close?.()
  const handleDoubleClick = () => electronAPI?.maximize?.()

  const menus: Record<MenuId, { label: string; items: MenuItem[] }> = {
    file: {
      label: '文件',
      items: [
        { label: '打开文件...', action: () => { onOpenFile?.(); closeMenu() } },
        { label: '保存', action: () => closeMenu() },
        { label: '另存为', action: () => closeMenu() },
        { label: '', divider: true },
        { label: '退出', action: () => electronAPI?.close?.() },
      ],
    },
    edit: {
      label: '编辑',
      items: [
        { label: '撤销', action: () => closeMenu() },
        { label: '重做', action: () => closeMenu() },
        { label: '', divider: true },
        { label: '剪切', action: () => closeMenu() },
        { label: '复制', action: () => closeMenu() },
        { label: '粘贴', action: () => closeMenu() },
      ],
    },
    selection: {
      label: '选择',
      items: [
        { label: '全选', action: () => closeMenu() },
        { label: '', divider: true },
        { label: '查找', action: () => closeMenu() },
        { label: '替换', action: () => closeMenu() },
      ],
    },
    view: {
      label: '查看',
      items: [
        { label: '切换侧边栏', action: () => closeMenu() },
        { label: '', divider: true },
        { label: '放大', action: () => closeMenu() },
        { label: '缩小', action: () => closeMenu() },
        { label: '重置缩放', action: () => closeMenu() },
      ],
    },
    run: {
      label: '运行',
      items: [
        { label: '运行任务', action: () => closeMenu() },
        { label: '停止任务', action: () => closeMenu() },
      ],
    },
    help: {
      label: '帮助',
      items: [
        { label: '关于 煎蛋Agent', action: () => { alert('煎蛋Agent v1.0\n一个基于 AI 的智能助手平台。'); closeMenu() } },
      ],
    },
  }

  return (
    <div
      ref={barRef}
      className="flex items-center h-[34px] bg-[#0d0d1a] select-none shrink-0"
      style={{ appRegion: 'drag', WebkitAppRegion: 'drag' } as any}
      onDoubleClick={handleDoubleClick}
    >
      {/* ── App Icon (煎蛋) ── */}
      <div className="flex items-center gap-1.5 pl-3 pr-2">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e6b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3C7 3 3.5 6 3.5 10c0 3 1.5 5.5 3.5 7s3.5 3 5 3 4-1 5.5-3 2.5-4 2.5-7c0-4-3-7-7.5-7z" />
          <circle cx="12" cy="10" r="4" fill="#f59e6b" stroke="none" />
        </svg>
        <span className="text-xs font-semibold text-gray-300 tracking-wide">煎蛋</span>
      </div>

      {/* ── Menu Items ── */}
      <div className="flex items-center h-full">
        {(Object.entries(menus) as [MenuId, typeof menus[MenuId]][]).map(([id, menu]) => (
          <div key={id} className="relative h-full">
            <button
              className={`px-3 h-full text-xs transition-colors ${
                openMenu === id
                  ? 'bg-[#1e1e3a] text-white'
                  : 'text-gray-400 hover:bg-[#1a1a30] hover:text-gray-200'
              }`}
              style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}
              onClick={() => toggleMenu(id)}
            >
              {menu.label}
            </button>

            {openMenu === id && (
              <div
                className="absolute top-full left-0 z-50 min-w-[180px] py-1"
                style={{
                  background: '#1e1e30',
                  border: '1px solid #2a2a4a',
                }}
              >
                {menu.items.map((item, idx) => {
                  if (item.divider) {
                    return <div key={idx} className="h-[1px] mx-2 my-1 bg-[#2a2a4a]" />
                  }
                  return (
                    <button
                      key={idx}
                      style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}
                      className="w-full px-3 py-1.5 text-left text-xs text-gray-300 hover:bg-[#2a2a4a] hover:text-white transition-colors"
                      onClick={item.action}
                    >
                      {item.label}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ── Temperature slider ── */}
      <div className="flex-1 flex items-center justify-end gap-2 px-4">
        <span className="text-[10px] text-gray-500 whitespace-nowrap shrink-0" title="控制AI回复的创造性：越低越精确，越高越发散">发散</span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={temperature ?? 0.5}
          onChange={(e) => onTemperatureChange?.(parseFloat(e.target.value))}
          className="w-28 h-1.5 cursor-pointer rounded-full appearance-none temp-slider"
          style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}
          style={{
            background: `linear-gradient(to right, #3b82f6, #8b5cf6, #ec4899, #ef4444)`,
          }}
          title={`温度: ${(temperature ?? 0.5).toFixed(2)}`}
        />
        <span className="text-xs font-mono text-gray-300 w-8 text-right shrink-0">
          {(temperature ?? 0.5).toFixed(2)}
        </span>
      </div>

      {/* ── API Config Popover (status dot + edit icon) ── */}
      <div style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}>
        <ApiConfigPopover onSaved={onApiConfigSaved} />
      </div>

      {/* ── Conversation History Popover ── */}
      <div style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}>
        <ConversationPopover
          activeConversationId={activeConversationId ?? null}
          currentProjectPath={currentProjectPath ?? null}
          onSelect={(conv) => onSelectConversation?.(conv)}
          onNewConversation={(conv) => {
            onNewConversation?.(conv)
          }}
          onDeleteConversation={onDeleteConversation}
          refreshKey={refreshKey ?? 0}
        />
      </div>

      {/* ── Skills Popover (standalone, always visible) ── */}
      <div style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}>
        <SkillsPopover />
      </div>

      {/* ── Settings Popover (Theme & Background only) ── */}
      <div className="mr-1" style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}>
        <SettingsPopover
          theme={theme}
          onThemeChange={onThemeChange}
          onBgUpload={(url) => onBgUpload?.(url)}
          onBgRemove={() => onBgRemove?.()}
          hasBg={hasBg ?? false}
        />
      </div>

      {/* ── Window Controls ── */}
      {electronAPI && (
        <div className="flex h-full" style={{ appRegion: 'no-drag', WebkitAppRegion: 'no-drag' } as any}>
          <button
            className="w-[46px] h-full flex items-center justify-center text-gray-400 hover:bg-[#1a1a30] hover:text-white text-xs transition-colors"
            onClick={handleMinimize}
            title="最小化"
          >
            <svg width="12" height="12" viewBox="0 0 12 12">
              <rect x="1" y="5.5" width="10" height="1" fill="currentColor" />
            </svg>
          </button>
          <button
            className="w-[46px] h-full flex items-center justify-center text-gray-400 hover:bg-[#1a1a30] hover:text-white text-xs transition-colors"
            onClick={handleMaximize}
            title={isMaximized ? '还原' : '最大化'}
          >
            {isMaximized ? (
              <svg width="12" height="12" viewBox="0 0 12 12">
                <rect x="2.5" y="0.5" width="9" height="9" rx="1" fill="none" stroke="currentColor" strokeWidth="1" />
                <rect x="0.5" y="2.5" width="9" height="9" rx="1" fill="#0d0d1a" stroke="currentColor" strokeWidth="1" />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 12 12">
                <rect x="1" y="1" width="10" height="10" rx="1" fill="none" stroke="currentColor" strokeWidth="1" />
              </svg>
            )}
          </button>
          <button
            className="w-[46px] h-full flex items-center justify-center text-gray-400 hover:bg-red-500 hover:text-white text-xs transition-colors"
            onClick={handleClose}
            title="关闭"
          >
            <svg width="12" height="12" viewBox="0 0 12 12">
              <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" strokeWidth="1.2" />
              <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" strokeWidth="1.2" />
            </svg>
          </button>
        </div>
      )}
    </div>
  )
}
