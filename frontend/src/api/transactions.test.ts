import { afterEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosAdapter } from 'axios'
import apiClient from './client'
import { transactionsApi } from './transactions'

const originalAdapter = apiClient.defaults.adapter
const payload = { date: '2026-09-26', postings: [] }
afterEach(() => { apiClient.defaults.adapter = originalAdapter; vi.useRealTimers() })

describe('transaction write transport', () => {
  it('allows a response after 10 seconds and keeps reads at 10 seconds', async () => {
    vi.useFakeTimers()
    const adapter = vi.fn<AxiosAdapter>(config => new Promise(resolve => {
      setTimeout(() => resolve({ data: { id: 'saved' }, status: 201, statusText: '', headers: {}, config }), 15000)
    }))
    apiClient.defaults.adapter = adapter
    let done = false
    const result = transactionsApi.createTransaction(payload).then(value => { done = true; return value })
    await vi.advanceTimersByTimeAsync(10001)
    expect(done).toBe(false)
    await vi.advanceTimersByTimeAsync(4999)
    expect(await result).toEqual({ id: 'saved' })
    expect(adapter.mock.calls[0]![0].timeout).toBe(60000)
    const read = transactionsApi.getTransactions()
    await vi.advanceTimersByTimeAsync(15000)
    await read
    expect(adapter.mock.calls[1]![0].timeout).toBe(10000)
  })

  it.each(['create', 'update', 'delete'] as const)('%s reaches 60 seconds without replay', async method => {
    vi.useFakeTimers()
    const adapter = vi.fn<AxiosAdapter>(config => new Promise((_, reject) => {
      setTimeout(() => reject(new AxiosError('timeout', 'ECONNABORTED', config)), config.timeout)
    }))
    apiClient.defaults.adapter = adapter
    const result = method === 'create' ? transactionsApi.createTransaction(payload)
      : method === 'update' ? transactionsApi.updateTransaction('one', payload) : transactionsApi.deleteTransaction('one')
    const assertion = expect(result).rejects.toMatchObject({ code: 'TRANSACTION_RESULT_UNCONFIRMED', message: expect.stringContaining('勿重复提交') })
    await vi.advanceTimersByTimeAsync(60000)
    await assertion
    expect(adapter).toHaveBeenCalledTimes(1)
    expect(adapter.mock.calls[0]![0].timeout).toBe(60000)
  })

  it.each([
    ['ERR_NETWORK', 'TRANSACTION_RESULT_UNCONFIRMED'],
    ['ERR_CANCELED', 'REQUEST_CANCELED'],
  ])('distinguishes %s', async (code, expected) => {
    apiClient.defaults.adapter = config => Promise.reject(code === 'ERR_CANCELED'
      ? new AxiosError('canceled', 'ERR_CANCELED', config) : new AxiosError('network', code, config))
    await expect(transactionsApi.createTransaction(payload)).rejects.toMatchObject({ code: expected })
  })

  it('preserves explicit server business errors', async () => {
    apiClient.defaults.adapter = config => Promise.reject(new AxiosError('invalid', 'ERR_BAD_REQUEST', config, {}, {
      data: { code: 'INVALID_TRANSACTION', message: '不平衡' }, status: 400, statusText: '', headers: {}, config,
    }))
    await expect(transactionsApi.createTransaction(payload)).rejects.toMatchObject({ code: 'INVALID_TRANSACTION', message: '不平衡', status: 400 })
  })
})
