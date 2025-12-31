import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
    // 使用 ?? 而不是 ||，这样空字符串不会被视为 falsy
    // 空字符串表示使用相对路径（适用于前后端同域部署）
    baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 请求拦截器
apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        // 动态导入 authStore 以避免循环依赖
        const token = localStorage.getItem('token')
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`
        }
        return config
    },
    (error: AxiosError) => {
        return Promise.reject(error)
    }
)

// 响应拦截器
apiClient.interceptors.response.use(
    (response) => {
        return response.data
    },
    async (error: AxiosError) => {
        // 处理 401 未授权错误
        if (error.response?.status === 401) {
            localStorage.removeItem('token')
            window.location.href = '/login'
        }

        // 处理其他错误
        const errorMessage = (error.response?.data as any)?.detail || error.message || '请求失败'

        return Promise.reject({
            status: error.response?.status,
            message: errorMessage
        })
    }
)

export default apiClient
