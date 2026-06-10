<template>
  <div class="page-container">
    <div class="page-header">
      <h2>智能分析</h2>
      <p>基于 Agent 的成本 / 进度 / 安全 / 风险分析与周报生成</p>
    </div>

    <el-card shadow="never" class="mb">
      <div class="toolbar">
        <el-input v-model="projectId" placeholder="输入项目 ID" style="width: 280px" clearable />
        <el-radio-group v-model="agentType">
          <el-radio-button value="cost">成本</el-radio-button>
          <el-radio-button value="progress">进度</el-radio-button>
          <el-radio-button value="safety">安全</el-radio-button>
          <el-radio-button value="risk">风险</el-radio-button>
          <el-radio-button value="weekly">周报</el-radio-button>
        </el-radio-group>
        <el-button type="primary" :loading="loading" @click="run">开始分析</el-button>
        <el-button :loading="dashLoading" @click="loadDashboard">加载看板</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" class="mb" v-if="dashboard">
      <el-col :span="8" v-for="d in dashCards" :key="d.title">
        <el-card shadow="never">
          <div class="dash-title">{{ d.title }}</div>
          <el-tag :type="riskType(d.risk)" size="large">风险：{{ d.risk || '未知' }}</el-tag>
          <div class="dash-metrics">
            <div v-for="(v, k) in d.metrics" :key="k"><span>{{ k }}</span><b>{{ v }}</b></div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" v-if="result">
      <div class="result-head">
        <span>分析结果（{{ result.agent_type }}）</span>
        <el-tag v-if="result.execution_time">{{ result.execution_time.toFixed(2) }}s</el-tag>
      </div>
      <pre class="result-body">{{ pretty(result.result || result) }}</pre>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api'

const projectId = ref('')
const agentType = ref('cost')
const loading = ref(false)
const dashLoading = ref(false)
const result = ref(null)
const dashboard = ref(null)

const callers = {
  cost: agentApi.costAnalysis,
  progress: agentApi.progressAnalysis,
  safety: agentApi.safetyAnalysis,
  risk: agentApi.riskAnalysis,
  weekly: agentApi.weeklyReport,
}

async function run() {
  if (!projectId.value.trim()) return ElMessage.warning('请输入项目 ID')
  loading.value = true
  result.value = null
  try {
    result.value = await callers[agentType.value]({ project_id: projectId.value.trim() })
  } finally {
    loading.value = false
  }
}

async function loadDashboard() {
  if (!projectId.value.trim()) return ElMessage.warning('请输入项目 ID')
  dashLoading.value = true
  try {
    dashboard.value = await agentApi.dashboard(projectId.value.trim())
  } finally {
    dashLoading.value = false
  }
}

const dashCards = computed(() => {
  const d = dashboard.value
  if (!d) return []
  return [
    { title: '进度', risk: d.progress?.risk_level, metrics: d.progress || {} },
    { title: '成本', risk: d.cost?.risk_level, metrics: d.cost || {} },
    { title: '安全', risk: d.safety?.risk_level, metrics: d.safety || {} },
  ]
})

function riskType(r) {
  if (!r) return 'info'
  const s = String(r).toLowerCase()
  if (s.includes('high') || s.includes('高')) return 'danger'
  if (s.includes('medium') || s.includes('中')) return 'warning'
  return 'success'
}
const pretty = (o) => JSON.stringify(o, null, 2)
</script>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.dash-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
}
.dash-metrics {
  margin-top: 12px;
  font-size: 13px;
}
.dash-metrics div {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  color: #555;
}
.result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 600;
}
.result-body {
  background: #0d1117;
  color: #c9d1d9;
  padding: 16px;
  border-radius: 6px;
  max-height: 520px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
}
</style>
