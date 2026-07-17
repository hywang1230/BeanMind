<template><section class="page transaction-editor-page"><van-nav-bar title="编辑交易" left-arrow @click-left="router.back()" /><div v-if="loadingInitial" class="state-card"><van-loading /></div><van-empty v-else-if="error && !transaction" image="error" :description="error"><van-button @click="load">重试</van-button></van-empty><TransactionForm v-else :initial="transaction" :loading="saving" @submit="save" /></section></template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'; import { useRoute, useRouter } from 'vue-router'; import TransactionForm from '../../components/TransactionForm.vue'; import { transactionsApi, type CreateTransactionRequest, type Transaction } from '../../api/transactions'; import type { ApiError } from '../../api/client'
const route = useRoute(); const router = useRouter(); const transaction = ref<Transaction|null>(null); const loadingInitial = ref(false); const saving = ref(false); const error = ref('')
async function load(){ loadingInitial.value=true; error.value=''; try{ transaction.value=await transactionsApi.getTransaction(String(route.params.id)) }catch(reason){error.value=(reason as ApiError).message}finally{loadingInitial.value=false}}
async function save(value:CreateTransactionRequest){saving.value=true;error.value='';try{await transactionsApi.updateTransaction(String(route.params.id),value);await router.replace(`/transactions/${route.params.id}`)}catch(reason){error.value=(reason as ApiError).message}finally{saving.value=false}}
onMounted(load)
</script>
