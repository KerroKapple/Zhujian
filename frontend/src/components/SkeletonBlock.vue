<template>
  <div class="skeleton-block">
    <div
      v-for="i in rows"
      :key="i"
      class="skeleton-row"
      :style="{ width: rowWidth(i), height: height }"
    />
  </div>
</template>

<script setup>
// 骨架占位
const props = defineProps({
  rows: { type: Number, default: 3 },
  height: { type: String, default: '14px' },
  gap: { type: String, default: '12px' },
})

// 末行略短，更自然
function rowWidth(i) {
  return i === props.rows ? '60%' : '100%'
}
</script>

<style scoped>
.skeleton-block {
  display: flex;
  flex-direction: column;
  gap: v-bind(gap);
  width: 100%;
}
.skeleton-row {
  border-radius: var(--r-sm);
  background: linear-gradient(90deg, #eef1f5 25%, #e3e8ef 37%, #eef1f5 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
}
@keyframes skeleton-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}
</style>
