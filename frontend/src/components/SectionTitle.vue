<template>
  <div class="section-title">
    <span class="bar" />
    <span class="text">{{ title }}</span>
    <span v-if="extra" class="extra">{{ extra }}</span>
    <div v-if="$slots.default" class="slot">
      <slot />
    </div>
  </div>
</template>

<script setup>
// 小节标题
defineProps({
  title: { type: String, default: '' },
  extra: { type: String, default: '' },
})
</script>

<style scoped>
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 12px;
}
.bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: var(--c-primary);
}
.text {
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
}
.extra {
  font-size: 12px;
  color: var(--c-text-3);
}
.slot {
  margin-left: auto;
}
</style>
