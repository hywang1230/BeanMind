import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AmountInput from '../AmountInput.vue'

// Mock f7-sheet and f7-link since we are unit testing logic
const F7SheetStub = {
    template: '<div><slot /></div>',
    props: ['opened']
}
const F7LinkStub = {
    template: '<a href="#"><slot /></a>'
}

describe('AmountInput', () => {
    it('应该渲染显示区域', () => {
        const wrapper = mount(AmountInput, {
            global: {
                stubs: {
                    'f7-sheet': F7SheetStub,
                    'f7-link': F7LinkStub
                }
            }
        })
        expect(wrapper.find('.amount-display').exists()).toBe(true)
        expect(wrapper.find('.value-text').text()).toBe('0.00')
    })

    it('点击显示区域应该打开键盘', async () => {
        const wrapper = mount(AmountInput, {
            global: {
                stubs: {
                    'f7-sheet': F7SheetStub,
                    'f7-link': F7LinkStub
                }
            }
        })

        await wrapper.find('.amount-display').trigger('click')
        // In real component, this sets isKeypadOpen=true.
        // Since we stubbed f7-sheet, we can check if visible or if VM state changed.
        // Better to check internal state (though accessing vm is implicit) 
        // Or check if 'focused' class is added to display
        expect(wrapper.find('.amount-display').classes()).toContain('focused')
    })

    it('键盘输入应该更新显示和值', async () => {
        const wrapper = mount(AmountInput, {
            global: {
                stubs: {
                    'f7-sheet': F7SheetStub,
                    'f7-link': F7LinkStub
                }
            }
        })

        await wrapper.find('.amount-display').trigger('click')

        // Find buttons. Text content matching.
        const buttons = wrapper.findAll('button')
        const btn1 = buttons.find(b => b.text() === '1')
        const btn2 = buttons.find(b => b.text() === '2')
        const btnPlus = buttons.find(b => b.text() === '+')

        if (btn1) await btn1.trigger('click')
        if (btn2) await btn2.trigger('click')

        expect(wrapper.find('.value-text').text()).toBe('12')

        if (btnPlus) await btnPlus.trigger('click')
        if (btn2) await btn2.trigger('click')

        expect(wrapper.find('.value-text').text()).toBe('12+2')

        // Find OK/= button
        const btnOk = wrapper.findAll('button').find(b => b.classes().includes('highlight'))
        await btnOk?.trigger('click') // Calculate

        expect(wrapper.find('.value-text').text()).toBe('14')
        expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([14])
    })

    it('不允负数时应该限制为0', async () => {
        const wrapper = mount(AmountInput, {
            props: { allowNegative: false },
            global: {
                stubs: { 'f7-sheet': F7SheetStub, 'f7-link': F7LinkStub }
            }
        })

        await wrapper.find('.amount-display').trigger('click')
        const buttons = wrapper.findAll('button')
        const btn1 = buttons.find(b => b.text() === '1')
        const btnMinus = buttons.find(b => b.text() === '-')
        const btn5 = buttons.find(b => b.text() === '5')
        const btnOk = buttons.find(b => b.classes().includes('highlight'))

        // 1 - 5 = -4
        await btn1?.trigger('click')
        await btnMinus?.trigger('click')
        await btn5?.trigger('click')
        await btnOk?.trigger('click')

        expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([0])
    })
})
