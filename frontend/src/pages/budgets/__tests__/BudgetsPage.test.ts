import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BudgetsPage from '../BudgetsPage.vue'

// Mock budgets API
vi.mock('../../../api/budgets', () => ({
    budgetsApi: {
        getBudgets: vi.fn(() => Promise.resolve([])),
        createBudget: vi.fn(),
        getBudget: vi.fn(),
        updateBudget: vi.fn(),
        deleteBudget: vi.fn(),
        getBudgetExecution: vi.fn(() => Promise.resolve({
            budget_id: 1,
            budget_name: '测试预算',
            period_start: '2024-01-01',
            period_end: '2024-01-31',
            items: [],
            total_budget: 1000,
            total_actual: 500,
            total_remaining: 500,
            status: 'normal'
        }))
    }
}))

describe('BudgetsPage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('应该渲染页面标题', () => {
        const wrapper = mount(BudgetsPage)
        expect(wrapper.find('h1').text()).toBe('预算管理')
    })

    it('应该显示创建按钮', () => {
        const wrapper = mount(BudgetsPage)
        expect(wrapper.find('.create-btn').exists()).toBe(true)
        expect(wrapper.find('.create-btn').text()).toContain('新建预算')
    })

    it('空状态应该显示正确内容', async () => {
        const wrapper = mount(BudgetsPage)
        await wrapper.vm.$nextTick()

        // 等待数据加载
        await new Promise(resolve => setTimeout(resolve, 100))
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.empty-state').exists()).toBe(true)
        expect(wrapper.find('.empty-text').text()).toBe('暂无预算')
    })

    it('点击创建按钮应该打开模态框', async () => {
        const wrapper = mount(BudgetsPage)
        await wrapper.vm.$nextTick()

        await wrapper.find('.create-btn').trigger('click')
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.modal').exists()).toBe(true)
    })

    it('格式化金额应该正确', () => {
        const wrapper = mount(BudgetsPage)
        const instance = wrapper.vm as any

        expect(instance.formatNumber(1000)).toBe('1,000.00')
        expect(instance.formatNumber(5000.5)).toBe('5,000.50')
    })

    it('格式化周期类型应该正确', () => {
        const wrapper = mount(BudgetsPage)
        const instance = wrapper.vm as any

        expect(instance.formatPeriodType('monthly')).toBe('月度')
        expect(instance.formatPeriodType('quarterly')).toBe('季度')
        expect(instance.formatPeriodType('yearly')).toBe('年度')
    })
})
