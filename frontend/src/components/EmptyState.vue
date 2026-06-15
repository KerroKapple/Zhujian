<template>
  <div class="empty-state">
    <el-icon class="empty-icon"><component :is="icon" /></el-icon>
    <div class="empty-title">{{ title }}</div>
    <div v-if="description" class="empty-desc">{{ description }}</div>
    <div v-if="$slots.default" class="empty-action">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { Box } from '@element-plus/icons-vue'

// 空态：图标 + 文案 + 可选操作（默认插槽）
defineProps({
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
  icon: { type: [String, Object], default: () => Box },
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 16px;
  text-align: center;
}
.empty-icon {
  font-size: 48px;
  color: var(--c-text-3);
}
.empty-title {
  font-size: 14px;
  color: var(--c-text-2);
}
.empty-desc {
  font-size: 12px;
  color: var(--c-text-3);
  max-width: 360px;
}
.empty-action {
  margin-top: 8px;
}
</style>
