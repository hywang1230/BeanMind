import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import apiClient from '../../api/client'
import { configApi } from '../../api/config'
import SettingsPage from './SettingsPage.vue'

vi.mock('../../api/config', () => ({ configApi: { get: vi.fn() } }))
vi.mock('../../api/client', () => ({ default: { get: vi.fn() } }))

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    vi.mocked(configApi.get).mockResolvedValue({ single_machine: true, backup_managed_externally: true, llm_enabled: false, llm_model: '', recurring_enabled: true })
    vi.mocked(apiClient.get).mockResolvedValue({ status: 'READY' })
  })

  it('shows only single-machine settings and projection status', async () => {
    const wrapper = mount(SettingsPage, { global: { plugins: [Vant, createPinia()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('单机 · 单账本 · 单写者')
    expect(wrapper.text()).toContain('由 NAS / 部署环境负责')
    expect(wrapper.text()).toContain('READY')
    expect(wrapper.text()).not.toContain('登录')
    expect(wrapper.text()).not.toContain('远端同步')
  })
})
