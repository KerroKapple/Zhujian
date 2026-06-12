<template>
  <div class="agents-board">
    <div class="board-head">
      <div>
        <h2>智能分析</h2>
        <p>成本 / 进度 / 安全 / 风险 / 周报 · 五类 Agent 项目体检台</p>
      </div>
      <div class="head-tools">
        <el-select
          v-model="projectId"
          class="proj-select"
          filterable
          allow-create
          default-first-option
          clearable
          :teleported="false"
          placeholder="输入或选择项目 ID"
        >
          <el-option v-for="p in projectOptions" :key="p.value" :label="p.label" :value="p.value" />
        </el-select>
        <el-button type="primary" :loading="dashLoading" @click="loadDashboard">加载看板</el-button>
      </div>
    </div>

    <!-- 综合看板 -->
    <template v-if="dashboard">
      <div class="overall-bar">
        <span class="overall-label">综合风险</span>
        <span class="risk-pill" :style="riskStyle(dashboard.overall_risk_level)">
          {{ riskText(dashboard.overall_risk_level) }}
        </span>
        <span class="overall-meta" v-if="dashboard.project_name">{{ dashboard.project_name }}</span>
        <span class="overall-meta" v-if="dashboard.last_updated">更新于 {{ shortTime(dashboard.last_updated) }}</span>
      </div>
      <div class="tile-row">
        <div v-for="c in dashCards" :key="c.title" class="d-tile">
          <span class="tile-strip" :style="{ background: riskColor(c.risk) }" />
          <div class="tile-head">
            <span class="tile-label">{{ c.title }}</span>
            <span class="risk-pill sm" :style="riskStyle(c.risk)">{{ riskText(c.risk) }}</span>
          </div>
          <div class="tile-metrics">
            <div v-for="m in c.metrics" :key="m.label">
              <span>{{ m.label }}</span><b>{{ m.value }}</b>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div class="board-main">
      <!-- 左列：快速体检 + 深度分析 -->
      <div class="board-col">
        <div class="board-card">
          <div class="card-head">
            <span class="card-title">快速体检</span>
            <el-button class="ghost-btn" size="small" :loading="quickRunning" @click="runQuickChecks">
              一键体检
            </el-button>
          </div>
          <div class="quick-grid">
            <div v-for="q in quickList" :key="q.key" class="quick-card" v-loading="q.loading" element-loading-background="rgba(13,17,23,.7)">
              <div class="quick-head">
                <span>{{ q.title }}</span>
                <span v-if="q.risk" class="risk-pill sm" :style="riskStyle(q.risk)">{{ riskText(q.risk) }}</span>
              </div>
              <div v-if="q.metrics.length" class="quick-metrics">
                <div v-for="m in q.metrics" :key="m.label"><span>{{ m.label }}</span><b>{{ m.value }}</b></div>
              </div>
              <div v-else class="quick-empty">{{ q.error || '暂未体检' }}</div>
            </div>
          </div>
        </div>

        <div class="board-card">
          <div class="card-head">
            <span class="card-title">深度分析</span>
            <div class="analysis-tools">
              <el-radio-group v-model="agentType" size="small">
                <el-radio-button v-for="t in AGENT_TYPES" :key="t.value" :value="t.value">{{ t.label }}</el-radio-button>
              </el-radio-group>
              <el-button type="primary" size="small" :loading="running" @click="runAnalysis">开始分析</el-button>
            </div>
          </div>
          <div v-loading="running" element-loading-background="rgba(13,17,23,.7)" element-loading-text="Agent 分析中，可能需要数十秒…">
            <template v-if="result">
              <div class="result-meta">
                <el-tag size="small" :type="result.success === false ? 'danger' : 'success'" effect="dark">
                  {{ result.success === false ? '失败' : '完成' }}
                </el-tag>
                <span v-if="result.execution_time != null">{{ Number(result.execution_time).toFixed(2) }}s</span>
                <span v-if="result.error" class="result-error">{{ result.error }}</span>
              </div>
              <pre v-if="reportText" class="result-body report">{{ reportText }}</pre>
              <pre v-else class="result-body">{{ pretty(result.result || result) }}</pre>
            </template>
            <EmptyState
              v-else
              title="暂无分析结果"
              description="选择项目与分析类型后开始；周报输出文本报告，其余输出结构化指标"
            />
          </div>
        </div>
      </div>

      <!-- 右列：工作流日志 -->
      <div class="board-card log-card">
        <div class="card-head">
          <span class="card-title">工作流日志</span>
          <el-button class="ghost-btn" size="small" :loading="logsLoading" @click="loadWorkflows">刷新</el-button>
        </div>
        <el-table
          :data="workflows"
          size="small"
          max-height="560"
          v-loading="logsLoading"
          element-loading-background="rgba(13,17,23,.7)"
        >
          <template #empty><EmptyState title="暂无执行记录" description="发起分析后此处展示 Agent 工作流轨迹" /></template>
          <el-table-column prop="workflow_type" label="类型" width="120" show-overflow-tooltip />
          <el-table-column prop="project_id" label="项目" width="100" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" effect="dark" :type="logStatusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80" align="right">
            <template #default="{ row }">
              {{ row.duration_seconds != null ? `${row.duration_seconds.toFixed(1)}s` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="140">
            <template #default="{ row }">{{ shortTime(row.start_time) }}</template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi, projectApi } from '@/api'
import EmptyState from '@/components/EmptyState.vue'

const AGENT_TYPES = [
  { value: 'cost', label: '成本' },
  { value: 'progress', label: '进度' },
  { value: 'safety', label: '安全' },
  { value: 'risk', label: '风险' },
  { value: 'weekly', label: '周报' },
]

// green/yellow/red 三级风险 → 暗色看板配色
const RISK = {
  green: { color: '#2dd4bf', text: '正常' },
  yellow: { color: '#f59e0b', text: '关注' },
  red: { color: '#f85149', text: '高危' },
}

const projectId = ref('')
const projectOptions = ref([])
const dashboard = ref(null)
const dashLoading = ref(false)

const agentType = ref('cost')
const running = ref(false)
const result = ref(null)

const quick = reactive({
  cost: { title: '成本', loading: false, data: null, error: '' },
  progress: { title: '进度', loading: false, data: null, error: '' },
  safety: { title: '安全', loading: false, data: null, error: '' },
  risk: { title: '风险', loading: false, data: null, error: '' },
})
const QUICK_CALLERS = {
  cost: agentApi.quickCost,
  progress: agentApi.quickProgress,
  safety: agentApi.quickSafety,
  risk: agentApi.quickRisk,
}

const workflows = ref([])
const logsLoading = ref(false)

const METRIC_LABELS = {
  overall_progress: '总进度',
  spi: 'SPI',
  cpi: 'CPI',
  delayed_tasks: '延期任务',
  budget_usage_rate: '预算使用率',
  variance_rate: '偏差率',
  pass_rate: '合格率',
  open_defects: '未闭环缺陷',
  high_defects: '高危缺陷',
  high_level_defects: '高危缺陷',
  total_risks: '风险数',
  high_risks: '高风险',
  status: '状态',
  total_budget: '总预算',
  actual_cost: '实际成本',
  total_tasks: '任务总数',
  completed_tasks: '已完成',
  total_checks: '检查数',
  risk_count: '风险数',
}

function toMetrics(obj, skip = ['risk_level', 'project_id', 'project_name', 'last_updated']) {
  if (!obj) return []
  return Object.entries(obj)
    .filter(([k, v]) => !skip.includes(k) && v !== null && typeof v !== 'object')
    .slice(0, 6)
    .map(([k, v]) => ({ label: METRIC_LABELS[k] || k, value: formatVal(k, v) }))
}

function formatVal(key, v) {
  if (typeof v !== 'number') return String(v)
  if (/rate|progress/.test(key)) return `${Number(v).toFixed(1)}%`
  return Number.isInteger(v) ? v : Number(v).toFixed(2)
}

const dashCards = computed(() => {
  const d = dashboard.value
  if (!d) return []
  return [
    { title: '进度', risk: d.progress?.risk_level, metrics: toMetrics(d.progress) },
    { title: '成本', risk: d.cost?.risk_level, metrics: toMetrics(d.cost) },
    { title: '安全', risk: d.safety?.risk_level, metrics: toMetrics(d.safety) },
  ]
})

const quickList = computed(() =>
  Object.entries(quick).map(([key, q]) => ({
    key,
    title: q.title,
    loading: q.loading,
    error: q.error,
    risk: q.data?.risk_level || q.data?.overall_risk_level || '',
    metrics: toMetrics(q.data),
  })),
)

const quickRunning = computed(() => Object.values(quick).some((q) => q.loading))

// 周报返回 result.report 文本，其余为结构化对象
const reportText = computed(() => {
  const r = result.value?.result
  return r && typeof r.report === 'string' ? r.report : ''
})

function requireProject() {
  const id = (projectId.value || '').trim()
  if (!id) ElMessage.warning('请先输入或选择项目 ID')
  return id
}

async function loadProjectOptions() {
  try {
    const res = await projectApi.list({ page: 1, page_size: 50 })
    projectOptions.value = (res.items || []).map((p) => ({
      value: p.project_id || p.id,
      label: `${p.name || p.project_name || p.project_id || p.id}（${p.project_id || p.id}）`,
    }))
  } catch (e) {
    projectOptions.value = []
  }
}

async function loadDashboard() {
  const id = requireProject()
  if (!id) return
  dashLoading.value = true
  try {
    dashboard.value = await agentApi.dashboard(id)
    runQuickChecks()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    dashLoading.value = false
  }
}

async function runQuickChecks() {
  const id = requireProject()
  if (!id) return
  await Promise.all(
    Object.entries(quick).map(async ([key, q]) => {
      q.loading = true
      q.error = ''
      try {
        q.data = await QUICK_CALLERS[key](id)
      } catch (e) {
        q.data = null
        q.error = e.httpStatus === 503 ? '依赖未就绪' : '体检失败'
      } finally {
        q.loading = false
      }
    }),
  )
}

const ANALYSIS_CALLERS = {
  cost: agentApi.costAnalysis,
  progress: agentApi.progressAnalysis,
  safety: agentApi.safetyAnalysis,
  risk: agentApi.riskAnalysis,
  weekly: agentApi.weeklyReport,
}

async function runAnalysis() {
  const id = requireProject()
  if (!id) return
  running.value = true
  result.value = null
  try {
    result.value = await ANALYSIS_CALLERS[agentType.value]({ project_id: id })
    loadWorkflows()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    running.value = false
  }
}

async function loadWorkflows() {
  logsLoading.value = true
  try {
    const id = (projectId.value || '').trim()
    workflows.value = await agentApi.workflows(id ? { project_id: id, limit: 20 } : { limit: 20 })
  } catch (e) {
    workflows.value = []
  } finally {
    logsLoading.value = false
  }
}

function riskColor(r) {
  return RISK[String(r || '').toLowerCase()]?.color || '#8b96a5'
}
function riskText(r) {
  return RISK[String(r || '').toLowerCase()]?.text || (r || '未知')
}
function riskStyle(r) {
  const c = riskColor(r)
  return { color: c, borderColor: `${c}59`, background: `${c}1a` }
}
function logStatusType(s) {
  const v = String(s || '').toLowerCase()
  if (v.includes('fail') || v.includes('error')) return 'danger'
  if (v.includes('running') || v.includes('pending')) return 'warning'
  return 'success'
}
function shortTime(t) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 16)
}
const pretty = (o) => JSON.stringify(o, null, 2)

