<template>
  <div class="category-picker">
    <div class="category-tabs">
      <button v-for="type in categoryTypes" :key="type.value" @click="selectType(type.value)" class="category-tab"
        :class="{ active: selectedType === type.value }">
        {{ type.label }}
      </button>
    </div>

    <div class="category-grid">
      <div v-for="category in currentCategories" :key="category.value" @click="selectCategory(category)"
        class="category-item" :class="{ active: modelValue === category.value }">
        <span class="category-icon">{{ category.icon }}</span>
        <span class="category-label">{{ category.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Category {
  value: string
  label: string
  icon: string
  type: 'expense' | 'income'
}

interface Props {
  modelValue?: string
  type?: 'expense' | 'income'
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: ''
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:type', value: 'expense' | 'income'): void
}>()

interface CategoryType {
  value: 'expense' | 'income'
  label: string
}

const categoryTypes: CategoryType[] = [
  { value: 'expense', label: '支出' },
  { value: 'income', label: '收入' }
]

const selectedType = ref<'expense' | 'income'>(props.type || 'expense')

const expenseCategories: Category[] = [
  { value: 'Expenses:Food:Dining', label: '餐饮', icon: '🍽️', type: 'expense' },
  { value: 'Expenses:Food:Groceries', label: '食材', icon: '🛒', type: 'expense' },
  { value: 'Expenses:Transport:Public', label: '交通', icon: '🚇', type: 'expense' },
  { value: 'Expenses:Transport:Fuel', label: '油费', icon: '⛽', type: 'expense' },
  { value: 'Expenses:Housing:Rent', label: '房租', icon: '🏠', type: 'expense' },
  { value: 'Expenses:Housing:Utilities', label: '水电', icon: '💡', type: 'expense' },
  { value: 'Expenses:Entertainment', label: '娱乐', icon: '🎮', type: 'expense' },
  { value: 'Expenses:Healthcare', label: '医疗', icon: '🏥', type: 'expense' },
  { value: 'Expenses:Education', label: '教育', icon: '📚', type: 'expense' },
  { value: 'Expenses:Shopping:Clothing', label: '服饰', icon: '👕', type: 'expense' },
  { value: 'Expenses:Shopping:Electronics', label: '数码', icon: '📱', type: 'expense' },
  { value: 'Expenses:Other', label: '其他', icon: '📝', type: 'expense' }
]

const incomeCategories: Category[] = [
  { value: 'Income:Salary', label: '工资', icon: '💰', type: 'income' },
  { value: 'Income:Bonus', label: '奖金', icon: '🎁', type: 'income' },
  { value: 'Income:Investment', label: '投资', icon: '📈', type: 'income' },
  { value: 'Income:Gift', label: '礼金', icon: '🧧', type: 'income' },
  { value: 'Income:Refund', label: '退款', icon: '↩️', type: 'income' },
  { value: 'Income:Other', label: '其他', icon: '📝', type: 'income' }
]

const currentCategories = computed(() => {
  return selectedType.value === 'expense' ? expenseCategories : incomeCategories
})

function selectType(type: 'expense' | 'income') {
  selectedType.value = type
  emit('update:type', type)
}

function selectCategory(category: Category) {
  emit('update:modelValue', category.value)
}
</script>

<style scoped>
.category-picker {
  width: 100%;
}

.category-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.category-tab {
  flex: 1;
  padding: 10px 16px;
  border: 1px solid var(--separator);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.category-tab.active {
  background: var(--f7-theme-color);
  color: white;
  border-color: var(--f7-theme-color);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.category-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 8px;
  border: 1px solid var(--separator);
  border-radius: 8px;
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.category-item:hover {
  border-color: var(--f7-theme-color);
  background: var(--bg-tertiary);
}

.category-item.active {
  border-color: var(--f7-theme-color);
  background: var(--f7-theme-color-rgb, 0.1);
  /* 注意：需要确保 CSS 变量回退值有效 */
  background-color: rgba(var(--f7-theme-color-rgb), 0.1);
}

.category-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.category-label {
  font-size: 14px;
  color: var(--text-primary);
  text-align: center;
}

.category-item.active .category-label {
  font-weight: 600;
  color: var(--f7-theme-color);
}
</style>
