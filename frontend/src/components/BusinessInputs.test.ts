import { mount, shallowMount } from '@vue/test-utils'
import Vant from 'vant'
import { describe, expect, it } from 'vitest'

import AccountPicker from './AccountPicker.vue'
import DatePickerField from './DatePickerField.vue'
import DateRangePickerField from './DateRangePickerField.vue'
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

  it('renders a searchable account tree and keeps full account values', async () => {
    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: '',
        prefixes: ['Expenses'],
        accounts: [
          { name: 'Assets', account_type: 'Assets', currencies: ['CNY'], children: [
            { name: 'Assets:Wallet:Lunch', account_type: 'Assets', currencies: ['CNY'] },
          ] },
          { name: 'Expenses', account_type: 'Expenses', currencies: ['CNY'], children: [
            { name: 'Expenses:Food', account_type: 'Expenses', currencies: ['CNY'], children: [
              { name: 'Expenses:Food:Lunch', account_type: 'Expenses', currencies: ['CNY'] },
            ] },
            { name: 'Expenses:Work:Lunch', account_type: 'Expenses', currencies: ['CNY'] },
          ] },
        ],
      },
      global: { plugins: [Vant] },
    })

    await wrapper.find('.van-field').trigger('click')
    // top-level prefixes auto-expand; Food should be visible without collapsing
    expect(wrapper.text()).toContain('Food')
    expect(wrapper.text()).toContain('Expenses:Food')
    expect(wrapper.text()).not.toContain('Assets:Wallet:Lunch')

    await wrapper.find('input[type="search"]').setValue('Lunch')
    const rows = wrapper.findAll('.account-tree-row')
    expect(rows.map(row => row.text()).join(' ')).toContain('Expenses:Food:Lunch')
    expect(rows.map(row => row.text()).join(' ')).toContain('Expenses:Work:Lunch')
    await rows.find(row => row.text().includes('Expenses:Work:Lunch'))!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['Expenses:Work:Lunch']])
    expect(wrapper.emitted('change')).toEqual([['Expenses:Work:Lunch']])
  })

  it('clears optional account picker values', async () => {
    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: 'Assets:Cash',
        clearable: true,
        accounts: [{ name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] }],
      },
      global: { plugins: [Vant] },
    })
    await wrapper.find('[aria-label="清空账户"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    expect(wrapper.emitted('change')).toEqual([['']])
  })

  it('clears optional picker values through the field clear action', async () => {
    const wrapper = mount(SelectPickerField, {
      props: {
        modelValue: 'expense',
        label: '类型',
        clearable: true,
        options: [{ text: '支出', value: 'expense' }],
      },
      global: { plugins: [Vant] },
    })
    await wrapper.find('[aria-label="清空类型"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    expect(wrapper.emitted('change')).toEqual([['']])
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

  it('clears an optional date and emits a filter change', async () => {
    const wrapper = mount(DatePickerField, {
      props: { modelValue: '2026-07-17', label: '日期', clearable: true },
      global: { plugins: [Vant] },
    })
    await wrapper.find('[aria-label="清空日期"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    expect(wrapper.emitted('change')).toEqual([['']])
  })

  it('uses Vant range mode and emits a complete date range', () => {
    const wrapper = mount(DateRangePickerField, {
      props: { startDate: '2026-04-10', endDate: '2026-04-30' },
      global: { plugins: [Vant] },
    })
    const calendar = wrapper.findComponent({ name: 'van-calendar' })
    expect(calendar.props('type')).toBe('range')
    expect(calendar.props('allowSameDay')).toBe(true)
    calendar.vm.$emit('confirm', [new Date(2026, 4, 1), new Date(2026, 4, 3)])
    expect(wrapper.emitted('update:startDate')).toEqual([['2026-05-01']])
    expect(wrapper.emitted('update:endDate')).toEqual([['2026-05-03']])
    expect(wrapper.emitted('change')).toEqual([[{ startDate: '2026-05-01', endDate: '2026-05-03' }]])
  })

  it('clears both sides of a date range together', async () => {
    const wrapper = mount(DateRangePickerField, {
      props: { startDate: '2026-04-10', endDate: '2026-04-30' },
      global: { plugins: [Vant] },
    })
    await wrapper.find('[aria-label="清空日期范围"]').trigger('click')
    expect(wrapper.emitted('update:startDate')).toEqual([['']])
    expect(wrapper.emitted('update:endDate')).toEqual([['']])
    expect(wrapper.emitted('change')).toEqual([[{ startDate: '', endDate: '' }]])
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