onMounted(() => {
  loadProjectOptions()
  loadWorkflows()
})
</script>

<style scoped>
/* 整页暗色看板：覆盖共享组件与 Element Plus 的 CSS 变量（与 GraphView 同款基线） */
.agents-board {
  min-height: calc(100vh - var(--header-h) - var(--sp-8));
  margin: calc(-1 * var(--sp-4));
  padding: var(--sp-5);
  background: var(--d-bg);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);

  --c-surface: var(--d-surface);
  --c-border: var(--d-border);
  --c-text: var(--d-text);
  --c-text-2: var(--d-text-2);
  --c-text-3: var(--d-text-2);

  --el-bg-color: var(--d-surface);
  --el-bg-color-overlay: var(--d-surface);
  --el-fill-color-blank: var(--d-surface);
  --el-fill-color-light: #1b2433;
  --el-fill-color: #1b2433;
  --el-text-color-primary: var(--d-text);
  --el-text-color-regular: var(--d-text-2);
  --el-border-color: var(--d-border);
  --el-border-color-light: var(--d-border);
  --el-border-color-lighter: var(--d-border);
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: #131926;
  --el-table-header-text-color: var(--d-text-2);
  --el-table-text-color: var(--d-text-2);
  --el-table-border-color: var(--d-border);
  --el-table-row-hover-bg-color: #1b2433;
  --el-disabled-bg-color: #131926;
}
.board-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.board-head h2 {
  margin: 0;
  font-size: 20px;
  color: var(--d-text);
}
.board-head p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--d-text-2);
}
.head-tools {
  display: flex;
  gap: var(--sp-2);
}
.proj-select {
  width: 300px;
}
.ghost-btn {
  background: transparent;
  border-color: var(--d-border);
  color: var(--d-text-2);
}

