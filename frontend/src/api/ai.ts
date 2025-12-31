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
