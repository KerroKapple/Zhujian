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

    <template v-if="dashboard">
      <el-card shadow="never" class="mb overall">
        <span class="dash-title">综合风险</span>
        <el-tag :type="riskType(dashboard.overall_risk_level)" size="large" effect="dark">
          {{ dashboard.overall_risk_level || '未知' }}
        </el-tag>
        <span class="dash-time" v-if="dashboard.project_name">项目：{{ dashboard.project_name }}</span>
      </el-card>
      <el-row :gutter="16" class="mb">
        <el-col :span="8" v-for="d in dashCards" :key="d.title">
          <el-card shadow="never">
            <div class="dash-title">{{ d.title }}</div>
            <el-tag :type="riskType(d.risk)" size="large">风险：{{ d.risk || '未知' }}</el-tag>
            <div class="dash-metrics">
              <div v-for="(v, k) in d.metrics" :key="k"><span>{{ metricLabel(k) }}</span><b>{{ v }}</b></div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>

    <el-card shadow="never" v-if="result">
      <div class="result-head">
        <span>分析结果（{{ result.agent_type || agentType }}）</span>
        <el-tag v-if="result.execution_time != null">{{ result.execution_time.toFixed(2) }}s</el-tag>
      </div>
      <el-alert
        v-if="result.success === false"
        :title="result.error || '执行失败'"
        type="error"
        :closable="false"
        class="mb"
      />
      <!-- 周报：result.result.report 为 Markdown/HTML 文本，直接渲染 -->
      <pre v-if="reportText" class="result-body report">{{ reportText }}</pre>
      <!-- 其他分析：结构化 JSON 展示 -->
      <pre v-else class="result-body">{{ pretty(result.result || result) }}</pre>
    </el-card>

    <el-empty v-else-if="!dashboard" description="输入项目 ID 后开始分析或加载看板" />
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
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    loading.value = false
  }
}

async function loadDashboard() {
  if (!projectId.value.trim()) return ElMessage.warning('请输入项目 ID')
  dashLoading.value = true
  try {
    dashboard.value = await agentApi.dashboard(projectId.value.trim())
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    dashLoading.value = false
  }
}

// 周报返回 result.report 为文本（Markdown/HTML），其余分析为结构化对象
const reportText = computed(() => {
  const r = result.value?.result
  if (r && typeof r.report === 'string') return r.report
  return ''
})

const dashCards = computed(() => {
  const d = dashboard.value
  if (!d) return []
  return [
    { title: '进度', risk: d.progress?.risk_level, metrics: d.progress || {} },
    { title: '成本', risk: d.cost?.risk_level, metrics: d.cost || {} },
    { title: '安全', risk: d.safety?.risk_level, metrics: d.safety || {} },
  ]
})

const metricLabels = {
  overall_progress: '总进度',
  spi: 'SPI',
  delayed_tasks: '延期任务',
  budget_usage_rate: '预算使用率',
  cpi: 'CPI',
  variance_rate: '偏差率',
  pass_rate: '合格率',
  open_defects: '未关闭缺陷',
  high_defects: '高危缺陷',
  risk_level: '风险等级',
}
const metricLabel = (k) => metricLabels[k] || k

function riskType(r) {
  if (!r) return 'info'
  const s = String(r).toLowerCase()
  if (s.includes('high') || s.includes('critical') || s.includes('red') || s.includes('高') || s.includes('严重')) return 'danger'
  if (s.includes('medium') || s.includes('yellow') || s.includes('中')) return 'warning'
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
.overall {
  display: flex;
  align-items: center;
  gap: 16px;
}
.overall .dash-title {
  margin-bottom: 0;
}
.dash-time {
  color: #8a8f99;
  font-size: 13px;
}
.report {
  background: #fff;
  color: #1f2329;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  border: 1px solid #eef0f3;
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
