import { defineStore } from 'pinia'
import type { CreateTransactionRequest, Posting } from '../api/transactions'
import { addAmounts, isValidAmount, isZero, negateAmount, quantizeAmount, subAmounts } from '../utils/decimal'

export type TransactionType = 'expense' | 'income' | 'transfer'
export type DraftMode = 'create' | `edit:${string}`
export type DistributeSide = 'from' | 'to'

export type DraftLine = {
  account: string
  amount: string
}

export type TransactionDraft = {
  mode: DraftMode
  type: TransactionType
  date: string
  payee: string
  description: string
  currency: string
  /** Total positive amount string for the transaction. */
  amount: string
  fromAccounts: string[]
  toAccounts: string[]
  /** Positive amount allocations per account on each side. */
  fromLines: DraftLine[]
  toLines: DraftLine[]
}

function emptyDraft(partial?: Partial<TransactionDraft>): TransactionDraft {
  return {
    mode: 'create',
    type: 'expense',
    date: new Date().toISOString().slice(0, 10),
    payee: '',
    description: '',
    currency: 'CNY',
    amount: '',
    fromAccounts: [],
    toAccounts: [],
    fromLines: [],
    toLines: [],
    ...partial,
  }
}

function unique(list: string[]): string[] {
  return [...new Set(list.filter(Boolean))]
}

/** Infer draft from a saved transaction's full posting list. */
export function draftFromTransaction(transaction: {
  id: string
  date: string
  description?: string
  payee?: string
  postings: Posting[]
  transaction_type?: string
}): TransactionDraft {
  const postings = transaction.postings || []
  const currency = postings[0]?.currency || 'CNY'
  const type: TransactionType =
    transaction.transaction_type === 'income'
      ? 'income'
      : transaction.transaction_type === 'transfer'
        ? 'transfer'
        : postings.some((p) => p.account.startsWith('Income:'))
          ? 'income'
          : postings.some((p) => p.account.startsWith('Assets:') || p.account.startsWith('Liabilities:'))
              && !postings.some((p) => p.account.startsWith('Expenses:') || p.account.startsWith('Income:'))
            ? 'transfer'
            : 'expense'

  let fromAccounts: string[] = []
  let toAccounts: string[] = []
  let fromLines: DraftLine[] = []
  let toLines: DraftLine[] = []
  let amount = '0'

  if (type === 'expense') {
    const categories = postings.filter((p) => p.account.startsWith('Expenses:'))
    const funding = postings.filter((p) => !p.account.startsWith('Expenses:'))
    toAccounts = categories.map((p) => p.account)
    fromAccounts = funding.map((p) => p.account)
    toLines = categories.map((p) => ({ account: p.account, amount: p.amount.startsWith('-') ? negateAmount(p.amount) : p.amount }))
    fromLines = funding.map((p) => ({ account: p.account, amount: p.amount.startsWith('-') ? negateAmount(p.amount) : p.amount }))
    amount = toLines.length ? addAmounts(...toLines.map((l) => l.amount || '0')) : '0'
  } else if (type === 'income') {
    // Income negative, funding positive in Beancount
    const income = postings.filter((p) => p.account.startsWith('Income:'))
    const funding = postings.filter((p) => !p.account.startsWith('Income:'))
    toAccounts = income.map((p) => p.account)
    fromAccounts = funding.map((p) => p.account)
    toLines = income.map((p) => ({ account: p.account, amount: p.amount.startsWith('-') ? negateAmount(p.amount) : p.amount }))
    fromLines = funding.map((p) => ({ account: p.account, amount: p.amount.startsWith('-') ? negateAmount(p.amount) : p.amount }))
    amount = fromLines.length ? addAmounts(...fromLines.map((l) => l.amount || '0')) : '0'
  } else {
    const sources = postings.filter((p) => p.amount.startsWith('-'))
    const targets = postings.filter((p) => !p.amount.startsWith('-'))
    fromAccounts = sources.map((p) => p.account)
    toAccounts = targets.map((p) => p.account)
    fromLines = sources.map((p) => ({ account: p.account, amount: negateAmount(p.amount) }))
    toLines = targets.map((p) => ({ account: p.account, amount: p.amount }))
    amount = fromLines.length ? addAmounts(...fromLines.map((l) => l.amount || '0')) : '0'
  }

  return emptyDraft({
    mode: `edit:${transaction.id}`,
    type,
    date: transaction.date,
    payee: transaction.payee || '',
    description: transaction.description || '',
    currency,
    amount,
    fromAccounts: unique(fromAccounts),
    toAccounts: unique(toAccounts),
    fromLines,
    toLines,
  })
}

