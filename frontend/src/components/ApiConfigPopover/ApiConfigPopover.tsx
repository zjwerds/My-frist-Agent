import { useState, useEffect, useRef } from 'react'
import type { ApiConfig } from '../../types'
import { apisApi } from '../../api/client'

interface ApiConfigPopoverProps {
  onSaved?: () => void
}

export function ApiConfigPopover({ onSaved }: ApiConfigPopoverProps) {
  const [open, setOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [configId, setConfigId] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com')
  const [model, setModel] = useState('deepseek-v4-flash')
  const [keyModified, setKeyModified] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms?: number } | null>(null)

  // On mount: check backend for existing API config (so status dot is correct on restart)
  useEffect(() => {
    apisApi.list().then((configs: ApiConfig[]) => {
      if (configs.length > 0) {
        setConfigured(configs[0].api_key.length > 0)
      }
    }).catch(() => {})
  }, [])

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

  // Load API config when popover opens
  useEffect(() => {
    if (!open) return
    setTestResult(null)
    apisApi.list().then((configs: ApiConfig[]) => {
      if (configs.length > 0) {
        const c = configs[0]
        setConfigId(c.id)
        setApiKey(c.api_key)
        setBaseUrl(c.base_url)
        setModel(c.model)
        setConfigured(c.api_key.length > 0)
      }
    }).catch(() => {})
  }, [open])

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await apisApi.test({ api_key: apiKey, base_url: baseUrl, model })
      setTestResult(res)
    } catch {
      setTestResult({ success: false })
    }
    setTesting(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const data: Record<string, string> = { base_url: baseUrl, model }
      if (keyModified) data.api_key = apiKey
      if (configId) {
        await apisApi.update(configId, data)
      } else {
        await apisApi.create({ name: 'default', provider: 'deepseek', api_key: apiKey, base_url: baseUrl, model })
      }
      setConfigured(true)
      setKeyModified(false)
      onSaved?.()
    } catch (err) {
      console.error('Save failed:', err)
    }
    setSaving(false)
  }

  const handleClear = async () => {
    if (!configId) return
    try {
      await apisApi.delete(configId)
      setConfigId(null)
      setApiKey('')
      setBaseUrl('https://api.deepseek.com')
      setModel('deepseek-v4-flash')
      setConfigured(false)
    } catch (err) {
      console.error('Clear failed:', err)
    }
  }

  return (
    <div ref={popoverRef} className="relative">
      {/* Trigger: API status dot + lock icon */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors hover:bg-black/10 hover:shadow-[0_0_8px_rgba(245,158,107,0.15)]"
        title={configured ? `API 已配置 (${model})` : 'API 未配置 — 点击配置'}
      >
        <span className={`relative flex w-2.5 h-2.5 shrink-0 ${configured ? 'text-green-400' : 'text-gray-500'}`}>
          <span className={`absolute inset-0 rounded-full ${configured ? 'bg-green-400' : 'bg-gray-500'}`} />
          {configured && (
            <span className="absolute inset-0 rounded-full bg-green-400 animate-ping opacity-30" style={{ animationDuration: '3s' }} />
          )}
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={configured ? 'text-green-400' : 'text-gray-400'}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      </button>

      {/* Popover */}
      {open && (
        <div
          className="absolute top-full right-0 z-50 w-[280px] mt-1 overflow-hidden glass-sm rounded-2xl"
        >
          <div className="p-3 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">状态:</span>
              <span className={`text-xs ${configured ? 'text-green-400' : 'text-gray-500'}`}>
                {configured ? `已配置 (${model})` : '未配置'}
              </span>
            </div>
            <div>
              <label className="text-[10px] text-gray-500 block mb-1">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setKeyModified(true) }}
                className="w-full bg-white/10 backdrop-blur-[40px] border border-white/15 rounded-2xl px-2 py-1.5 text-xs text-gray-200 outline-none focus:border-white/30 placeholder:text-gray-600"
                placeholder="sk-..."
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 block mb-1">Base URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className="w-full bg-white/10 backdrop-blur-[40px] border border-white/15 rounded-2xl px-2 py-1.5 text-xs text-gray-200 outline-none focus:border-white/30"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 block mb-1">模型</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSave() }}
                className="w-full bg-white/10 backdrop-blur-[40px] border border-white/15 rounded-2xl px-2 py-1.5 text-xs text-gray-200 outline-none focus:border-white/30"
              />
            </div>
            <div className="flex gap-2 pt-1">
              <button
                onClick={handleTest}
                disabled={testing || !apiKey}
                className="flex-1 px-3 py-1.5 text-xs rounded-2xl bg-white/10 text-gray-300 hover:bg-white/20 transition-colors disabled:opacity-40"
              >
                {testing ? '测试中...' : '测试连接'}
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !apiKey}
                className="flex-1 px-3 py-1.5 text-xs rounded text-white transition-colors disabled:opacity-40"
                style={{ backgroundColor: 'var(--accent)' }}
              >
                {saving ? '保存中...' : '保存'}
              </button>
            </div>
            {testResult && (
              <div className={`text-xs ${testResult.success ? 'text-green-400' : 'text-red-400'}`}>
                {testResult.success
                  ? `连接成功 (${testResult.latency_ms}ms)`
                  : '连接失败，请检查配置'}
              </div>
            )}
            {configured && (
              <button onClick={handleClear} className="text-[10px] text-gray-500 hover:text-red-400 transition-colors">
                清除配置
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
