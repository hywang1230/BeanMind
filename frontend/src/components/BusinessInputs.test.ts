import { mount, shallowMount } from '@vue/test-utils'
import Vant from 'vant'
import { describe, expect, it } from 'vitest'

import AccountPicker from './AccountPicker.vue'
import DatePickerField from './DatePickerField.vue'
import MoneyInput from './MoneyInput.vue'
import MonthPicker from './MonthPicker.vue'
import SelectPickerField from './SelectPickerField.vue'

describe('business inputs', () => {
  it('keeps money as a normalized string without Number conversion', async () => {
    const wrapper = mount(MoneyInput, {
      props: { modelValue: '', currency: 'CNY' },
      global: { plugins: [Vant] },
    })
    await wrapper.find('input').setValue('123.456789123456789x')
    const events = wrapper.emitted('update:modelValue') || []
    expect(events[events.length - 1]).toEqual(['123.456789123456789'])
  })

  it('flattens the account tree and filters by domain prefix', () => {
    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: '',
        prefixes: ['Expenses'],
        accounts: [
          { name: 'Assets', account_type: 'Assets', currencies: ['CNY'] },
          { name: 'Expenses', account_type: 'Expenses', currencies: ['CNY'], children: [
            { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'] },
          ] },
        ],
      },
      global: { plugins: [Vant] },
    })
    const picker = wrapper.findComponent(SelectPickerField)
    const options = picker.props('options') as Array<{ text: string; value: string }>
    expect(options.map(option => option.text)).toContain('Expenses:Food')
    expect(options.map(option => option.text)).not.toContain('Assets')
  })

  it('uses the Vant date picker instead of a native month input', async () => {
    const wrapper = shallowMount(MonthPicker, {
      props: { modelValue: '2026-07' },
      global: { plugins: [Vant], stubs: { VanPopup: { template: '<div><slot /></div>' } } },
    })
    expect(wrapper.find('input[type="month"]').exists()).toBe(false)
    expect(wrapper.find('van-date-picker-stub').exists()).toBe(true)
  })

  it('uses the Vant calendar instead of a native date input', async () => {
    const wrapper = shallowMount(DatePickerField, {
      props: { modelValue: '2026-07-17', label: '日期' },
      global: { plugins: [Vant] },
    })
    expect(wrapper.find('input[type="date"]').exists()).toBe(false)
    expect(wrapper.find('van-calendar-stub').exists()).toBe(true)
  })

  it('uses the Vant picker instead of a native select', () => {
    const wrapper = shallowMount(SelectPickerField, {
      props: { modelValue: 'expense', label: '类型', options: [{ text: '支出', value: 'expense' }] },
      global: { plugins: [Vant], stubs: { VanPopup: { template: '<div><slot /></div>' } } },
    })
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.find('van-picker-stub').exists()).toBe(true)
  })
})
