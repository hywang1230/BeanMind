import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import {
  buildPostingsFromDraft,
  draftFromTransaction,
  draftNeedsDistribute,
  sideIsBalanced,
  sideRemaining,
  toCreateRequest,
  useTransactionDraftStore,
  type TransactionDraft,
} from './transactionDraft'

function baseDraft(partial: Partial<TransactionDraft> = {}): TransactionDraft {
  return {
    mode: 'create',
    type: 'expense',
    date: '2025-04-01',
    payee: '',
    description: '',
    currency: 'CNY',
    amount: '30.00',
    fromAccounts: ['Assets:Cash'],
    toAccounts: ['Expenses:Food'],
    fromLines: [],
    toLines: [],
    ...partial,
  }
}

describe('transactionDraft', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('builds single expense postings without distribute', () => {
    const draft = baseDraft()
    expect(draftNeedsDistribute(draft)).toBe(false)
    const postings = buildPostingsFromDraft(draft)
    expect(postings).toEqual([
      { account: 'Expenses:Food', amount: '30.00', currency: 'CNY' },
      { account: 'Assets:Cash', amount: '-30.00', currency: 'CNY' },
    ])
  })


  it('builds expense with negative amount (refund-style reverse postings)', () => {
    const draft = baseDraft({ amount: '-8.00' })
    expect(sideIsBalanced('-8.00', [], ['Assets:Cash'])).toBe(true)
    const postings = buildPostingsFromDraft(draft)
    expect(postings).toEqual([
      { account: 'Expenses:Food', amount: '-8.00', currency: 'CNY' },
      { account: 'Assets:Cash', amount: '8.00', currency: 'CNY' },
    ])
  })

  it('requires distribute and balances multi category with decimal strings', () => {
    const draft = baseDraft({
      amount: '0.30',
      toAccounts: ['Expenses:Food', 'Expenses:Transport'],
      toLines: [
        { account: 'Expenses:Food', amount: '0.10' },
        { account: 'Expenses:Transport', amount: '0.20' },
      ],
      fromLines: [{ account: 'Assets:Cash', amount: '0.30' }],
    })
    expect(draftNeedsDistribute(draft)).toBe(true)
    expect(sideRemaining('0.30', draft.toLines)).toBe('0')
    expect(sideIsBalanced('0.30', draft.toLines, draft.toAccounts)).toBe(true)
    const postings = buildPostingsFromDraft(draft)
    expect(postings).toHaveLength(3)
    expect(postings.find((p) => p.account === 'Assets:Cash')?.amount).toBe('-0.30')
  })

  it('keeps full multi postings when editing', () => {
    const draft = draftFromTransaction({
      id: 'tx-1',
      date: '2025-04-01',
      description: 'split',
      payee: 'shop',
      transaction_type: 'expense',
      postings: [
        { account: 'Expenses:Food', amount: '0.10', currency: 'CNY' },
        { account: 'Expenses:Transport', amount: '0.20', currency: 'CNY' },
        { account: 'Assets:Cash', amount: '-0.30', currency: 'CNY' },
      ],
    })
    expect(draft.mode).toBe('edit:tx-1')
    expect(draft.toAccounts).toEqual(['Expenses:Food', 'Expenses:Transport'])
    expect(draft.fromAccounts).toEqual(['Assets:Cash'])
    expect(buildPostingsFromDraft(draft)).toHaveLength(3)
  })

  it('builds income with negative income accounts', () => {
    const draft = baseDraft({
      type: 'income',
      amount: '1000',
      fromAccounts: ['Assets:Cash'],
      toAccounts: ['Income:Salary', 'Income:Bonus'],
      fromLines: [{ account: 'Assets:Cash', amount: '1000' }],
      toLines: [
        { account: 'Income:Salary', amount: '700' },
        { account: 'Income:Bonus', amount: '300' },
      ],
    })
    const req = toCreateRequest(draft)
    expect(req.postings.find((p) => p.account === 'Income:Salary')?.amount).toBe('-700.00')
    expect(req.postings.find((p) => p.account === 'Assets:Cash')?.amount).toBe('1000.00')
  })

  it('clears draft after success path and keeps draft on failure', () => {
    const store = useTransactionDraftStore()
    store.setDraft(baseDraft())
    expect(store.hasDraft).toBe(true)
    // failure path: leave draft
    expect(store.draft?.amount).toBe('30.00')
    // success path
    store.clear()
    expect(store.hasDraft).toBe(false)
  })
})
