<template>
  <AppPage>
    <!-- 欢迎区 + 快捷操作 -->
    <div class="welcome">
      <div class="welcome-text">
        <div class="welcome-title-row">
          <h2 class="welcome-title">{{ greeting }}，工程账户</h2>
          <StatusTag status="primary" :text="`角色 · ${role}`" />
        </div>
        <p class="welcome-date">{{ today }} · 筑见 BuildView 工作台</p>
      </div>
      <div class="welcome-actions">
        <el-button type="primary" :icon="ChatDotRound" @click="go('/qa')">去提问</el-button>
        <el-button :icon="UploadFilled" @click="go('/documents')">上传文档</el-button>
        <el-button :icon="Picture" @click="go('/drawings')">上传图纸</el-button>
      </div>
    </div>

    <!-- 指标行：各自独立加载，失败显示 — 不连坐 -->
    <el-row :gutter="16">
      <el-col v-for="t in tiles" :key="t.label" :xs="12" :md="6" class="tile-col">
        <StatTile
          :label="t.label"
          :value="t.value"
          :unit="t.unit"
          :trend="t.note"
          :status="t.status"
          :icon="t.icon"
        />
      </el-col>
    </el-row>

    <!-- 项目核：全部/项目/造价/安全 -->
    <el-row v-if="showProject" :gutter="16">
      <el-col :xs="24" :md="14" class="tile-col">
        <AppCard title="项目概览" status="primary">
          <template #extra>
            <el-button text type="primary" size="small" @click="go('/projects')">全部项目</el-button>
          </template>
          <SkeletonBlock v-if="projectsLoading" :rows="5" height="18px" />
          <EmptyState
            v-else-if="projectsError"
            :title="projectsError.unready ? '服务未就绪' : '加载失败'"
            :description="projectsError.message"
          />
          <EmptyState v-else-if="!projects.length" title="暂无项目" description="创建项目后可在此查看概览">
            <el-button size="small" type="primary" @click="go('/projects')">去创建</el-button>
          </EmptyState>
          <ul v-else class="row-list">
            <li v-for="p in projects" :key="p.project_id" class="row-item" @click="go('/projects')">
              <span class="row-main">{{ p.project_name }}</span>
              <span class="row-sub">{{ p.project_id }}</span>
              <span class="row-sub">进度 {{ pct(p.progress_rate) }}</span>
              <StatusTag :status="projectTag(p.status).status" :text="projectTag(p.status).text" />
            </li>
          </ul>
        </AppCard>
      </el-col>

      <el-col :xs="24" :md="10" class="tile-col">
        <AppCard title="快捷分析 · 风险扫描" status="warning">
          <div class="inline-form">
            <el-input
              v-model="riskProjectId"
              placeholder="输入项目 ID，如 P001"
              clearable
              @keyup.enter="runQuickRisk"
            />
            <el-button type="primary" :loading="riskLoading" @click="runQuickRisk">扫描</el-button>
          </div>
          <SkeletonBlock v-if="riskLoading" :rows="3" />
          <EmptyState
            v-else-if="riskError"
            :title="riskError.unready ? '服务未就绪' : '扫描失败'"
            :description="riskError.message"
          />
          <div v-else-if="riskResult" class="risk-result">
            <div class="risk-head">
              <span>最高风险：{{ catText(riskResult.highest_risk_category) }}</span>
              <StatusTag :status="riskResult.highest_risk_level" />
            </div>
            <div class="risk-levels">
              <span v-for="(lv, cat) in riskResult.risk_levels" :key="cat" class="risk-level-item">
                {{ catText(cat) }}
                <StatusTag :status="lv" effect="plain" />
              </span>
            </div>
            <ul v-if="riskResult.alerts?.length" class="risk-alerts">
              <li v-for="(a, i) in riskResult.alerts" :key="i">{{ a }}</li>
            </ul>
          </div>
          <EmptyState
            v-else
            title="输入项目 ID 一键扫描"
            description="快速获取进度 / 成本 / 安全风险概况"
            :icon="Aim"
          />
        </AppCard>
      </el-col>
    </el-row>

    <!-- 知识核：全部/技术 -->
    <el-row v-if="showKnowledge" :gutter="16">
      <el-col :xs="24" :md="10" class="tile-col">
        <AppCard title="快捷问答" status="primary">
          <p class="card-hint">面向规范 / 合同 / 项目文档的知识问答</p>
          <div class="inline-form">
            <el-input
              v-model="qaQuery"
              placeholder="例如：高支模专项方案的验收要求？"
              clearable
              @keyup.enter="goAsk"
            />
            <el-button type="primary" :icon="ChatDotRound" @click="goAsk">提问</el-button>
          </div>
        </AppCard>
      </el-col>

      <el-col :xs="24" :md="14" class="tile-col">
        <AppCard title="最近文档" status="info">
          <template #extra>
            <el-button text type="primary" size="small" @click="go('/documents')">全部文档</el-button>
          </template>
          <SkeletonBlock v-if="docsLoading" :rows="5" height="18px" />
          <EmptyState
            v-else-if="docsError"
            :title="docsError.unready ? '服务未就绪' : '加载失败'"
            :description="docsError.message"
          />
          <EmptyState v-else-if="!docs.length" title="暂无文档" description="上传文档后可在此查看最近记录">
            <el-button size="small" type="primary" @click="go('/documents')">去上传</el-button>
          </EmptyState>
          <ul v-else class="row-list">
            <li v-for="d in docs" :key="d.doc_id" class="row-item" @click="go('/documents')">
              <span class="row-main">{{ d.filename }}</span>
              <span class="row-sub">{{ fmtDate(d.uploaded_at) }}</span>
              <StatusTag :status="docTag(d.status).status" :text="docTag(d.status).text" />
            </li>
          </ul>
        </AppCard>
      </el-col>
    </el-row>
  </AppPage>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  ChatDotRound,
  UploadFilled,
  Picture,
  Document,
  Monitor,
  Share,
  Aim,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { adminApi, graphApi, projectApi, documentApi, agentApi } from '@/api'
