import apiClient from './client'

// 类型定义
export type MessageRole = 'user' | 'assistant' | 'system'

export type ChatMessage = {
    id: string
    role: MessageRole
    content: string
    created_at: string
}

export type ChatSession = {
    id: string
    title?: string
    messages: ChatMessage[]
    created_at: string
    updated_at: string
    message_count: number
    pending_action?: {
        action_type: string
        draft: Record<string, unknown>
        missing_fields?: string[]
        confidence?: number
        assumptions?: Record<string, unknown>
    } | null
}

export type ChatSessionSummary = {
    id: string
    title?: string
    created_at: string
    updated_at: string
    message_count: number
    last_message_preview?: string
}

export type QuickQuestion = {
    id: string
    text: string
    icon?: string
}

export type AISkill = {
    id: string
    name: string
    description: string
    agent_id: string
    write_policy: string
}

export type ChatContext = {
    source_page?: string
    selected_entity_id?: string
    date_range?: Record<string, unknown>
}

export type ChatRequest = {
    message: string
    session_id?: string
    history?: Array<{ role: string; content: string }>
    context?: ChatContext
}

export type ChatResponse = {
    session_id: string
    message: ChatMessage
}

export type ResumeSessionRequest = {
    action: 'confirm' | 'cancel' | 'edit'
    draft?: Record<string, unknown>
}

export type StreamEvent =
    | { type: 'session'; session_id: string }
    | { type: 'token'; content: string }
    | { type: 'done'; message: ChatMessage }
    | { type: 'error'; error: string }
    | { type: 'progress'; content?: string; step?: string }
    | { type: 'tool'; tool_name: string; skill_id?: string; payload?: unknown }
    | { type: 'skill'; skill_id: string }
    | { type: 'agent'; agent_id: string }
    | {
        type: 'interrupt'
        session_id: string
        action_type: string
        draft: Record<string, unknown>
        missing_fields?: string[]
        confidence?: number
        assumptions?: Record<string, unknown>
    }

/**
 * AI API 客户端
 */
export const aiApi = {
    /**
     * 获取快捷问题列表
     */
    getQuickQuestions(): Promise<{ questions: QuickQuestion[] }> {
        return apiClient.get('/api/ai/questions')
    },

    /**
     * 获取 Skill 列表
     */
    getSkills(): Promise<{ skills: AISkill[] }> {
        return apiClient.get('/api/ai/skills')
    },

    /**
     * AI 对话
     * 注意：AI 对话需要更长的超时时间（120秒）
     */
    chat(request: ChatRequest): Promise<ChatResponse> {
        return apiClient.post('/api/ai/chat', request, {
            timeout: 120000  // 120 秒超时，AI 对话需要更长时间
        })
    },

    /**
     * AI 流式对话
     * 使用 Server-Sent Events (SSE) 实现实时流式输出
     * 
     * @param request 聊天请求
     * @param onToken 收到 token 时的回调
     * @param onDone 完成时的回调，包含完整的消息对象
     * @param onError 错误时的回调
     * @returns 返回 session_id
     */
    async chatStream(
        request: ChatRequest,
        onToken: (token: string) => void,
        onDone: (message: ChatMessage) => void,
        onError: (error: string) => void,
        onEvent?: (event: StreamEvent) => void
    ): Promise<string> {
        // 获取 baseURL
        const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
        const url = `${baseURL}/api/ai/chat/stream`

        // 获取 token
        const token = localStorage.getItem('token')

        let sessionId = ''

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                },
                body: JSON.stringify(request)
            })

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`)
            }

            const reader = response.body?.getReader()
            if (!reader) {
                throw new Error('无法获取响应流')
            }

            const decoder = new TextDecoder()
            let buffer = ''

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                buffer += decoder.decode(value, { stream: true })

                // 处理 SSE 数据
                const lines = buffer.split('\n')
                buffer = lines.pop() || ''  // 保留不完整的行

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6))

                            switch (data.type) {
                                case 'session':
                                    sessionId = data.session_id
                                    onEvent?.(data as StreamEvent)
                                    break
                                case 'token':
                                    onToken(data.content)
                                    break
                                case 'done':
                                    onDone(data.message)
                                    onEvent?.(data as StreamEvent)
                                    break
                                case 'error':
                                    onError(data.error)
                                    onEvent?.(data as StreamEvent)
                                    break
                                case 'progress':
                                case 'tool':
                                case 'skill':
                                case 'agent':
                                case 'interrupt':
                                    onEvent?.(data as StreamEvent)
                                    break
                            }
                        } catch {
                            // 忽略解析错误
                        }
                    }
                }
            }

            return sessionId

        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : '流式请求失败'
            onError(errorMsg)
            throw error
        }
    },

    /**
     * 获取会话历史
     */
    getSessionHistory(sessionId: string): Promise<ChatSession> {
        return apiClient.get(`/api/ai/sessions/${sessionId}`)
    },

    /**
     * 创建空会话
     */
    createSession(): Promise<ChatSession> {
        return apiClient.post('/api/ai/sessions')
    },

    /**
     * 获取会话列表
     */
    listSessions(): Promise<{ sessions: ChatSessionSummary[]; total: number }> {
        return apiClient.get('/api/ai/sessions')
    },

    /**
     * 删除会话
     */
    deleteSession(sessionId: string): Promise<{ message: string }> {
        return apiClient.delete(`/api/ai/sessions/${sessionId}`)
    },

    /**
     * 清空会话消息
     */
    clearSession(sessionId: string): Promise<{ message: string }> {
        return apiClient.post(`/api/ai/sessions/${sessionId}/clear`)
    },

    /**
     * 恢复待确认草稿
     */
    resumeSession(sessionId: string, request: ResumeSessionRequest): Promise<ChatResponse> {
        return apiClient.post(`/api/ai/sessions/${sessionId}/resume`, request, {
            timeout: 120000
        })
    },
}

export default aiApi
