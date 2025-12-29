import apiClient from './client'

// 类型定义
export type MessageRole = 'user' | 'assistant' | 'system'

export type ChatMessage = {
    id: string
    role: MessageRole
    content: string
    created_at: string
    is_streaming?: boolean
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

export type StreamChunk = {
    type: 'chunk' | 'done' | 'error'
    content: string
    session_id?: string
    message_id?: string
}

// 回调类型
export type StreamCallbacks = {
    onChunk?: (chunk: StreamChunk) => void
    onDone?: (fullContent: string, sessionId: string, messageId: string) => void
    onError?: (error: string) => void
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
     * 流式对话
     * 
     * @param request 聊天请求
     * @param callbacks 流式回调函数
     * @returns AbortController 用于取消请求
     */
    chatStream(request: ChatRequest, callbacks: StreamCallbacks): AbortController {
        const abortController = new AbortController()
        
        const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
        const token = localStorage.getItem('token')
        
        fetch(`${baseUrl}/api/ai/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            body: JSON.stringify(request),
            signal: abortController.signal,
        })
        .then(async (response) => {
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: '请求失败' }))
                callbacks.onError?.(error.detail || '请求失败')
                return
            }
            
            const reader = response.body?.getReader()
            if (!reader) {
                callbacks.onError?.('无法读取响应流')
                return
            }
            
            const decoder = new TextDecoder()
            let fullContent = ''
            let sessionId = request.session_id || ''
            let messageId = ''
            
            try {
                while (true) {
                    const { done, value } = await reader.read()
                    if (done) break
                    
                    const text = decoder.decode(value, { stream: true })
                    const lines = text.split('\n')
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6)) as StreamChunk
                                
                                if (data.session_id) sessionId = data.session_id
                                if (data.message_id) messageId = data.message_id
                                
                                if (data.type === 'chunk') {
                                    fullContent += data.content
                                    callbacks.onChunk?.(data)
                                } else if (data.type === 'done') {
                                    // 使用服务端返回的完整内容
                                    if (data.content) fullContent = data.content
                                    callbacks.onDone?.(fullContent, sessionId, messageId)
                                } else if (data.type === 'error') {
                                    callbacks.onError?.(data.content)
                                }
                            } catch (e) {
                                // 忽略解析错误
                                console.warn('解析 SSE 数据失败:', line)
                            }
                        }
                    }
                }
            } catch (e) {
                if ((e as Error).name !== 'AbortError') {
                    callbacks.onError?.((e as Error).message)
                }
            }
        })
        .catch((error) => {
            if (error.name !== 'AbortError') {
                callbacks.onError?.(error.message)
            }
        })
        
        return abortController
    },

    /**
     * 同步对话（非流式）
     */
    chatSync(request: ChatRequest): Promise<ChatResponse> {
        return apiClient.post('/api/ai/chat/sync', request)
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

