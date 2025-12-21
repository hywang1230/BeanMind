import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import RecurringPage from '../RecurringPage.vue'

// Mock recurring API
vi.mock('../../../api/recurring', () => ({
    recurringApi: {
        getRules: vi.fn(() => Promise.resolve([])),
        createRule: vi.fn(),
        getRule: vi.fn(),
        updateRule: vi.fn(),
        deleteRule: vi.fn(),
        executeRule: vi.fn(),
        getExecutions: vi.fn(() => Promise.resolve([]))
    }
}))

describe('RecurringPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('应该渲染页面标题', () => {
        const wrapper = mount(RecurringPage)
        expect(wrapper.find('h1').text()).toBe('周期任务')
    })

    it('应该显示创建按钮', () => {
        const wrapper = mount(RecurringPage)
        expect(wrapper.find('.create-btn').exists()).toBe(true)
        expect(wrapper.find('.create-btn').text()).toContain('新建规则')
    })

    it('空状态应该显示正确内容', async () => {
        const wrapper = mount(RecurringPage)
        await wrapper.vm.$nextTick()

        // 等待数据加载
        await new Promise(resolve => setTimeout(resolve, 100))
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.empty-state').exists()).toBe(true)
        expect(wrapper.find('.empty-text').text()).toBe('暂无周期任务')
    })

    it('点击创建按钮应该打开模态框', async () => {
        const wrapper = mount(RecurringPage)
        await wrapper.vm.$nextTick()

        await wrapper.find('.create-btn').trigger('click')
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.modal').exists()).toBe(true)
    })

    it('格式化频率应该正确', () => {
        const wrapper = mount(RecurringPage)
        const instance = wrapper.vm as any

        expect(instance.formatFrequency('daily')).toBe('每日')
        expect(instance.formatFrequency('weekly')).toBe('每周')
        expect(instance.formatFrequency('monthly')).toBe('每月')
    })

    it('格式化日期应该正确', () => {
        const wrapper = mount(RecurringPage)
        const instance = wrapper.vm as any

        expect(instance.formatDate('2024-01-15')).toBe('2024-01-15')
    })
})
