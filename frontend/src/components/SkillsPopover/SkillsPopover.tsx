import { useState, useEffect, useRef } from 'react'
import type { Skill } from '../../types'
import { skillsApi } from '../../api/client'

export function SkillsPopover() {
  const [open, setOpen] = useState(false)
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  // Load skills when popover opens
  useEffect(() => {
    if (!open) return
    setLoading(true)
    skillsApi.list().then(setSkills).catch(() => {}).finally(() => setLoading(false))
  }, [open])

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

  const handleToggle = async (skillId: string) => {
    const skill = skills.find((s) => s.id === skillId)
    if (!skill) return
    try {
      await skillsApi.toggle(skillId, !skill.enabled)
      setSkills((prev) => prev.map((s) => s.id === skillId ? { ...s, enabled: !s.enabled } : s))
    } catch (err) {
      console.error('Toggle skill failed:', err)
    }
  }

  const handleRemove = async (skillId: string) => {
    try {
      await skillsApi.remove(skillId)
      setSkills((prev) => prev.filter((s) => s.id !== skillId))
    } catch (err) {
      console.error('Remove skill failed:', err)
    }
  }

  // Group by category
  const catNames = [...new Set(skills.map((s) => s.category))]
  const grouped = catNames.map((name) => ({
    name,
    skills: skills.filter((s) => s.category === name),
  })).filter((g) => g.skills.length > 0)

  return (
    <div ref={popoverRef} className="relative">
      {/* Skills icon — more visible, with accent color hint */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-7 h-7 flex items-center justify-center rounded transition-colors ${
          open
            ? 'bg-[#2a2a4a] text-white'
            : 'text-gray-400 hover:bg-[#1a1a30] hover:text-gray-200'
        }`}
        title="Skill 管理"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      </button>

      {/* Popover panel */}
      {open && (
        <div
          className="absolute top-full right-0 z-50 w-[320px] mt-1 overflow-hidden"
          style={{
            background: '#1a1a30',
            border: '1px solid #2a2a4a',
            borderRadius: '8px',
          }}
        >
          {/* Header */}
          <div className="px-3 py-2 border-b border-[#2a2a4a] flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              <span className="text-xs font-medium text-gray-300">Skill 管理</span>
            </div>
            <span className="text-[10px] text-gray-500">{skills.length} 个已安装</span>
          </div>

          {/* Skills list */}
          <div className="max-h-[300px] overflow-y-auto hide-scrollbar p-1">
            {loading && skills.length === 0 && (
              <div className="px-3 py-6 text-xs text-gray-500 text-center">加载中...</div>
            )}
            {!loading && skills.length === 0 && (
              <div className="px-3 py-6 text-xs text-gray-500 text-center">暂无安装的 Skill</div>
            )}
            {grouped.map((cat) => (
              <div key={cat.name}>
                <div className="px-2 py-1.5 text-[10px] text-gray-500 font-medium tracking-wide uppercase">
                  {cat.name}
                </div>
                {cat.skills.map((skill) => (
                  <div
                    key={skill.id}
                    className="group flex items-center justify-between px-2 py-1.5 rounded text-xs text-gray-400 hover:bg-[#1e1e3a] transition-colors"
                  >
                    <div className="flex-1 min-w-0 flex items-center gap-2">
                      <span className="truncate">{skill.name}</span>
                      {skill.builtin && (
                        <span className="text-[9px] text-gray-600 px-1 rounded bg-[#2a2a4a] shrink-0">内置</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {!skill.builtin && (
                        <button
                          onClick={() => handleRemove(skill.id)}
                          className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-0.5"
                          title="卸载"
                        >
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={skill.enabled}
                          onChange={() => handleToggle(skill.id)}
                          className="sr-only peer"
                        />
                        <div className="w-7 h-3.5 bg-[#3a3a5a] rounded-full peer peer-checked:bg-[#4fc3f7] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:after:translate-x-[14px]" />
                      </label>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
