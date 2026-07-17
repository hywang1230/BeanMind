import axios, { type AxiosError, type AxiosInstance } from 'axios'

export type ApiError = {
  status?: number
  code: string
  message: string
  details?: Record<string, unknown> | null
}

const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.response.use(
  response => response.data,
  (error: AxiosError) => {
    const payload = (error.response?.data || {}) as Record<string, any>
    const detail = typeof payload.detail === 'object' ? payload.detail : undefined
    const normalized: ApiError = {
      status: error.response?.status,
      code: payload.code || detail?.code || 'REQUEST_FAILED',
      message: payload.message || detail?.message || payload.detail || error.message || '请求失败',
      details: payload.details || detail?.details || null,
    }
    return Promise.reject(normalized)
  },
)

export default apiClient
