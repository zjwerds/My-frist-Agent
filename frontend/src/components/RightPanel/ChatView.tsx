import { useState, useCallback, useEffect, useRef } from 'react'
import type { Message } from '../../types'
import { historyApi, sendChatMessage } from '../../api/client'
import { MessageList } from './MessageList'
import { ChatInput } from './ChatInput'

interface ChatViewProps {
  conversationId: string | null
  onMessageComplete: () => void
  onUsage?: (usage: { prompt_tokens: number; completion_tokens: number; cache_hit_tokens: number }) => void
  onNewConversation?: () => Promise<import('../../types').Conversation>
  temperature: number
  onSwitchConversation?: (conv: import('../../types').Conversation & { messages: import('../../types').Message[] }) => void
}

export function ChatView({ conversationId, onMessageComplete, onUsage, onNewConversation, temperature, onSwitchConversation }: ChatViewProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [streamingContent, setStreamingContent] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [toolStatus, setToolStatus] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const fetchRef = useRef<number>(0) // request counter to avoid race conditions
  const streamingConvRef = useRef<string | null>(null) // track which conversation is currently streaming
  const streamingContentRef = useRef('') // ref to track streaming content reliably

  // Helper to parse message content (plain text or JSON with images)
  const parseMessage = useCallback((raw: any): Message => {
    const msg: Message = {
      id: raw.id,
      role: raw.role,
      content: raw.content || '',
      created_at: raw.created_at,
    }
    if (raw.content && typeof raw.content === 'string') {
      try {
        const parsed = JSON.parse(raw.content)
        if (parsed && typeof parsed === 'object' && 'text' in parsed) {
          msg.content = parsed.text || ''
          msg.images = parsed.images || []
        }
      } catch {
        // plain text, keep as-is
      }
    }
    return msg
  }, [])

  // Cleanup SSE on unmount + abort stale streams on conversation switch
  useEffect(() => {
    // Bump request counter
    fetchRef.current += 1
    const currentFetch = fetchRef.current

    // Don't abort if the same conversation is still streaming (auto-create case)
    if (abortRef.current && streamingConvRef.current !== conversationId) {
      abortRef.current.abort()
      abortRef.current = null
      setIsLoading(false)
    }

    if (conversationId) {
      // Skip history load if SSE is already streaming this conversation
      if (streamingConvRef.current !== conversationId) {
        historyApi.get(conversationId).then((data: any) => {
          // Ignore stale responses from previous conversation switches
          if (currentFetch !== fetchRef.current) return
          if (data.messages) {
            setMessages(data.messages.map(parseMessage))
          }
        }).catch((err) => {
          if (err.name === 'AbortError') return
          if (currentFetch === fetchRef.current) {
            console.error('Failed to load history:', err)
          }
        })
      }
    } else {
      setMessages([])
    }
    // Don't clear streaming if this conversation is already streaming (e.g. auto-create flow)
    if (streamingConvRef.current !== conversationId) {
      setStreamingContent('')
      setToolStatus(null)
    }

    // Cleanup: abort SSE on unmount only if it belongs to this conversation
    // (not on re-render where conversationId changed due to auto-create flow)
    return () => {
      if (abortRef.current && streamingConvRef.current === conversationId) {
        abortRef.current.abort()
        abortRef.current = null
      }
    }
  }, [conversationId, parseMessage])

  // Commit streaming message when done (used by both handleSend and handleEdit)
  const commitStreamingMessage = useCallback(() => {
    const content = streamingContentRef.current
    if (content) {
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])
      setStreamingContent('')
      streamingContentRef.current = ''
    }
  }, [])

  const handleSend = useCallback(async (text: string, images?: string[], fileContext?: string) => {
    if (!text.trim() && (!images || images.length === 0)) return

    // Auto-create conversation if none active
    let convId = conversationId
    if (!convId) {
      if (!onNewConversation) return
      try {
        const conv = await onNewConversation()
        convId = conv.id
      } catch {
        return
      }
    }

    const imageArray = images || []
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      images: imageArray,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)
    setStreamingContent('')
    streamingContentRef.current = ''

    streamingConvRef.current = convId
    const controller = sendChatMessage(
      convId,
      text,
      imageArray,
      // onText
      (text) => {
        streamingContentRef.current += text
        setStreamingContent(streamingContentRef.current)
      },
      // onToolStart
      (toolName, _args) => {
        setToolStatus(`正在调用: ${toolName}...`)
      },
      // onToolResult
      (toolName, _result) => {
        setToolStatus(`✅ ${toolName} 执行完成`)
        setTimeout(() => setToolStatus(null), 2000)
      },
      // onError
      (error) => {
        streamingConvRef.current = null
        commitStreamingMessage()
        const [firstLine] = (error instanceof Error ? error.message : String(error)).split('\n')
        const errorMsg: Message = {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ ${firstLine}`,
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, errorMsg])
        setIsLoading(false)
        setToolStatus(null)
        onMessageComplete()
      },
      // onDone
      () => {
        streamingConvRef.current = null
        commitStreamingMessage()
        setIsLoading(false)
        setToolStatus(null)
        onMessageComplete()
      },
      // onUsage
      onUsage,
      temperature,
      undefined, // edit_mode
      fileContext,
    )

    abortRef.current = controller
  }, [conversationId, onUsage, onMessageComplete, onNewConversation, temperature, commitStreamingMessage])

  const handleEdit = useCallback(async (msgId: string, newContent: string) => {
    if (!conversationId) return
    try {
      // Abort any in-flight stream first
      if (abortRef.current) {
        abortRef.current.abort()
        abortRef.current = null
      }

      await historyApi.editMessage(conversationId, msgId, newContent)
      // Find index of edited message
      const editedIndex = messages.findIndex((m) => m.id === msgId)
      if (editedIndex === -1) return

      // Keep messages up to and including the edited message, with updated content
      const updatedMessages = messages.slice(0, editedIndex + 1).map((m) =>
        m.id === msgId ? { ...m, content: newContent } : m
      )
      setMessages(updatedMessages)

      // Re-invoke SSE with edit_mode=true to regenerate
      setIsLoading(true)
      setStreamingContent('')
      streamingContentRef.current = ''

      streamingConvRef.current = conversationId
      const controller = sendChatMessage(
        conversationId,
        newContent,
        [],
        // onText
        (text) => {
          streamingContentRef.current += text
          setStreamingContent(streamingContentRef.current)
        },
        // onToolStart
        (toolName, _args) => {
          setToolStatus(`正在调用: ${toolName}...`)
        },
        // onToolResult
        (toolName, _result) => {
          setToolStatus(`✅ ${toolName} 执行完成`)
          setTimeout(() => setToolStatus(null), 2000)
        },
        // onError
        (error) => {
          streamingConvRef.current = null
          const [firstLine] = (error instanceof Error ? error.message : String(error)).split('\n')
          const errorMsg: Message = {
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `⚠️ ${firstLine}`,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, errorMsg])
          setIsLoading(false)
          setStreamingContent('')
          streamingContentRef.current = ''
          setToolStatus(null)
          onMessageComplete()
        },
        // onDone
        () => {
          streamingConvRef.current = null
          commitStreamingMessage()
          setIsLoading(false)
          setToolStatus(null)
          onMessageComplete()
        },
        onUsage,
        temperature,
        true, // edit_mode=true
      )
      abortRef.current = controller
    } catch (err) {
      console.error('Edit failed:', err)
    }
  }, [conversationId, messages, onUsage, onMessageComplete, temperature, commitStreamingMessage])

  const handleCancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    streamingConvRef.current = null
    streamingContentRef.current = ''
    setStreamingContent('')
    setIsLoading(false)
    setToolStatus(null)
  }, [])

  const handleBranch = useCallback(async (msgId: string) => {
    if (!conversationId) return
    try {
      const result = await historyApi.branch(conversationId, msgId)
      onSwitchConversation?.(result)
    } catch (err) {
      console.error('Branch failed:', err)
    }
  }, [conversationId, onSwitchConversation])

  return (
    <div className="flex flex-col h-full">

      {/* Messages area - flex-1 to fill space */}
      <div className="flex-1 overflow-hidden">
        <MessageList
          messages={messages}
          streamingContent={streamingContent}
          isLoading={isLoading}
          toolStatus={toolStatus}
          onEdit={handleEdit}
          onBranch={handleBranch}
        />
      </div>

      {/* Input area - fixed at bottom */}
      <ChatInput
        onSend={handleSend}
        isLoading={isLoading}
        onCancel={handleCancel}
      />
    </div>
  )
}
