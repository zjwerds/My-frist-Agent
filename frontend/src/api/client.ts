import type { Conversation, Skill, ApiConfig } from '../types'

const BASE_URL = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

// Skills
export const skillsApi = {
  list: () => request<Skill[]>('/skills'),
  toggle: (id: string, enabled: boolean) =>
    request<Skill>(`/skills/${id}/toggle`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  remove: (id: string) =>
    request<void>(`/skills/${id}`, { method: 'DELETE' }),
  autoCategorize: () =>
    request<{ reclassified: number }>('/skills/auto-categorize', {
      method: 'POST',
    }),
}

// History
export const historyApi = {
  list: (project_path?: string) => {
    const params = project_path ? `?project_path=${encodeURIComponent(project_path)}` : ''
    return request<Conversation[]>(`/history${params}`)
  },
  get: (id: string) => request(`/history/${id}`),
  create: (project_path?: string) =>
    request<Conversation>('/history', {
      method: 'POST',
      body: project_path ? JSON.stringify({ project_path }) : undefined,
    }),
  delete: (id: string) =>
    request<void>(`/history/${id}`, { method: 'DELETE' }),
  editMessage: (convId: string, msgId: string, content: string) =>
    request<any>(`/history/${convId}/messages/${msgId}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
  branch: (convId: string, fromMsgId: string) =>
    request<any>(`/history/${convId}/branch?from_msg_id=${encodeURIComponent(fromMsgId)}`, {
      method: 'POST',
    }),
}

// APIs
export const apisApi = {
  list: () => request<ApiConfig[]>('/apis'),
  create: (data: Partial<ApiConfig>) =>
    request<ApiConfig>('/apis', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (id: string, data: Partial<ApiConfig>) =>
    request<ApiConfig>(`/apis/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/apis/${id}`, { method: 'DELETE' }),
  test: (data: { api_key: string; base_url: string; model: string }) =>
    request<{ success: boolean; latency_ms: number }>('/apis/test', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
}

// File upload & parse
export interface FileParseResult {
  filename: string
  text: string
  pages?: number
  paragraphs?: number
  sheets?: number
  rows?: number
  size: number
  time_ms: number
  warning?: string
}

export async function uploadAndParseFile(file: File): Promise<FileParseResult> {
  const formData = new FormData()
  formData.append('file', file)

  const resp = await fetch(`${BASE_URL}/upload/parse-file`, {
    method: 'POST',
    body: formData,
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || '文件解析失败')
  }

  return resp.json()
}

// Chat (SSE)
export function sendChatMessage(
  conversationId: string,
  message: string,
  images: string[],
  onText: (text: string) => void,
  onToolStart: (toolName: string, args: string) => void,
  onToolResult: (toolName: string, result: string) => void,
  onError: (error: Error) => void,
  onDone: () => void,
  onUsage?: (usage: { prompt_tokens: number; completion_tokens: number; cache_hit_tokens: number }) => void,
  temperature?: number,
  edit_mode?: boolean,
): AbortController {
  const controller = new AbortController()
  let isTimedOut = false

  // 120s timeout — abort the fetch if no response received within this time
  const timeoutId = setTimeout(() => {
    isTimedOut = true
    controller.abort()
  }, 120000)

  fetch(`${BASE_URL}/chat?conversation_id=${conversationId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      images: images.length > 0 ? images : undefined,
      temperature: temperature !== undefined ? temperature : undefined,
      edit_mode: edit_mode || undefined,
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      clearTimeout(timeoutId)
      let completed = false
      try {
        if (!response.ok) {
          onError(new Error(`HTTP ${response.status}`))
          return
        }
        const reader = response.body?.getReader()
        if (!reader) {
          onError(new Error('No response body'))
          return
        }

        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (trimmed.startsWith('event: ')) {
              currentEvent = trimmed.slice(7).trim()
            } else if (trimmed.startsWith('data: ')) {
              const data = trimmed.slice(6).trim()
              if (data === '[DONE]') {
                completed = true
                break
              }
              try {
                const parsed = JSON.parse(data)
                switch (currentEvent) {
                  case 'text_chunk':
                    onText(parsed.content || '')
                    break
                  case 'tool_call_start':
                    onToolStart(parsed.tool_name || '', parsed.arguments || '')
                    break
                  case 'tool_call_result':
                    onToolResult(parsed.tool_name || '', parsed.result || '')
                    break
                  case 'error':
                    onError(new Error(parsed.error || 'Unknown error'))
                    break
                  case 'usage':
                    onUsage?.(parsed)
                    break
                }
              } catch {
                // ignore parse errors
              }
            }
          }
          if (completed) break
        }
      } finally {
        if (!completed) onDone()
      }
    })
    .catch((err) => {
      clearTimeout(timeoutId)
      if (err.name !== 'AbortError') {
        onError(err)
      } else if (isTimedOut) {
        onError(new Error('请求超时（120秒），请重试或简化任务'))
      }
      // Ensure onDone is always called so UI doesn't hang
      onDone()
    })

  return controller
}

// File explorer
import type { FileEntry, FileContent } from '../types'
export const filesApi = {
  listDir: (path: string, root?: string) => {
    const params = new URLSearchParams({ path })
    if (root) params.set('root', root)
    return request<{ path: string; parent: string | null; entries: FileEntry[] }>(`/files?${params}`)
  },
  readFile: (path: string, root?: string) => {
    const params = new URLSearchParams({ path })
    if (root) params.set('root', root)
    return request<FileContent>(`/files/read?${params}`)
  },
  createDir: (path: string, root?: string) => {
    const params = root ? `?root=${encodeURIComponent(root)}` : ''
    return request<{ success: boolean; path: string }>(`/files/create-dir${params}`, {
      method: 'POST',
      body: JSON.stringify({ path }),
    })
  },
  createFile: (path: string, content: string = '', root?: string) => {
    const params = root ? `?root=${encodeURIComponent(root)}` : ''
    return request<{ success: boolean; path: string }>(`/files/create-file${params}`, {
      method: 'POST',
      body: JSON.stringify({ path, content }),
    })
  },
}
