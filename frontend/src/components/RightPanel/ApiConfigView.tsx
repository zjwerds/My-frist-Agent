import { useState, useEffect } from 'react'
import { apisApi } from '../../api/client'

interface ApiConfigViewProps {
  onBackToChat: () => void
  onSaved?: () => void
}

const BOOKMARK_STEPS = [
  { title: '访问 platform.deepseek.com 并注册/登录' },
  { title: '进入 API Keys 页面，创建新的 API Key' },
  { title: '复制生成的 Key 粘贴到下方输入框' },
  { title: '点击测试连接验证，然后保存配置' },
]

function BackIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
    </svg>
  )
}

export function ApiConfigView({ onBackToChat, onSaved }: ApiConfigViewProps) {
  const [configId, setConfigId] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://api.deepseek.com')
  const [model, setModel] = useState('deepseek-v4-flash')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; latency_ms: number; error?: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [keyModified, setKeyModified] = useState(false)

  useEffect(() => {
    apisApi.list().then((configs) => {
      if (configs.length > 0) {
        const config = configs[0]
        setConfigId(config.id)
        setApiKey(config.api_key)
        setBaseUrl(config.base_url)
        setModel(config.model)
      }
      setLoaded(true)
    }).catch(() => setLoaded(true))
  }, [])

  const handleTest = async () => {
    if (!apiKey.trim()) return
    setTesting(true)
    setTestResult(null)
    try {
      const result = await apisApi.test({ api_key: apiKey, base_url: baseUrl, model })
      setTestResult(result)
    } catch (err: any) {
      setTestResult({ success: false, latency_ms: 0, error: err.message || '连接失败' })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    if (!apiKey.trim()) return
    setSaving(true)
    try {
      if (configId) {
        const updates: Record<string, string> = { base_url: baseUrl, model }
        if (keyModified) updates.api_key = apiKey
        await apisApi.update(configId, updates)
        setKeyModified(false)
      } else {
        const newConfig = await apisApi.create({
          name: '煎蛋API', provider: 'deepseek',
          api_key: apiKey, base_url: baseUrl, model,
        })
        setConfigId(newConfig.id)
      }
      setSaved(true)
      onSaved?.()
      setTimeout(() => setSaved(false), 3000)
    } catch (err: any) {
      console.error('Save failed:', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full glass">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-white/10">
        <button
          onClick={onBackToChat}
          className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-white transition-colors"
        >
          <BackIcon />
          返回对话
        </button>
        <h2 className="text-base font-medium text-gray-200">API 配置</h2>
        <div className="w-16" />
      </div>

      {/* Status bar */}
      {loaded && (
        <div className={`px-6 py-2 border-b border-white/10 flex items-center gap-2 text-sm ${
          configId ? 'bg-green-500/5' : 'bg-red-500/5'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${configId ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-gray-400">
            {configId ? (
              <>当前模型：<code className="text-accent text-xs font-mono ml-1">{model}</code></>
            ) : (
              '尚未配置 API，请填写并保存'
            )}
          </span>
          {configId && (
            <span className="text-gray-500 text-xs ml-2">{baseUrl}</span>
          )}
          {configId && (
            <button
              onClick={() => { setConfigId(null); setApiKey(''); setModel('deepseek-v4-flash'); setBaseUrl('https://api.deepseek.com') }}
              className="ml-auto text-xs text-gray-500 hover:text-red-400 transition-colors"
            >
              更换配置
            </button>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto p-6 space-y-8">
          {/* Guide */}
          <div className="glass-card p-5">
            <h3 className="text-sm font-medium text-gray-300 mb-3">如何获取 DeepSeek API Key</h3>
            <ol className="space-y-2 text-sm text-gray-400">
              {BOOKMARK_STEPS.map((step, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span className="flex-shrink-0 w-5 h-5 rounded-full bg-accent-dim text-accent text-xs flex items-center justify-center font-medium">
                    {i + 1}
                  </span>
                  <span className="pt-0.5">{step.title}</span>
                </li>
              ))}
            </ol>
          </div>

          {/* Form */}
          <div className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5 font-medium">API Key</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => { setApiKey(e.target.value); setKeyModified(true) }}
                placeholder="sk-..."
                className="w-full bg-white/10 backdrop-blur-[40px] text-gray-200 rounded-2xl px-4 py-2.5 text-sm placeholder-gray-600 outline-none focus:ring-1 focus:ring-white/20 transition-all border border-white/15 focus:border-white/30"
              />
              <p className="text-[10px] text-gray-600 mt-1">API Key 仅保存在本地，不会上传到其他服务器</p>
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-1.5 font-medium">Base URL</label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                className="w-full bg-white/10 backdrop-blur-[40px] text-gray-200 rounded-2xl px-4 py-2.5 text-sm outline-none focus:ring-1 focus:ring-white/20 transition-all border border-white/15 focus:border-white/30"
              />
            </div>

            <div>
              <label className="block text-xs text-gray-400 mb-1.5 font-medium">模型</label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="deepseek-v4-flash"
                className="w-full bg-white/10 backdrop-blur-[40px] text-gray-200 rounded-2xl px-4 py-2.5 text-sm placeholder-gray-600 outline-none focus:ring-1 focus:ring-white/20 transition-all border border-white/15 focus:border-white/30"
              />
              <p className="text-[10px] text-gray-600 mt-1">例如 deepseek-v4-flash、deepseek-reasoner、gpt-4o</p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={handleTest}
              disabled={!apiKey.trim() || testing}
              className="px-5 py-2.5 bg-white/10 backdrop-blur-[40px] text-gray-300 rounded-2xl text-sm hover:bg-white/20 disabled:opacity-40 transition-colors border border-white/15"
            >
              <div className="flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
                {testing ? '测试中...' : '测试连接'}
              </div>
            </button>

            <button
              onClick={handleSave}
              disabled={!apiKey.trim() || saving}
              className="px-5 py-2.5 bg-accent text-[#0d0d1a] rounded-lg text-sm font-medium disabled:opacity-40 transition-all hover:brightness-110"
            >
              {saving ? '保存中...' : saved ? '已保存' : '保存配置'}
            </button>

            {configId && (
              <button
                onClick={async () => {
                  if (!confirm('确定要清除 API 配置吗？')) return
                  try { await apisApi.delete(configId) } catch (_) { console.error('清除配置失败', _) }
                  setConfigId(null)
                  setApiKey('')
                  setBaseUrl('https://api.deepseek.com')
                  setModel('deepseek-v4-flash')
                  setTestResult(null)
                  setKeyModified(false)
                }}
                className="ml-auto px-3 py-2 text-xs text-gray-500 hover:text-red-400 transition-colors"
              >
                清除配置
              </button>
            )}
          </div>

          {/* Test Result */}
          {testResult && (
            <div className={`rounded-2xl px-4 py-3 text-sm backdrop-blur-[40px] border ${
              testResult.success
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}>
              <div className="flex items-center gap-2">
                {testResult.success ? (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                )}
                <span>
                  {testResult.success
                    ? `连接成功 (延迟 ${testResult.latency_ms}ms)`
                    : `连接失败${testResult.error ? `: ${testResult.error}` : ''}`
                  }
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
