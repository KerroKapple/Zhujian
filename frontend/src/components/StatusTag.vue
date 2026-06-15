<template>
  <el-tag :type="elType" :effect="effect" round disable-transitions>{{ displayText }}</el-tag>
</template>

<script setup>
import { computed } from 'vue'

// 按语义/中英风险词映射颜色的标签
const props = defineProps({
  // 高/中/低 | red/yellow/green | success/warning/danger/info | 自定义文案
  status: { type: String, default: 'info' },
  text: { type: String, default: '' },
  effect: { type: String, default: 'light' }, // light/dark/plain
})

// 归一化到 Element Plus type
const MAP = {
  高: { type: 'danger', text: '高风险' },
  中: { type: 'warning', text: '中风险' },
  低: { type: 'success', text: '低风险' },
  red: { type: 'danger', text: '高' },
  yellow: { type: 'warning', text: '中' },
  green: { type: 'success', text: '低' },
  danger: { type: 'danger', text: '危险' },
  warning: { type: 'warning', text: '警告' },
  success: { type: 'success', text: '正常' },
  info: { type: 'info', text: '信息' },
  primary: { type: 'primary', text: '' },
}

const matched = computed(() => MAP[props.status] || { type: 'info', text: props.status })
const elType = computed(() => matched.value.type)
const displayText = computed(() => props.text || matched.value.text || props.status)
</script>
