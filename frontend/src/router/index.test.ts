import { describe, expect, it } from 'vitest'

import router from './index'

describe('router', () => {
  it.each([
    '/dashboard',
    '/transactions',
    '/transactions/new',
    '/transactions/example',
    '/transactions/example/edit',
    '/budgets',
    '/reviews/2026-07',
    '/settings',
  ])('matches independent route %s', path => {
    expect(router.resolve(path).matched.length).toBeGreaterThan(0)
  })

  it('replaces the root with dashboard route', () => {
    expect(router.resolve('/').redirectedFrom).toBeUndefined()
    const root = router.getRoutes().find(route => route.path === '/')
    expect(root?.redirect).toBe('/dashboard')
  })

  it('keeps only the transaction list page alive for detail round trips', () => {
    expect(router.resolve('/transactions').meta.keepAlive).toBe(true)
    expect(router.resolve('/transactions/example').meta.keepAlive).toBeUndefined()
  })
})
