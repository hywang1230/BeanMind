<template><section class="page transaction-editor-page"><van-nav-bar title="记一笔" left-arrow @click-left="router.back()" /><TransactionForm :loading="loading" @submit="save" /><van-notice-bar v-if="error" color="var(--bm-expense)" background="var(--bm-danger-soft)">{{ error }}</van-notice-bar></section></template>
<script setup lang="ts">
import { ref } from 'vue'; import { useRouter } from 'vue-router'; import TransactionForm from '../../components/TransactionForm.vue'; import { transactionsApi, type CreateTransactionRequest } from '../../api/transactions'; import type { ApiError } from '../../api/client'
const router = useRouter(); const loading = ref(false); const error = ref('')
async function save(value: CreateTransactionRequest) { loading.value = true; error.value = ''; try { const created = await transactionsApi.createTransaction(value); await router.replace(`/transactions/${created.id}`) } catch (reason) { error.value = (reason as ApiError).message } finally { loading.value = false } }
</script>
