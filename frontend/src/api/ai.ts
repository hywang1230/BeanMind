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
}

export type QuickQuestion = {
    id: string
    text: string
    icon?: string
}

export type ChatRequest = {
    message: string
    session_id?: string
    history?: Array<{ role: string; content: string }>
}

export type ChatResponse = {
    session_id: string
    message: ChatMessage
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
        onError: (error: string) => void
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
                                    break
                                case 'token':
                                    onToken(data.content)
                                    break
                                case 'done':
                                    onDone(data.message)
                                    break
                                case 'error':
                                    onError(data.error)
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
}

export default aiApi