import AppPage from '@/components/AppPage.vue'
import AppCard from '@/components/AppCard.vue'
import StatTile from '@/components/StatTile.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'

const router = useRouter()
const { role } = storeToRefs(useUserStore())

// 角色 → 卡片组合
const showProject = computed(() => ['全部', '项目', '造价', '安全'].includes(role.value))
const showKnowledge = computed(() => ['全部', '技术'].includes(role.value))

// 问候 + 日期
const hour = new Date().getHours()
const greeting =
  hour < 6 ? '凌晨好' : hour < 9 ? '早上好' : hour < 12 ? '上午好' : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好'
const today = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

function go(path) {
  router.push(path)
}

// 错误归一：503 = 服务未就绪（降级）
function errInfo(e) {
  return {
    unready: e?.httpStatus === 503,
    message: e?.apiError?.message || e?.message || '请求失败',
  }
}

// ===== 指标行（各自独立 try/catch，不连坐） =====
const tiles = reactive([
  { label: '文档总数', value: '—', unit: '', status: 'info', icon: Document, note: '' },
  { label: '查询次数', value: '—', unit: '', status: 'info', icon: ChatDotRound, note: '' },
  { label: '服务健康', value: '—', unit: '在线', status: 'info', icon: Monitor, note: '' },
  { label: '图谱节点', value: '—', unit: '', status: 'info', icon: Share, note: '' },
])

async function loadDocTile() {
  const t = tiles[0]
  try {
    const s = await adminApi.indexStats()
    if (s.degraded) {
      t.note = s.reason || '未就绪'
      return
    }
    t.value = s.total_documents ?? 0
    t.status = 'success'
  } catch (e) {
    t.note = errInfo(e).unready ? '服务未就绪' : '加载失败'
  }
}

async function loadQueryTile() {
  const t = tiles[1]
  try {
    const s = await adminApi.statistics({ days: 7 })
    if (s.degraded) {
      t.note = s.reason || '未就绪'
      return
    }
    t.value = s.total_queries ?? 0
    t.status = 'success'
  } catch (e) {
    t.note = errInfo(e).unready ? '服务未就绪' : '加载失败'
  }
}

async function loadHealthTile() {
  const t = tiles[2]
  try {
    const h = await adminApi.health()
    const comps = Object.values(h.components || {})
    const online = comps.filter((c) => c?.ok).length
    t.value = `${online}/${comps.length || 4}`
    t.status = online === comps.length ? 'success' : online > 0 ? 'warning' : 'danger'
    t.note = h.status === 'healthy' ? '' : '部分组件离线'
  } catch (e) {
    t.note = errInfo(e).unready ? '服务未就绪' : '加载失败'
  }
}

