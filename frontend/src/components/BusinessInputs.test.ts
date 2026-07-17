import { mount } from '@vue/test-utils'
import Vant from 'vant'
import { describe, expect, it } from 'vitest'

import AccountPicker from './AccountPicker.vue'
import MoneyInput from './MoneyInput.vue'

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
    const options = wrapper.findAll('option').map(option => option.text())
    expect(options).toContain('Expenses:Food')
    expect(options).not.toContain('Assets')
  })
})
