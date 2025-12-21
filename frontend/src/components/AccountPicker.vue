<template>
  <div class="account-picker">
    <input
      type="text"
      :value="modelValue"
      @click="openPicker"
      readonly
      :placeholder="placeholder"
      class="account-input"
    />
    
    <div v-if="isOpen" class="account-picker-modal" @click.self="closePicker">
      <div class="account-picker-content">
        <div class="account-picker-header">
          <h3>选择账户</h3>
          <button @click="closePicker" class="close-btn">×</button>
        </div>
        
        <div class="account-picker-body">
          <div class="search-box">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索账户..."
              class="search-input"
            />
          </div>
          
          <div class="account-list">
            <div
              v-for="account in filteredAccounts"
              :key="account.name"
              class="account-item"
              :class="{ 'has-children': account.children && account.children.length > 0 }"
            >
              <div
                class="account-item-header"
                @click="selectAccount(account)"
              >
                <span class="account-name">{{ account.name }}</span>
                <span class="account-type">{{ account.type }}</span>
              </div>
              
              <div v-if="account.children && account.children.length > 0" class="account-children">
                <div
                  v-for="child in account.children"
                  :key="child.name"
                  class="account-item child"
                  @click="selectAccount(child)"
                >
                  <span class="account-name">{{ child.name }}</span>
                  <span class="account-type">{{ child.type }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { accountsApi, type Account } from '../api/accounts'

interface Props {
  modelValue?: string
  placeholder?: string
  accountType?: string
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: '选择账户'
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const isOpen = ref(false)
const searchQuery = ref('')
const accounts = ref<Account[]>([])

const filteredAccounts = computed(() => {
  if (!searchQuery.value) {
    return props.accountType
      ? accounts.value.filter(acc => acc.type === props.accountType)
      : accounts.value
  }
  
  const query = searchQuery.value.toLowerCase()
  return accounts.value
    .filter(acc => {
      if (props.accountType && acc.type !== props.accountType) {
        return false
      }
      return acc.name.toLowerCase().includes(query)
    })
})

function openPicker() {
  isOpen.value = true
}

function closePicker() {
  isOpen.value = false
  searchQuery.value = ''
}

function selectAccount(account: Account) {
  emit('update:modelValue', account.name)
  closePicker()
}

async function loadAccounts() {
  try {
    accounts.value = await accountsApi.getAccounts()
  } catch (error) {
    console.error('Failed to load accounts:', error)
  }
}

onMounted(() => {
  loadAccounts()
})
</script>

<style scoped>
.account-picker {
  position: relative;
}

.account-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  background: white;
}

.account-picker-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 1000;
}

.account-picker-content {
  background: white;
  width: 100%;
  max-height: 70vh;
  border-radius: 16px 16px 0 0;
  display: flex;
  flex-direction: column;
}

.account-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e0e0e0;
}

.account-picker-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  font-size: 32px;
  cursor: pointer;
  color: #666;
  line-height: 1;
  padding: 0;
}

.account-picker-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.search-box {
  margin-bottom: 16px;
}

.search-input {
  width: 100%;
  padding: 10px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
}

.account-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.account-item {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.account-item-header {
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  background: white;
  transition: background 0.2s;
}

.account-item-header:hover {
  background: #f5f5f5;
}

.account-name {
  font-size: 16px;
  font-weight: 500;
  color: #333;
}

.account-type {
  font-size: 12px;
  color: #999;
  background: #f0f0f0;
  padding: 4px 8px;
  border-radius: 4px;
}

.account-children {
  background: #f9f9f9;
  border-top: 1px solid #e0e0e0;
}

.account-item.child {
  border: none;
  border-radius: 0;
  border-bottom: 1px solid #e0e0e0;
}

.account-item.child:last-child {
  border-bottom: none;
}

.account-item.child .account-item-header {
  background: #f9f9f9;
  padding-left: 32px;
}

.account-item.child .account-item-header:hover {
  background: #f0f0f0;
}
</style>
