<template>
  <div class="tree-section">
    <h2 class="section-title">{{ title }}</h2>
    <van-empty v-if="!items.length" description="暂无数据" />
    <van-cell-group v-else inset>
      <template v-for="node in visible" :key="node.account">
        <van-cell
          :title="node.display_name || node.account"
          :label="node.account"
          is-link
          :style="{ paddingLeft: `${12 + node.depth * 12}px` }"
          @click="onClick(node)"
        >
          <template #value>
            <div class="amount-col">
              <strong>{{ formatAmountDisplay(node.total_cny, 2) }}</strong>
              <small v-if="showPercentage && percentageText(node)">{{ percentageText(node) }}</small>
              <small v-for="(amt, cur) in node.balances" :key="String(cur)">{{ cur }} {{ formatAmountDisplay(String(amt), 2) }}</small>
            </div>
          </template>
          <template #right-icon>
            <van-icon
              v-if="node.children?.length"
              :name="expanded.has(node.account) ? 'arrow-down' : 'arrow'"
              class="expand-icon"
              @click.stop="toggle(node.account)"
            />
          </template>
        </van-cell>
      </template>
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { formatAmountDisplay } from '../../utils/decimal'

export type TreeItem = {
  account: string
  display_name?: string
  balances?: Record<string, string>
  total_cny: string
  percentage?: string
  children?: TreeItem[]
  depth: number
}

const props = withDefaults(defineProps<{
  title: string
  items: TreeItem[]
  amountKey?: string
  showPercentage?: boolean
}>(), {
  amountKey: 'balances',
  showPercentage: false,
})

const emit = defineEmits<{ (event: 'open', account: string): void }>()
const expanded = ref<Set<string>>(new Set())

const visible = computed(() => {
  const result: TreeItem[] = []
  function walk(list: TreeItem[], depth = 0) {
    for (const item of list) {
      result.push({ ...item, depth: item.depth ?? depth })
      if (item.children?.length && expanded.value.has(item.account)) {
        walk(item.children, depth + 1)
      }
    }
  }
  walk(props.items)
  return result
})

function percentageText(node: TreeItem): string {
  if (node.percentage == null || node.percentage === '') return ''
  return `${formatAmountDisplay(String(node.percentage), 2)}%`
}

function toggle(account: string) {
  const next = new Set(expanded.value)
  if (next.has(account)) next.delete(account)
  else next.add(account)
  expanded.value = next
}

function onClick(node: TreeItem) {
  if (node.children?.length) {
    toggle(node.account)
    return
  }
  emit('open', node.account)
}
</script>

<style scoped>
.tree-section :deep(.van-cell-group--inset) {
  margin-left: 0;
  margin-right: 0;
}
.section-title { margin: 16px 0 8px; font-size: 15px; }
.amount-col { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.amount-col small { color: var(--bm-muted, #888); font-size: 11px; }
.expand-icon { margin-left: 4px; color: var(--bm-muted, #888); }
</style>
