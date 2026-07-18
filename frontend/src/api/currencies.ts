import apiClient from './client'

export type CurrencyItem = {
  code: string
  name: string
  symbol?: string | null
  enabled: boolean
  sort_order: number
  in_use?: boolean
  is_operating?: boolean
  created_at?: string | null
  updated_at?: string | null
}

export type CurrencyListResponse = {
  currencies: CurrencyItem[]
  total: number
}

export type CreateCurrencyRequest = {
  code: string
  name: string
  symbol?: string | null
  enabled?: boolean
  sort_order?: number | null
}

export type UpdateCurrencyRequest = {
  name?: string
  symbol?: string | null
  enabled?: boolean
  sort_order?: number | null
}

export const currenciesApi = {
  async list(enabledOnly = false): Promise<CurrencyItem[]> {
    const response: CurrencyListResponse = await apiClient.get('/api/currencies', {
      params: { enabled_only: enabledOnly },
    })
    return response.currencies
  },

  async listEnabledCodes(): Promise<string[]> {
    const items = await this.list(true)
    return items.map((item) => item.code)
  },

  create(data: CreateCurrencyRequest): Promise<CurrencyItem> {
    return apiClient.post('/api/currencies', data)
  },

  update(code: string, data: UpdateCurrencyRequest): Promise<CurrencyItem> {
    return apiClient.patch(`/api/currencies/${encodeURIComponent(code)}`, data)
  },

  delete(code: string): Promise<void> {
    return apiClient.delete(`/api/currencies/${encodeURIComponent(code)}`)
  },
}
