<template>
  <f7-treeview-item
    :label="displayName"
    :icon="icon"
    :toggle="hasChildren"
    @click="onItemClick"
  >
    <template #root-start>
        <!-- Icon slot if needed -->
    </template>
    
    <template v-if="hasChildren">
      <AccountTreeItem
        v-for="child in account.children"
        :key="child.name"
        :account="child"
        @select="(name) => $emit('select', name)"
      />
    </template>
  </f7-treeview-item>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Account } from '../api/accounts'

const props = defineProps<{
  account: Account
}>()

const emit = defineEmits<{
  (e: 'select', name: string): void
}>()

const hasChildren = computed(() => props.account.children && props.account.children.length > 0)

const displayName = computed(() => {
  const parts = props.account.name.split(':')
  return parts[parts.length - 1]
})

const icon = computed(() => {
    // Simple icon mapping based on root type or conventions could go here
    return hasChildren.value ? 'f7:folder' : 'f7:document_text'
    // Note: F7 custom icons require configuration. I'll leave it blank or use text icons if needed.
    // actually f7-treeview-item has 'icon' prop for F7 icons or material icons.
    // Let's just use default styling for now.
    return undefined
})

function onItemClick(e: any) {
    // If it has children, Framework7 handles the toggle via the 'toggle' prop logic usually.
    // However, we want to allow selecting this node.
    // If we want to support specific selection distinct from toggle:
    // We can rely on the user clicking the text vs the arrow.
    // But f7-treeview-item wraps the whole thing.
    
    // Simplification for this task:
    // Always select on click.
    // If it has children, it ALSO toggles.
    // This might be annoying (selecting closes the popup).
    
    // Better UX:
    // If has children -> Click toggles. 
    // If no children -> Click selects.
    // BUT what if user wants to select a parent category?
    // Let's assume for now we only select leaf nodes OR we add a specific "Select" action?
    // Let's stick to "Click selects" and see.
    // Wait, the Requirement says "Categorize... Tree structure".
    // Usually you categorize to a leaf.
    
    // Let's implement dynamic logic:
    // If has children, we don't emit select immediately?
    // No, Beancount allows selecting parents.
    
    // Let's emit select. The parent popup handles closing.
    // If I want to just expand, I should click the arrow.
    // Does F7 TreeViewItem have a separate arrow click?
    // Yes, usually the `.treeview-toggle` element.
    
    // I will assume clicking the main body selects.
    // To avoid closing the popup when I just wanted to toggle,
    // I need to know if the user clicked the toggle arrow.
    
    if (e.target && e.target.closest('.treeview-toggle')) {
        // It was a toggle click, do not select
        return
    }
    
    emit('select', props.account.name)
}
</script>
