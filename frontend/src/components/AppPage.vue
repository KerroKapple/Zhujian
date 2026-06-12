<template>
  <div class="app-page">
    <div v-if="title || description || $slots.actions" class="app-page-head">
      <div class="app-page-titles">
        <h2 v-if="title" class="app-page-title">{{ title }}</h2>
        <p v-if="description" class="app-page-desc">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="app-page-actions">
        <slot name="actions" />
      </div>
    </div>
    <div class="app-page-body">
      <slot />
    </div>
  </div>
</template>

<script setup>
// 页头（标题/描述/右侧操作位）+ 默认内容插槽
defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})
</script>

<style scoped>
.app-page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.app-page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-4);
}
.app-page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--c-text);
}
.app-page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--c-text-2);
}
.app-page-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-shrink: 0;
}
</style>
