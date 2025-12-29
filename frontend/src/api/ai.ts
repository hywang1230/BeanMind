import apiClient from './client'
import axios from 'axios'

// AI 专用 axios 实例，超时时间更长
const aiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
    timeout: 120000,  // 120 秒超时，AI 对话需要更长时间
    headers: {
        'Content-Type': 'application/json'
    }
})

// 请求拦截器 - 添加 token
aiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// 响应拦截器 - 处理错误
aiClient.interceptors.response.use(
    (response) => response.data,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token')
            window.location.href = '/login'
        }
        const errorMessage = error.response?.data?.detail || error.message || '请求失败'
        return Promise.reject({ status: error.response?.status, message: errorMessage })
    }
)

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
     */
    chat(request: ChatRequest): Promise<ChatResponse> {
        return aiClient.post('/api/ai/chat', request)
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
