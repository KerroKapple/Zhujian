<template>
  <div class="stat-tile">
    <span class="strip" :style="{ background: statusColor }" />
    <div class="stat-main">
      <div class="stat-label">{{ label }}</div>
      <div class="stat-value-row">
        <span class="stat-value">{{ value }}</span>
        <span v-if="unit" class="stat-unit">{{ unit }}</span>
      </div>
      <div v-if="trend !== null && trend !== undefined && trend !== ''" class="stat-trend" :class="trendDir">
        <el-icon><CaretTop v-if="trendDir === 'up'" /><CaretBottom v-else-if="trendDir === 'down'" /><Minus v-else /></el-icon>
        <span>{{ trendText }}</span>
      </div>
    </div>
    <div v-if="icon" class="stat-icon" :style="{ color: statusColor, background: iconBg }">
      <el-icon><component :is="icon" /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { CaretTop, CaretBottom, Minus } from '@element-plus/icons-vue'

// 指标卡：label/value/unit/trend/status 语义色/可选 icon
const props = defineProps({
  label: { type: String, default: '' },
  value: { type: [String, Number], default: '-' },
  unit: { type: String, default: '' },
  // 趋势：数值(正升负降)或字符串
  trend: { type: [String, Number], default: null },
  status: { type: String, default: 'info' }, // success/warning/danger/info
  icon: { type: [String, Object], default: '' },
})

const STATUS_COLOR = {
  success: 'var(--c-success)',
  warning: 'var(--c-warning)',
  danger: 'var(--c-danger)',
  info: 'var(--c-primary)',
}
const statusColor = computed(() => STATUS_COLOR[props.status] || STATUS_COLOR.info)
const iconBg = computed(() => {
  const m = {
    success: 'rgba(45,164,78,.1)',
    warning: 'rgba(210,153,34,.1)',
    danger: 'rgba(207,34,46,.1)',
    info: 'rgba(31,111,235,.1)',
  }
  return m[props.status] || m.info
})

const trendDir = computed(() => {
  const t = props.trend
  if (typeof t === 'number') return t > 0 ? 'up' : t < 0 ? 'down' : 'flat'
  return 'flat'
})
const trendText = computed(() => {
  const t = props.trend
  if (typeof t === 'number') return `${t > 0 ? '+' : ''}${t}%`
  return t
})
</script>

<style scoped>
.stat-tile {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  padding: var(--sp-4) var(--sp-5);
  overflow: hidden;
}
.strip {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}
.stat-label {
  font-size: 13px;
  color: var(--c-text-2);
}
.stat-value-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 6px;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 1.1;
}
.stat-unit {
  font-size: 13px;
  color: var(--c-text-2);
}
.stat-trend {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 6px;
  font-size: 12px;
}
.stat-trend.up {
  color: var(--c-success);
}
.stat-trend.down {
  color: var(--c-danger);
}
.stat-trend.flat {
  color: var(--c-text-2);
}
.stat-icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  border-radius: var(--r-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
</style>
