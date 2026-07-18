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
    vi.mocked(configApi.get).mockResolvedValue({
      single_machine: true,
      backup_managed_externally: true,
      llm_enabled: false,
      llm_model: '',
      recurring_enabled: true,
    })
    vi.mocked(apiClient.get).mockResolvedValue({ status: 'READY' })
  })

  it('shows version and friendly ledger status with cell-aligned theme row', async () => {
    const wrapper = mount(SettingsPage, { global: { plugins: [Vant, createPinia()] } })
    await flushPromises()
    expect(wrapper.text()).toContain('3.0.0')
    expect(wrapper.text()).toContain('账本状态')
    expect(wrapper.text()).toContain('正常')
    expect(wrapper.text()).toContain('主题')
    expect(wrapper.find('.van-field').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('投影')
    expect(wrapper.text()).not.toContain('READY')
    expect(wrapper.text()).not.toContain('单机个人财务')
    expect(wrapper.text()).not.toContain('部署模式')
    expect(wrapper.text()).not.toContain('备份')
    expect(wrapper.text()).not.toContain('设计约束')
    expect(wrapper.text()).not.toContain('登录')
    expect(wrapper.text()).not.toContain('远端同步')
  })
})