/* 综合风险条 */
.overall-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-5);
  background: var(--d-surface);
  border: 1px solid var(--d-border);
  border-radius: var(--r-md);
}
.overall-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--d-text);
}
.overall-meta {
  font-size: 12px;
  color: var(--d-text-2);
}
.risk-pill {
  display: inline-block;
  padding: 3px 12px;
  border: 1px solid;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
}
.risk-pill.sm {
  padding: 1px 9px;
  font-size: 12px;
}

/* 三域指标卡 */
.tile-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-4);
}
.d-tile {
  position: relative;
  padding: var(--sp-4) var(--sp-5);
  background: var(--d-surface);
  border: 1px solid var(--d-border);
  border-radius: var(--r-md);
  overflow: hidden;
}
.tile-strip {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}
.tile-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.tile-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--d-text);
}
.tile-metrics {
  margin-top: var(--sp-3);
  font-size: 13px;
}
.tile-metrics div {
  display: flex;
  justify-content: space-between;
  padding: 3px 0;
  color: var(--d-text-2);
}
.tile-metrics b {
  color: var(--d-text);
}

/* 主区 */
.board-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 480px;
  gap: var(--sp-4);
  align-items: start;
}
.board-col {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}
.board-card {
  background: var(--d-surface);
  border: 1px solid var(--d-border);
  border-radius: var(--r-md);
  padding: var(--sp-4) var(--sp-5);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  flex-wrap: wrap;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--d-text);
}

