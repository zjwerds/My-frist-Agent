export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  images?: string[]   // base64 data URIs, only for user messages
  tool_calls?: ToolCall[]
  created_at: string
}

export interface ToolCall {
  id: string
  type: 'function'
  function: {
    name: string
    arguments: string
  }
}

export interface Conversation {
  id: string
  title: string
  project_path?: string | null
  created_at: string
  updated_at: string
  message_count: number
}

export interface Skill {
  id: string
  name: string
  description: string
  category: string
  enabled: boolean
  builtin: boolean
  config?: string
}

export interface SkillCategory {
  name: string
  icon: string
  skills: Skill[]
}

export interface ApiConfig {
  id: string
  name: string
  provider: string
  api_key: string
  base_url: string
  model: string
  is_active: boolean
  created_at: string
}

export type RightView = 'chat' | 'api-config'

export interface FileEntry {
  name: string
  path: string
  type: 'dir' | 'file'
  size: number
  ext: string
}

export interface FileContent {
  path: string
  name: string
  ext: string
  size: number
  content: string
  truncated: boolean
  lines: number
  binary?: boolean
  binary_type?: 'document' | 'image'
}
