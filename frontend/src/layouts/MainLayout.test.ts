import { enableAutoUnmount, mount } from '@vue/test-utils'
import Vant from 'vant'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MainLayout from './MainLayout.vue'

const push = vi.fn()
const route = reactive<{ path: string; meta: Record<string, unknown> }>({
  path: '/transactions',
  meta: { tab: 'transactions' },
})

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ push }),
}))

enableAutoUnmount(afterEach)

describe('MainLayout', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    route.path = '/transactions'
    route.meta = { tab: 'transactions' }
  })

  it('renders a center add action that opens the new transaction page', async () => {
    const wrapper = mount(MainLayout, {
      global: {
        plugins: [Vant],
        stubs: {
          RouterView: true,
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    const add = wrapper.find('.tabbar-add')
    expect(add.exists()).toBe(true)
    expect(wrapper.find('.tabbar-add-btn').exists()).toBe(true)
    expect(wrapper.text()).toContain('首页')
    expect(wrapper.text()).toContain('流水')
    expect(wrapper.text()).toContain('预算')
    expect(wrapper.text()).toContain('设置')

    await add.trigger('click')
    expect(push).toHaveBeenCalledWith('/transactions/new')
  })

  it('hides the tabbar on non-tab routes', () => {
    route.path = '/transactions/new'
    route.meta = { title: '记一笔' }
    const wrapper = mount(MainLayout, {
      global: {
        plugins: [Vant],
        stubs: {
          RouterView: true,
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    expect(wrapper.find('.main-tabbar').exists()).toBe(false)
  })
})
