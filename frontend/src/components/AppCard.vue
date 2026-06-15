<template>
  <div class="app-card" :class="{ 'no-shadow': !shadow, 'has-strip': !!status }">
    <div v-if="status" class="strip" :style="{ background: stripColor }" />
    <div v-if="title || $slots.title || $slots.extra" class="app-card-head">
      <div class="app-card-title">
        <slot name="title">{{ title }}</slot>
      </div>
      <div v-if="$slots.extra" class="app-card-extra">
        <slot name="extra" />
      </div>
    </div>
    <div class="app-card-body" v-loading="loading">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// 白卡片：标题 + 右上操作位 + 内容；可选 loading/shadow + 左侧彩色状态条
const props = defineProps({
  title: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  shadow: { type: Boolean, default: true },
  // 左侧状态条语义色：success/warning/danger/info/primary
  status: { type: String, default: '' },
})

const STATUS_COLOR = {
  success: 'var(--c-success)',
  warning: 'var(--c-warning)',
  danger: 'var(--c-danger)',
  info: 'var(--c-text-2)',
  primary: 'var(--c-primary)',
}
const stripColor = computed(() => STATUS_COLOR[props.status] || 'var(--c-primary)')
</script>

<style scoped>
.app-card {
  position: relative;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.app-card.no-shadow {
  box-shadow: none;
}
.strip {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}
.app-card.has-strip .app-card-head,
.app-card.has-strip .app-card-body {
  padding-left: calc(var(--sp-5) + 3px);
}
.app-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--c-border);
}
.app-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--c-text);
}
.app-card-extra {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.app-card-body {
  padding: var(--sp-5);
}
</style>
