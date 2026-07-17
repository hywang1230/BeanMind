<template>
  <section class="page transactions-page">
    <header class="page-header"><h1>流水</h1><van-button type="primary" size="small" to="/transactions/new">记一笔</van-button></header>
    <van-search v-model="filters.description" placeholder="搜索交易方或备注" @search="applyFilters" @clear="applyFilters" />
    <van-cell-group inset class="page-section">
      <van-field label="类型"><template #input><select v-model="filters.transaction_type" class="native-select" @change="applyFilters"><option value="">全部</option><option value="expense">支出</option><option value="income">收入</option><option value="transfer">转账</option></select></template></van-field>
      <van-field v-model="filters.start_date" label="开始" type="date" @change="applyFilters" />
      <van-field v-model="filters.end_date" label="结束" type="date" @change="applyFilters" />
      <van-field v-model="filters.account" label="账户" placeholder="完整账户名" @change="applyFilters" />
      <van-field v-model="filters.tags" label="标签" placeholder="多个标签用逗号分隔" @change="applyFilters" />
    </van-cell-group>
    <div v-if="loading && !items.length" class="state-card"><van-loading>加载中</van-loading></div>
    <van-empty v-else-if="error && !items.length" image="error" :description="error"><van-button type="primary" size="small" @click="load(true)">重试</van-button></van-empty>
    <van-empty v-else-if="!items.length" description="暂无交易"><van-button type="primary" size="small" to="/transactions/new">开始记账</van-button></van-empty>
    <van-cell-group v-else inset>
      <van-cell v-for="item in items" :key="item.id" is-link :to="`/transactions/${item.id}`">
        <template #title>{{ item.payee || item.description || '未命名交易' }}</template>
        <template #label>{{ item.date }} · {{ category(item) }}</template>
        <template #value><span :class="item.transaction_type === 'income' ? 'positive' : item.transaction_type === 'expense' ? 'negative' : ''">{{ amount(item) }}</span></template>
      </van-cell>
    </van-cell-group>
    <div v-if="items.length" style="padding:16px;text-align:center">
      <van-button v-if="hasMore" :loading="loadingMore" @click="loadMore">加载更多</van-button>
      <span v-else class="muted">没有更多了</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { transactionsApi, type Transaction, type TransactionsQuery } from '../../api/transactions'
import type { ApiError } from '../../api/client'

const route = useRoute(); const router = useRouter()
const filters = reactive({ description: String(route.query.description || ''), transaction_type: String(route.query.transaction_type || ''), start_date: String(route.query.start_date || ''), end_date: String(route.query.end_date || ''), account: String(route.query.account || ''), tags: String(route.query.tags || '') })
const items = ref<Transaction[]>([]); const cursor = ref<string | null>(null); const hasMore = ref(false)
const loading = ref(false); const loadingMore = ref(false); const error = ref('')
function query(): TransactionsQuery { return { limit: 20, description: filters.description || undefined, transaction_type: filters.transaction_type as TransactionsQuery['transaction_type'] || undefined, start_date: filters.start_date || undefined, end_date: filters.end_date || undefined, account: filters.account || undefined, tags: filters.tags || undefined } }
async function load(reset = true) { loading.value = true; error.value = ''; try { const page = await transactionsApi.getTransactions(query()); items.value = page.items; cursor.value = page.next_cursor; hasMore.value = page.has_more } catch (reason) { error.value = (reason as ApiError).message; if (reset) items.value = [] } finally { loading.value = false } }
async function loadMore() { if (!cursor.value || loadingMore.value) return; loadingMore.value = true; try { const page = await transactionsApi.getTransactions({ ...query(), cursor: cursor.value }); items.value.push(...page.items); cursor.value = page.next_cursor; hasMore.value = page.has_more } catch (reason) { error.value = (reason as ApiError).message } finally { loadingMore.value = false } }
function applyFilters() { const query = Object.fromEntries(Object.entries(filters).filter(([, value]) => value)); router.replace({ path: '/transactions', query }) }
watch(() => route.query, () => { Object.assign(filters, { description: String(route.query.description || ''), transaction_type: String(route.query.transaction_type || ''), start_date: String(route.query.start_date || ''), end_date: String(route.query.end_date || ''), account: String(route.query.account || ''), tags: String(route.query.tags || '') }); load(true) })
function category(item: Transaction) { return item.postings.find(p => p.account.startsWith('Expenses:') || p.account.startsWith('Income:'))?.account || '转账' }
function amount(item: Transaction) { const posting = item.postings.find(p => p.account.startsWith('Expenses:') || p.account.startsWith('Income:')) || item.postings[0]; if (!posting) return ''; const value = item.transaction_type === 'income' ? String(posting.amount).replace('-', '') : item.transaction_type === 'expense' ? `-${posting.amount}` : posting.amount; return `${posting.currency} ${value}` }
onMounted(() => load(true))
</script>