/* 快速体检 */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--sp-3);
}
.quick-card {
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--d-border);
  border-radius: var(--r-sm);
  background: #131926;
  min-height: 96px;
}
.quick-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 600;
  color: var(--d-text);
}
.quick-metrics {
  margin-top: var(--sp-2);
  font-size: 12px;
}
.quick-metrics div {
  display: flex;
  justify-content: space-between;
  padding: 2px 0;
  color: var(--d-text-2);
}
.quick-metrics b {
  color: var(--d-text);
}
.quick-empty {
  margin-top: var(--sp-3);
  font-size: 12px;
  color: var(--d-text-2);
}

/* 深度分析 */
.analysis-tools {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.result-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
  font-size: 12px;
  color: var(--d-text-2);
}
.result-error {
  color: #f85149;
}
.result-body {
  margin: 0;
  background: #0a0e14;
  color: #c9d1d9;
  padding: var(--sp-4);
  border: 1px solid var(--d-border);
  border-radius: var(--r-sm);
  max-height: 480px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.6;
}
.result-body.report {
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 13px;
  color: var(--d-text);
}

.log-card {
  min-width: 0;
}

@media (max-width: 1400px) {
  .board-main {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 900px) {
  .tile-row,
  .quick-grid {
    grid-template-columns: 1fr;
  }
}
</style>
