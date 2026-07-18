import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PwaUpdatePrompt from './PwaUpdatePrompt.vue'

const pwa = vi.hoisted(() => ({
  onNeedRefresh: undefined as (() => void) | undefined,
  updateServiceWorker: vi.fn<() => Promise<void>>(),
}))

vi.mock('virtual:pwa-register', () => ({
  registerSW: (options: { onNeedRefresh?: () => void }) => {
    pwa.onNeedRefresh = options.onNeedRefresh
    return pwa.updateServiceWorker
  },
}))

describe('PwaUpdatePrompt', () => {
  beforeEach(() => {
    pwa.onNeedRefresh = undefined
    pwa.updateServiceWorker.mockReset().mockResolvedValue()
  })

  async function showPrompt() {
    const wrapper = mount(PwaUpdatePrompt)
    pwa.onNeedRefresh?.()
    await nextTick()
    return wrapper
  }

  it('shows actions when a new version is ready', async () => {
    const wrapper = await showPrompt()

    expect(wrapper.text()).toContain('发现新版本')
    expect(wrapper.text()).toContain('立即更新')
    expect(wrapper.text()).toContain('稍后')
  })

  it('activates the waiting service worker only after confirmation', async () => {
    const wrapper = await showPrompt()

    await wrapper.find('.pwa-update__confirm').trigger('click')
    await flushPromises()

    expect(pwa.updateServiceWorker).toHaveBeenCalledOnce()
    expect(pwa.updateServiceWorker).toHaveBeenCalledWith(true)
  })

  it('dismisses the prompt without activating the update', async () => {
    const wrapper = await showPrompt()

    await wrapper.find('.pwa-update__later').trigger('click')

    expect(wrapper.find('.pwa-update').exists()).toBe(false)
    expect(pwa.updateServiceWorker).not.toHaveBeenCalled()
  })
})
