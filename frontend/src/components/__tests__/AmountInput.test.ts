import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AmountInput from '../AmountInput.vue'

describe('AmountInput', () => {
    it('应该渲染输入框', () => {
        const wrapper = mount(AmountInput)
        expect(wrapper.find('input').exists()).toBe(true)
    })

    it('应该显示快捷金额按钮', () => {
        const wrapper = mount(AmountInput)
        const buttons = wrapper.findAll('.quick-amount-btn')
        expect(buttons.length).toBeGreaterThan(0)
    })

    it('点击快捷金额按钮应该更新值', async () => {
        const wrapper = mount(AmountInput)
        const button = wrapper.find('.quick-amount-btn')

        await button.trigger('click')

        expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    })

    it('应该显示正确的货币符号', () => {
        const wrapper = mount(AmountInput, {
            props: {
                currency: 'USD'
            }
        })

        expect(wrapper.find('.currency').text()).toBe('USD')
    })
})
