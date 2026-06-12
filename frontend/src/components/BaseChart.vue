<template>
  <div ref="el" class="base-chart" :style="{ height }" />
</template>

<script setup>
import { ref, shallowRef, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ZHUJIAN_THEME } from '@/charts/theme'

// 封装 ECharts：自动 init/resize/dispose，套用 zhujian 主题
const props = defineProps({
  option: { type: Object, required: true },
  height: { type: String, default: '320px' },
  // dark 用暗色看板背景；theme 可覆盖
  theme: { type: String, default: ZHUJIAN_THEME },
  autoresize: { type: Boolean, default: true },
})

const el = ref(null)
const chart = shallowRef(null)
let ro = null

function init() {
  if (!el.value) return
  chart.value = echarts.init(el.value, props.theme)
  chart.value.setOption(props.option || {})
}

function resize() {
  chart.value && chart.value.resize()
}

watch(
  () => props.option,
  (opt) => {
    if (chart.value) chart.value.setOption(opt || {}, true)
  },
  { deep: true }
)

watch(
  () => props.theme,
  async () => {
    dispose()
    await nextTick()
    init()
  }
)

function dispose() {
  if (chart.value) {
    chart.value.dispose()
    chart.value = null
  }
}

onMounted(() => {
  init()
  if (props.autoresize && el.value) {
    ro = new ResizeObserver(() => resize())
    ro.observe(el.value)
  }
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  if (ro) {
    ro.disconnect()
    ro = null
  }
  window.removeEventListener('resize', resize)
  dispose()
})

// 暴露实例供高级用法
defineExpose({ getChart: () => chart.value, resize })
</script>

<style scoped>
.base-chart {
  width: 100%;
}
</style>
