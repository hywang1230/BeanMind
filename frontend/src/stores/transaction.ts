import { defineStore } from 'pinia'
import { ref } from 'vue'
import { transactionsApi, type Transaction, type TransactionsQuery, type CreateTransactionRequest } from '../api/transactions'

export const useTransactionStore = defineStore('transaction', () => {
    // 状态
    const transactions = ref<Transaction[]>([])
    const currentTransaction = ref<Transaction | null>(null)
    const total = ref(0)
    const loading = ref(false)

    // 操作
    async function fetchTransactions(query: TransactionsQuery = {}) {
        loading.value = true
        try {
            const response = await transactionsApi.getTransactions(query)
            transactions.value = response.transactions
            total.value = response.total
            return response
        } catch (error) {
            console.error('Failed to fetch transactions:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    async function fetchTransaction(id: string) {
        loading.value = true
        try {
            currentTransaction.value = await transactionsApi.getTransaction(id)
            return currentTransaction.value
        } catch (error) {
            console.error('Failed to fetch transaction:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    async function createTransaction(data: CreateTransactionRequest) {
        loading.value = true
        try {
            const transaction = await transactionsApi.createTransaction(data)
            transactions.value.unshift(transaction)
            total.value++
            return transaction
        } catch (error) {
            console.error('Failed to create transaction:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    async function updateTransaction(id: string, data: Partial<CreateTransactionRequest>) {
        loading.value = true
        try {
            const updated = await transactionsApi.updateTransaction(id, data)
            const index = transactions.value.findIndex(t => t.id === id)
            if (index !== -1) {
                transactions.value[index] = updated
            }
            if (currentTransaction.value?.id === id) {
                currentTransaction.value = updated
            }
            return updated
        } catch (error) {
            console.error('Failed to update transaction:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    async function deleteTransaction(id: string) {
        loading.value = true
        try {
            await transactionsApi.deleteTransaction(id)
            transactions.value = transactions.value.filter(t => t.id !== id)
            total.value--
            if (currentTransaction.value?.id === id) {
                currentTransaction.value = null
            }
        } catch (error) {
            console.error('Failed to delete transaction:', error)
            throw error
        } finally {
            loading.value = false
        }
    }

    return {
        transactions,
        currentTransaction,
        total,
        loading,
        fetchTransactions,
        fetchTransaction,
        createTransaction,
        updateTransaction,
        deleteTransaction
    }
})
