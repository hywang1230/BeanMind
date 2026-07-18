import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import Vant from 'vant'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { statisticsApi } from '../api/statistics'
import AccountPicker from './AccountPicker.vue'
import DatePickerField from './DatePickerField.vue'
import DateRangePickerField from './DateRangePickerField.vue'
import MoneyInput from './MoneyInput.vue'
import MonthPicker from './MonthPicker.vue'
import SelectPickerField from './SelectPickerField.vue'

vi.mock('../api/statistics', () => ({
  statisticsApi: {
    getFrequentItems: vi.fn(),
  },
}))

const popupStub = {
  name: 'VanPopup',
  props: ['show', 'teleport'],
  template: '<div class="popup-stub"><slot /></div>',
}

describe('business inputs', () => {
  beforeEach(() => {
    vi.mocked(statisticsApi.getFrequentItems).mockReset()
  })

  it('opens a calc keypad and commits decimal-string results', async () => {
    const wrapper = mount(MoneyInput, {
      props: { modelValue: '', currency: 'CNY' },
      global: {
        plugins: [Vant],
        stubs: {
          // Keep popup content in-tree for unit tests.
          VanPopup: { template: '<div class="van-popup-stub"><slot /></div>', props: ['show'] },
        },
      },
    })

    await wrapper.find('.money-display').trigger('click')
    expect(wrapper.find('.money-display').classes()).toContain('focused')

    const press = async (label: string) => {
      const btn = wrapper.findAll('button.key-btn').find((node) => node.text() === label)
      expect(btn).toBeTruthy()
      await btn!.trigger('click')
    }

    await press('1')
    await press('2')
    await press('+')
    await press('3')
    expect(wrapper.find('.keypad-preview-value').text()).toBe('12+3')

    await wrapper.find('.confirm-key').trigger('click')
    const events = wrapper.emitted('update:modelValue') || []
    expect(events[events.length - 1]).toEqual(['15.00'])
    expect(typeof events[events.length - 1]![0]).toBe('string')
  })

  it('keeps negative keypad results by default', async () => {
    const wrapper = mount(MoneyInput, {
      props: { modelValue: '', currency: 'CNY' },
      global: {
        plugins: [Vant],
        stubs: { VanPopup: { template: '<div><slot /></div>', props: ['show'] } },
      },
    })
    await wrapper.find('.money-display').trigger('click')
    for (const label of ['1', '-', '5']) {
      const btn = wrapper.findAll('button.key-btn').find((node) => node.text() === label)
      await btn!.trigger('click')
    }
    await wrapper.find('.confirm-key').trigger('click')
    const events = wrapper.emitted('update:modelValue') || []
    expect(events[events.length - 1]).toEqual(['-4.00'])
  })

  it('clamps negative keypad results when allowNegative is false', async () => {
    const wrapper = mount(MoneyInput, {
      props: { modelValue: '', currency: 'CNY', allowNegative: false },
      global: {
        plugins: [Vant],
        stubs: { VanPopup: { template: '<div><slot /></div>', props: ['show'] } },
      },
    })
    await wrapper.find('.money-display').trigger('click')
    for (const label of ['1', '-', '5']) {
      const btn = wrapper.findAll('button.key-btn').find((node) => node.text() === label)
      await btn!.trigger('click')
    }
    await wrapper.find('.confirm-key').trigger('click')
    const events = wrapper.emitted('update:modelValue') || []
    expect(events[events.length - 1]).toEqual(['0.00'])
  })

  it('commits the expression when the keypad is closed without confirm', async () => {
    const wrapper = mount(MoneyInput, {
      props: { modelValue: '', currency: 'CNY' },
      global: {
        plugins: [Vant],
        stubs: {
          VanPopup: {
            name: 'VanPopup',
            props: ['show'],
            emits: ['update:show', 'closed'],
            template: '<div class="popup-stub"><slot /></div>',
          },
        },
      },
    })
    await wrapper.find('.money-display').trigger('click')
    for (const label of ['8', '+', '2']) {
      const btn = wrapper.findAll('button.key-btn').find((node) => node.text() === label)
      await btn!.trigger('click')
    }
    // Simulate popup close (backdrop / swipe).
    await wrapper.findComponent({ name: 'VanPopup' }).vm.$emit('closed')
    const events = wrapper.emitted('update:modelValue') || []
    expect(events[events.length - 1]).toEqual(['10.00'])
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
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })

    expect(wrapper.findComponent({ name: 'VanPopup' }).props('teleport')).toBe('body')
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

  it('allows selecting synthetic parent categories when allowParentSelect is on', async () => {
    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: '',
        allowParentSelect: true,
        prefixes: ['Expenses'],
        accounts: [
          {
            name: 'Expenses:JT-交通:地铁',
            account_type: 'Expenses',
            currencies: ['CNY'],
          },
          {
            name: 'Expenses:JT-交通:打车',
            account_type: 'Expenses',
            currencies: ['CNY'],
          },
        ],
      },
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })

    await wrapper.find('.van-field').trigger('click')
    const parentRow = wrapper.findAll('button.account-tree-row').find((row) => row.text().includes('JT-交通'))
    expect(parentRow).toBeTruthy()
    expect(parentRow!.text()).toContain('含子分类')
    expect(parentRow!.classes()).not.toContain('disabled')
    await parentRow!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['Expenses:JT-交通']])
  })

  it('clears optional account picker values', async () => {
    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: 'Assets:Cash',
        clearable: true,
        accounts: [{ name: 'Assets:Cash', account_type: 'Assets', currencies: ['CNY'] }],
      },
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })
    await wrapper.find('[aria-label="清空账户"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['']])
    expect(wrapper.emitted('change')).toEqual([['']])
  })

  it('loads frequent accounts for the transaction type and supports quick select', async () => {
    vi.mocked(statisticsApi.getFrequentItems).mockResolvedValue([
      { name: 'Expenses:Food:Lunch', count: 5, last_used: '2026-07-01' },
      { name: 'Expenses:Food:Dinner', count: 3, last_used: '2026-07-02' },
      { name: 'Assets:Cash', count: 9, last_used: '2026-07-03' },
    ])

    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: '',
        transactionType: 'expense',
        prefixes: ['Expenses'],
        accounts: [
          {
            name: 'Expenses',
            account_type: 'Expenses',
            currencies: ['CNY'],
            children: [
              {
                name: 'Expenses:Food',
                account_type: 'Expenses',
                currencies: ['CNY'],
                children: [
                  { name: 'Expenses:Food:Lunch', account_type: 'Expenses', currencies: ['CNY'] },
                  { name: 'Expenses:Food:Dinner', account_type: 'Expenses', currencies: ['CNY'] },
                ],
              },
            ],
          },
        ],
      },
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })

    await wrapper.find('.van-field').trigger('click')
    await flushPromises()

    expect(statisticsApi.getFrequentItems).toHaveBeenCalledWith({
      type: 'expense',
      days: 30,
      limit: 3,
    })
    expect(wrapper.text()).toContain('最近常用')
    expect(wrapper.text()).toContain('Expenses:Food:Lunch')
    expect(wrapper.text()).not.toContain('Assets:Cash')

    await wrapper.find('.frequent-item').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['Expenses:Food:Lunch']])
    expect(wrapper.emitted('change')).toEqual([['Expenses:Food:Lunch']])
  })

  it('skips frequent account loading without transactionType', async () => {
    const wrapper = mount(AccountPicker, {
      props: {
        modelValue: '',
        prefixes: ['Expenses'],
        accounts: [
          { name: 'Expenses:Food:Lunch', account_type: 'Expenses', currencies: ['CNY'] },
        ],
      },
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })

    await wrapper.find('.van-field').trigger('click')
    await flushPromises()

    expect(statisticsApi.getFrequentItems).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('最近常用')
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
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })
    expect(wrapper.find('input[type="month"]').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'VanPopup' }).props('teleport')).toBe('body')
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
    expect(calendar.props('teleport')).toBe('body')
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
      global: { plugins: [Vant], stubs: { VanPopup: popupStub } },
    })
    expect(wrapper.find('select').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'VanPopup' }).props('teleport')).toBe('body')
    expect(wrapper.find('van-picker-stub').exists()).toBe(true)
  })
})
