<template>
  <div class="page-container">
    <div class="page-header">
      <h2>知识图谱</h2>
      <p>可视化施工图实体关系网络</p>
    </div>

    <el-row :gutter="16" class="mb">
      <el-col :span="6" v-for="s in statCards" :key="s.label">
        <el-card shadow="never">
          <div class="metric-value">{{ s.value }}</div>
          <div class="metric-label">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <div class="toolbar">
        <el-input v-model="docId" placeholder="输入文档 ID 加载图谱" style="width: 320px" clearable />
        <el-button type="primary" :loading="loading" @click="loadGraph">加载图谱</el-button>
      </div>
      <div ref="chartRef" class="chart" v-loading="loading"></div>
      <el-empty v-if="!hasData && !loading" description="输入文档 ID 后加载可视化图谱" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onActivated, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { graphApi } from '@/api'

const chartRef = ref(null)
const docId = ref('')
const loading = ref(false)
const hasData = ref(false)
const statCards = ref([
  { label: '节点总数', value: 0 },
  { label: '关系总数', value: 0 },
  { label: '节点类型', value: 0 },
  { label: '关系类型', value: 0 },
])
let chart = null

function initChart() {
  if (!chart && chartRef.value) {
    chart = echarts.init(chartRef.value)
    window.addEventListener('resize', resize)
  }
}
function resize() {
  chart && chart.resize()
}

async function loadStats() {
  try {
    const res = await graphApi.statistics()
    statCards.value[0].value = res.total_nodes ?? 0
    statCards.value[1].value = res.total_relationships ?? 0
    statCards.value[2].value = Object.keys(res.node_labels || {}).length
    statCards.value[3].value = Object.keys(res.relationship_types || {}).length
  } catch (e) {
    /* 忽略统计失败 */
  }
}

async function loadGraph() {
  if (!docId.value.trim()) {
    ElMessage.warning('请输入文档 ID')
    return
  }
  loading.value = true
  try {
    const res = await graphApi.visualization(docId.value.trim(), { max_nodes: 200 })
    await nextTick()
    initChart()
    chart.setOption({
      tooltip: {},
      legend: [{ data: (res.categories || []).map((c) => c.name) }],
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          draggable: true,
          label: { show: true, position: 'right' },
          force: { repulsion: 120, edgeLength: 80 },
          categories: res.categories || [],
          data: (res.nodes || []).map((n) => ({
            id: String(n.id),
            name: n.name,
            category: n.category,
            symbolSize: n.symbolSize || 20,
          })),
          links: (res.edges || []).map((e) => ({
            source: String(e.source),
            target: String(e.target),
            value: e.value,
          })),
        },
      ],
    })
    hasData.value = (res.nodes || []).length > 0
    if (!hasData.value) ElMessage.info('该文档暂无图谱数据')
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
onActivated(resize)
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
  chart = null
})
</script>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.metric-label {
  color: #8a8f99;
  font-size: 13px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.chart {
  width: 100%;
  height: 560px;
}
</style>
