import { useRef, useEffect } from 'react'

interface ChangelogEntry {
  version: string
  date: string
  items: { type: 'add' | 'fix' | 'change'; text: string }[]
}

const CHANGELOG: ChangelogEntry[] = [
  {
    version: '2.0.0',
    date: '2026-07-08',
    items: [
      { type: 'fix', text: '菜单栏改为不透明浅色背景，字体改为深色提升可读性' },
      { type: 'fix', text: '下拉菜单面板改为不透明白色毛玻璃背景，深色文字' },
      { type: 'fix', text: '侧边栏分隔线加粗加深，左右区域界限更清晰' },
      { type: 'fix', text: '背景图模式：大幅降低 glass blur（60px→15-20px）和 opacity（8-12%→15-20%），让背景图片清晰可见' },
      { type: 'change', text: '配色方案替换为 3 套全新主题：深邃蓝黑、极简黑白、暗紫橙金' },
      { type: 'change', text: '默认主题从暖白杏橙改为深邃蓝黑（theme1）' },
      { type: 'change', text: '全局 UI 翻新为 Liquid Glass 设计系统（Apple WWDC25 风格）' },
      { type: 'change', text: '菜单栏：液态玻璃背景 backdrop-blur-[60px] + 毛玻璃下拉面板' },
      { type: 'change', text: '侧边栏：glass 背景替换旧暗色背景' },
      { type: 'change', text: '消息气泡：AI 回复 + 代码块工具栏改用 glass-sm 样式' },
      { type: 'change', text: '输入框：毛玻璃输入框 backdrop-blur-[40px]，圆角统一 rounded-2xl' },
      { type: 'change', text: '所有弹出面板（对话历史/Skill管理/设置/API配置）：glass-sm 面板' },
      { type: 'change', text: '文件管理器/统计面板/文件查看器：玻璃化背景与边框' },
      { type: 'change', text: 'API 配置页：毛玻璃输入框与按钮，统一 rounded-2xl' },
      { type: 'change', text: '更新日志弹窗：glass-sm 面板' },
      { type: 'change', text: '全局动效统一为 spring 缓动（duration-500 ease-[cubic-bezier(0.16,1,0.3,1)]）' },
      { type: 'change', text: '所有分隔线、边框从暗色（#2a2a4a）改为白色半透明（white/10）' },
    ],
  },
  {
    version: '1.0.1',
    date: '2026-07-07',
    items: [
      { type: 'fix', text: '移除 max_tokens 硬编码，长回答不再被静默截断' },
      { type: 'fix', text: '增大默认 timeout 至 120s，减少超时断流' },
      { type: 'fix', text: '新增 finish_reason 检测，截断时给出明确提示' },
      { type: 'fix', text: '移除 skill 缓存，新建 skill 立即出现在管理栏' },
      { type: 'fix', text: '删除 find_skills 不存在的假工具引用' },
      { type: 'fix', text: '修复 npx 安装 skill 后不显示的问题' },
      { type: 'change', text: 'taste-skill 添加 .json 注册文件，纳入体系管理' },
    ],
  },
  {
    version: '1.0.0',
    date: '2026-07-06',
    items: [
      { type: 'add', text: '代码语法高亮（react-syntax-highlighter）' },
      { type: 'add', text: '保存代码块为文件' },
      { type: 'add', text: '启动时无启用 skill 的提醒' },
      { type: 'add', text: '捏蛋神器（nvwa）—— AI 驱动的 skill 创建流程' },
      { type: 'add', text: '查蛋神器（find-skills）—— skills.sh 搜索与安装' },
      { type: 'add', text: '图片 OCR 文字识别' },
      { type: 'add', text: '对话记忆压缩与检索' },
      { type: 'add', text: '22 个内置函数工具（代码审查、翻译、正则、数据库查询等）' },
      { type: 'add', text: '顶部菜单栏' },
      { type: 'add', text: '对话历史管理' },
      { type: 'add', text: '技能管理面板' },
      { type: 'add', text: 'API 配置面板' },
      { type: 'add', text: 'Temperature 调节滑块' },
    ],
  },
]

function TypeBadge({ type }: { type: ChangelogEntry['items'][0]['type'] }) {
  const styles = {
    add: 'bg-emerald-500/20 text-emerald-400',
    fix: 'bg-amber-500/20 text-amber-400',
    change: 'bg-blue-500/20 text-blue-400',
  }
  const labels = { add: '新增', fix: '修复', change: '优化' }
  return (
    <span className={`inline-block w-10 text-[10px] font-semibold text-center rounded ${styles[type]}`}>
      {labels[type]}
    </span>
  )
}

interface ChangelogModalProps {
  onClose: () => void
}

export function ChangelogModal({ onClose }: ChangelogModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[1px] bg-black/50"
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
    >
      <div
        className="w-[560px] max-h-[80vh] overflow-y-auto rounded-2xl glass-sm"
      >
        {/* Header — sticky, always visible */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-3 border-b border-white/10 glass-sm rounded-t-2xl">
          <h2 className="text-sm font-semibold text-gray-200">更新日志</h2>
          <button
            className="-mr-3 w-10 h-10 flex items-center justify-center rounded-lg text-gray-400 hover:text-white hover:bg-white/15 active:bg-white/20 transition-colors"
            onClick={onClose}
            title="关闭"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-6">
          {CHANGELOG.map((entry) => (
            <div key={entry.version}>
              <div className="flex items-baseline gap-3 mb-3">
                <span className="text-sm font-bold text-white">v{entry.version}</span>
                <span className="text-[11px] text-gray-500">{entry.date}</span>
              </div>
              <ul className="space-y-1.5">
                {entry.items.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-gray-300">
                    <TypeBadge type={item.type} />
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
