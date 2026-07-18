import apiClient from './client'

/** 常用账户/分类 */
export type FrequentItem = {
  name: string
  count: number
  last_used: string
}

type FrequentCacheEntry = {
  expiresAt: number
  data: FrequentItem[]
  inflight?: Promise<FrequentItem[]>
}

const FREQUENT_TTL_MS = 60_000
const frequentCache = new Map<string, FrequentCacheEntry>()

function frequentCacheKey(params: {
  type: string
  days?: number
  limit?: number
}): string {
  return `${params.type}|${params.days ?? 30}|${params.limit ?? 3}`
}

export const statisticsApi = {
  getFrequentItems(params: {
    type: 'expense' | 'income' | 'transfer' | 'account'
    days?: number
    limit?: number
  }): Promise<FrequentItem[]> {
    const key = frequentCacheKey(params)
    const now = Date.now()
    const hit = frequentCache.get(key)
    if (hit) {
      if (hit.data && hit.expiresAt > now) return Promise.resolve(hit.data)
      if (hit.inflight) return hit.inflight
    }

    const request = apiClient
      .get('/api/statistics/frequent', { params })
      .then((data) => {
        const items = data as unknown as FrequentItem[]
        frequentCache.set(key, {
          expiresAt: Date.now() + FREQUENT_TTL_MS,
          data: items,
        })
        return items
      })
      .catch((error) => {
        const current = frequentCache.get(key)
        if (current?.inflight === request) frequentCache.delete(key)
        throw error
      })

    frequentCache.set(key, {
      expiresAt: 0,
      data: hit?.data || [],
      inflight: request,
    })
    return request
  },
}