async function loadGraphTile() {
  const t = tiles[3]
  try {
    const s = await graphApi.statistics()
    t.value = s.total_nodes ?? 0
    t.status = 'success'
  } catch (e) {
    t.note = errInfo(e).unready ? '服务未就绪' : '加载失败'
  }
}

// ===== 项目概览 =====
const projects = ref([])
const projectsLoading = ref(true)
const projectsError = ref(null)

const PROJECT_TAG = {
  active: { status: 'success', text: '进行中' },
  completed: { status: 'info', text: '已完成' },
  paused: { status: 'warning', text: '已暂停' },
  suspended: { status: 'warning', text: '已暂停' },
}
const projectTag = (s) => PROJECT_TAG[s] || { status: 'info', text: s || '未知' }
const pct = (v) => (v == null ? '—' : `${Number(v).toFixed(0)}%`)

async function loadProjects() {
  projectsLoading.value = true
  projectsError.value = null
  try {
    const res = await projectApi.list({ skip: 0, limit: 5 })
    projects.value = res.items || []
  } catch (e) {
    projectsError.value = errInfo(e)
  } finally {
    projectsLoading.value = false
  }
}

// ===== 快捷分析（一键风险扫描） =====
const riskProjectId = ref('')
const riskLoading = ref(false)
const riskResult = ref(null)
const riskError = ref(null)

const CAT_TEXT = { progress: '进度', cost: '成本', safety: '安全' }
const catText = (c) => CAT_TEXT[c] || c

async function runQuickRisk() {
  const id = riskProjectId.value.trim()
  if (!id || riskLoading.value) return
  riskLoading.value = true
  riskResult.value = null
  riskError.value = null
  try {
    riskResult.value = await agentApi.quickRisk(id)
  } catch (e) {
    riskError.value = errInfo(e)
  } finally {
    riskLoading.value = false
  }
}

// ===== 快捷问答 =====
const qaQuery = ref('')
function goAsk() {
  const q = qaQuery.value.trim()
  router.push(q ? { path: '/qa', query: { q } } : '/qa')
}

// ===== 最近文档 =====
const docs = ref([])
const docsLoading = ref(true)
const docsError = ref(null)

const DOC_TAG = {
  completed: { status: 'success', text: '已完成' },
  processing: { status: 'warning', text: '处理中' },
  pending: { status: 'info', text: '待处理' },
  failed: { status: 'danger', text: '失败' },
}
const docTag = (s) => DOC_TAG[s] || { status: 'info', text: s || '未知' }
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('zh-CN') : '—')

async function loadDocs() {
  docsLoading.value = true
  docsError.value = null
  try {
    const res = await documentApi.list({ page: 1, page_size: 5 })
    docs.value = res.items || []
  } catch (e) {
    docsError.value = errInfo(e)
  } finally {
    docsLoading.value = false
  }
}

onMounted(() => {
  loadDocTile()
  loadQueryTile()
  loadHealthTile()
  loadGraphTile()
  loadProjects()
  loadDocs()
})
</script>

<style scoped>
/* 欢迎区 */
.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-4);
  flex-wrap: wrap;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  padding: var(--sp-5);
}
.welcome-title-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}
.welcome-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--c-text);
}
.welcome-date {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--c-text-2);
}
.welcome-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* 栅格列在窄屏换行时保留间距 */
.tile-col {
  margin-bottom: var(--sp-4);
}
.el-row {
  margin-bottom: calc(var(--sp-4) * -1);
}

/* 列表行 */
.row-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.row-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 10px 4px;
  border-bottom: 1px solid var(--c-border);
  cursor: pointer;
}
.row-item:last-child {
  border-bottom: none;
}
.row-item:hover {
  background: var(--c-surface-2);
}
.row-main {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-sub {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--c-text-3);
}

/* 内联表单 */
.inline-form {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-4);
}
.card-hint {
  margin: 0 0 var(--sp-3);
  font-size: 13px;
  color: var(--c-text-2);
}

/* 风险扫描结果 */
.risk-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: 14px;
  font-weight: 600;
  color: var(--c-text);
}
.risk-levels {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
}
.risk-level-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--c-text-2);
}
.risk-alerts {
  margin: var(--sp-3) 0 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--c-danger);
}
.risk-alerts li {
  padding: 2px 0;
}
</style>
