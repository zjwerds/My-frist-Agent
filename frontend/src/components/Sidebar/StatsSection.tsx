import { useState, useEffect, useCallback } from 'react'

const STATS_URL = 'http://127.0.0.1:8000/api/stats'

interface Stats {
  balance?: string
  currency?: string
  total_prompt_tokens: number
  total_completion_tokens: number
  total_tokens: number
  total_cache_hit_tokens: number
  cache_hit_rate: number
  session_count: number
}

function WalletIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M21 12V7H5a2 2 0 010-4h14v4" />
      <path d="M3 5v14a2 2 0 002 2h16v-5" />
      <path d="M18 12a2 2 0 000 4h4v-4h-4z" />
    </svg>
  )
}

function BarChartIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  )
}

function ZapIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 11-2.12-9.36L23 10" />
    </svg>
  )
}

export function StatsSection() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(STATS_URL)
      if (res.ok) {
        setStats(await res.json())
        setFetchError(null)
      } else {
        setFetchError(`请求失败 (${res.status})`)
      }
    } catch (e) {
      setFetchError(e instanceof Error ? e.message : '网络错误')
    }
  }, [])

  useEffect(() => {
    fetchStats()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [fetchStats])

  const formatNum = (n: number) => n.toLocaleString('zh-CN')

  return (
    <div className="rounded-lg overflow-hidden pt-2">
      <div className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-300">
        <svg className="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3.5C7.5 3.5 4.5 6 4.5 9.5c0 2.5 1 4.5 2.5 6s3 2.5 5 2.5 3.5-.8 5-2.5 2.5-3.5 2.5-6c0-3.5-2.5-6-7-6z" />
          <circle cx="12" cy="9" r="3" fill="currentColor" opacity="0.6" stroke="none" />
        </svg>
        <span>煎蛋状态</span>
      </div>
      <div className="px-3 pb-2">
        {!stats ? (
          fetchError ? (
            <div className="text-xs text-red-400 text-center py-2">{fetchError}</div>
          ) : (
            <div className="flex items-center justify-center gap-1.5 text-xs text-gray-500 py-2">
              <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
                <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" opacity="0.6" />
              </svg>
              加载中...
            </div>
          )
        ) : (
          <div className="space-y-2.5">
            {/* Balance */}
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-gray-400">
                <WalletIcon />
                <span>余额</span>
              </div>
              <span className="text-gray-200 font-medium">
                {stats.balance
                  ? `¥${parseFloat(stats.balance).toFixed(2)}`
                  : '--'}
              </span>
            </div>

            {/* Token Usage */}
            <div className="space-y-0.5">
              <div className="flex items-center gap-1.5 text-[10px] text-gray-500">
                <BarChartIcon />
                <span>Token 用量</span>
              </div>
              <div className="bg-[#1e1e3a]/30 rounded-lg px-2.5 py-1.5 space-y-0.5 border border-[#2a2a4a]/30">
                <div className="flex justify-between text-[11px]">
                  <span className="text-gray-500">Prompt</span>
                  <span className="text-gray-300">{formatNum(stats.total_prompt_tokens)}</span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-gray-500">Completion</span>
                  <span className="text-gray-300">{formatNum(stats.total_completion_tokens)}</span>
                </div>
                <div className="flex justify-between text-[11px] border-t border-[#2a2a4a]/50 pt-0.5 mt-0.5">
                  <span className="text-gray-400 font-medium">总计</span>
                  <span className="text-gray-200 font-medium">{formatNum(stats.total_tokens)}</span>
                </div>
              </div>
            </div>

            {/* Cache Hit Rate */}
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-gray-400">
                <ZapIcon />
                <span>缓存命中率</span>
              </div>
              <span
                className="font-medium"
                style={{ color: stats.cache_hit_rate > 0.3 ? '#4ade80' : '#e2e8f0' }}
              >
                {(stats.cache_hit_rate * 100).toFixed(1)}%
              </span>
            </div>

            {/* Refresh */}
            <button
              onClick={fetchStats}
              className="w-full flex items-center justify-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 pt-0.5 transition-colors"
            >
              <RefreshIcon />
              刷新
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
