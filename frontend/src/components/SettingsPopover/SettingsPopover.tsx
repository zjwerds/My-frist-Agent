import { useState, useEffect, useRef } from 'react'

interface SettingsPopoverProps {
  theme: string
  onThemeChange: (theme: string) => void
  onBgUpload: (dataUrl: string) => void
  onBgRemove: () => void
  hasBg: boolean
}

const THEMES = ['theme1', 'theme2', 'theme3'] as const
const THEME_LABELS: Record<string, string> = { theme1: '深邃蓝黑', theme2: '极简黑白', theme3: '暗紫橙金' }

export function SettingsPopover({ theme, onThemeChange, onBgUpload, onBgRemove, hasBg }: SettingsPopoverProps) {
  const [open, setOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handleClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) setOpen(false)
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

  return (
    <div ref={popoverRef} className="relative">
      {/* Settings gear icon */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${
          open ? 'bg-black/15 text-gray-900' : 'text-gray-500 hover:bg-black/10 hover:text-gray-700'
        }`}
        title="主题与背景"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      </button>

      {/* Popover panel */}
      {open && (
        <div
          className="absolute top-full right-0 z-50 w-[280px] mt-1 overflow-hidden glass-sm rounded-2xl"
        >
          <div className="p-3 space-y-4">
            {/* Theme */}
            <div>
              <label className="text-[10px] text-gray-500 block mb-2">主题</label>
              <div className="flex gap-3">
                {THEMES.map((t) => (
                  <button
                    key={t}
                    onClick={() => onThemeChange(t)}
                    className={`flex flex-col items-center gap-1.5 px-3 py-2 rounded-lg transition-colors flex-1 ${
                      theme === t ? 'bg-white/15' : 'hover:bg-white/10'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 rounded-full border-2 transition-all ${
                        theme === t ? 'border-white scale-110' : 'border-transparent'
                      }`}
                      style={{
                        backgroundColor:
                          t === 'theme1' ? '#3b82f6' : t === 'theme2' ? '#ff006e' : '#e94560',
                      }}
                    />
                    <span className="text-[10px] text-gray-400">{THEME_LABELS[t]}</span>
                  </button>
                ))}
              </div>
            </div>
            {/* Background */}
            <div>
              <label className="text-[10px] text-gray-500 block mb-2">背景图片</label>
              <div className="flex gap-2">
                <label className="flex-1 px-3 py-1.5 text-xs rounded-2xl bg-white/10 text-gray-300 hover:bg-white/20 cursor-pointer transition-colors text-center">
                  {hasBg ? '更换图片' : '选择图片'}
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        const reader = new FileReader()
                        reader.onload = (ev) => ev.target?.result && onBgUpload(ev.target.result as string)
                        reader.readAsDataURL(file)
                      }
                    }}
                  />
                </label>
                {hasBg && (
                  <button
                    onClick={onBgRemove}
                    className="px-3 py-1.5 text-xs rounded-2xl bg-white/10 text-red-400 hover:bg-white/20 transition-colors"
                  >
                    移除
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