export function buildPostingsFromDraft(draft: TransactionDraft): Posting[] {
  const currency = draft.currency || 'CNY'
  const ensureLines = (accounts: string[], lines: DraftLine[], total: string): DraftLine[] => {
    if (accounts.length === 1) {
      const only = accounts[0]
      if (!only) return []
      const existing = lines.find((l) => l.account === only)
      return [{ account: only, amount: existing?.amount || total }]
    }
    return accounts.map((account) => {
      const existing = lines.find((l) => l.account === account)
      return { account, amount: existing?.amount || '0' }
    })
  }

  const fromLines = ensureLines(draft.fromAccounts, draft.fromLines, draft.amount)
  const toLines = ensureLines(draft.toAccounts, draft.toLines, draft.amount)

  const q = (amount: string) => quantizeAmount(amount || '0', 2)

  if (draft.type === 'expense') {
    return [
      ...toLines.map((l) => ({ account: l.account, amount: q(l.amount), currency })),
      ...fromLines.map((l) => ({ account: l.account, amount: q(negateAmount(l.amount)), currency })),
    ]
  }
  if (draft.type === 'income') {
    return [
      ...fromLines.map((l) => ({ account: l.account, amount: q(l.amount), currency })),
      ...toLines.map((l) => ({ account: l.account, amount: q(negateAmount(l.amount)), currency })),
    ]
  }
  return [
    ...fromLines.map((l) => ({ account: l.account, amount: q(negateAmount(l.amount)), currency })),
    ...toLines.map((l) => ({ account: l.account, amount: q(l.amount), currency })),
  ]
}

export function draftNeedsDistribute(draft: TransactionDraft): boolean {
  return draft.fromAccounts.length > 1 || draft.toAccounts.length > 1
}

export function sideRemaining(total: string, lines: DraftLine[]): string {
  const assigned = lines.length ? addAmounts(...lines.map((l) => l.amount || '0')) : '0'
  return subAmounts(total || '0', assigned)
}

export function sideIsBalanced(total: string, lines: DraftLine[], accounts: string[]): boolean {
  if (!accounts.length) return false
  if (accounts.length === 1) return isValidAmount(total, { allowZero: false, allowNegative: true })
  if (lines.length !== accounts.length) return false
  if (!lines.every((l) => accounts.includes(l.account) && isValidAmount(l.amount, { allowZero: false }))) return false
  return isZero(sideRemaining(total, lines))
}

export function toCreateRequest(draft: TransactionDraft): CreateTransactionRequest {
  return {
    date: draft.date,
    payee: draft.payee || undefined,
    description: draft.description || undefined,
    postings: buildPostingsFromDraft(draft),
  }
}

export const useTransactionDraftStore = defineStore('transactionDraft', {
  state: () => ({
    draft: null as TransactionDraft | null,
  }),
  getters: {
    hasDraft: (state) => Boolean(state.draft),
  },
  actions: {
    setDraft(draft: TransactionDraft) {
      this.draft = {
        ...draft,
        fromAccounts: unique(draft.fromAccounts),
        toAccounts: unique(draft.toAccounts),
      }
    },
    updateDraft(partial: Partial<TransactionDraft>) {
      if (!this.draft) {
        this.draft = emptyDraft(partial)
        return
      }
      this.draft = {
        ...this.draft,
        ...partial,
        fromAccounts: unique(partial.fromAccounts ?? this.draft.fromAccounts),
        toAccounts: unique(partial.toAccounts ?? this.draft.toAccounts),
      }
    },
    setSideLines(side: DistributeSide, lines: DraftLine[]) {
      if (!this.draft) return
      if (side === 'from') this.draft = { ...this.draft, fromLines: lines }
      else this.draft = { ...this.draft, toLines: lines }
    },
    clear() {
      this.draft = null
    },
    createEmpty(mode: DraftMode = 'create') {
      this.draft = emptyDraft({ mode })
      return this.draft
    },
  },
})
