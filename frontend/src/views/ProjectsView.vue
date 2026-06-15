<template>
  <AppPage title="项目管理" description="管理工程项目，作为智能分析的数据底座">
    <template #actions>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建项目</el-button>
    </template>

    <AppCard>
      <div class="toolbar">
        <el-select v-model="query.status" placeholder="状态筛选" clearable style="width: 140px" @change="reload">
          <el-option v-for="(v, k) in PROJECT_STATUS" :key="k" :label="v[0]" :value="k" />
        </el-select>
        <el-input v-model="keyword" placeholder="搜索名称 / 编号" clearable style="width: 220px">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>

      <!-- 503 降级 -->
      <EmptyState v-if="degraded" title="服务未就绪" description="项目数据库不可用，请检查后端依赖后重试">
        <el-button type="primary" @click="load">重试</el-button>
      </EmptyState>

      <template v-else>
        <el-table :data="filteredItems" v-loading="loading" @row-click="openDetail" row-key="project_id" class="proj-table">
          <template #empty>
            <EmptyState title="暂无项目" description="点击右上角「新建项目」创建第一个项目" />
          </template>
          <el-table-column prop="project_name" label="项目名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="project_id" label="编号" width="120" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusTag :status="statusSemantic(row.status)" :text="statusText(row.status)" />
            </template>
          </el-table-column>
          <el-table-column label="工期" width="210">
            <template #default="{ row }">{{ row.start_date || '-' }} ~ {{ row.planned_end_date || '-' }}</template>
          </el-table-column>
          <el-table-column label="预算" width="140" align="right">
            <template #default="{ row }">{{ fmtMoney(row.total_budget) }}</template>
          </el-table-column>
          <el-table-column label="进度" min-width="150">
            <template #default="{ row }">
              <el-progress :percentage="clampRate(row.progress_rate)" :stroke-width="8" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click.stop="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click.stop="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="pager"
          layout="total, prev, pager, next, sizes"
          :total="total"
          v-model:current-page="query.page"
          v-model:page-size="query.pageSize"
          :page-sizes="[10, 20, 50]"
          @current-change="load"
          @size-change="reload"
        />
      </template>
    </AppCard>

    <!-- 新建 / 编辑 -->
    <el-dialog v-model="dialog.visible" :title="dialog.editing ? '编辑项目' : '新建项目'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="项目编号" required>
          <el-input v-model="form.project_id" :disabled="dialog.editing" placeholder="如 P001" />
        </el-form-item>
        <el-form-item label="项目名称" required>
          <el-input v-model="form.project_name" placeholder="项目名称" />
        </el-form-item>
        <el-form-item label="项目类型">
          <el-input v-model="form.project_type" placeholder="如 住宅 / 市政 / 厂房" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="(v, k) in PROJECT_STATUS" :key="k" :label="v[0]" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="起止日期">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="计划结束"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="总预算">
          <el-input-number v-model="form.total_budget" :min="0" :step="10000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="项目经理">
          <el-input v-model="form.project_manager" placeholder="负责人姓名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detail.visible" :title="detail.project?.project_name || '项目详情'" size="720px" destroy-on-close>
      <el-tabs v-model="detail.tab" @tab-change="onTabChange">
        <!-- 概览 -->
        <el-tab-pane label="概览" name="overview">
          <SkeletonBlock v-if="detail.stats.loading" :rows="4" height="48px" />
          <EmptyState v-else-if="detail.stats.degraded" title="服务未就绪" description="统计服务暂不可用" />
          <EmptyState v-else-if="!detail.stats.data" title="暂无统计数据" />
          <div v-else class="tile-grid">
            <StatTile label="整体进度" :value="clampRate(detail.stats.data.overall_progress)" unit="%" status="info" />
            <StatTile label="任务完成" :value="`${detail.stats.data.completed_tasks}/${detail.stats.data.total_tasks}`" status="success" />
            <StatTile label="延期任务" :value="detail.stats.data.delayed_tasks" :status="detail.stats.data.delayed_tasks > 0 ? 'danger' : 'success'" />
            <StatTile label="平均 SPI" :value="fmtNum(detail.stats.data.average_spi)" :status="spiStatus(detail.stats.data.average_spi)" />
            <StatTile label="总预算" :value="fmtMoney(detail.stats.data.total_budget)" status="info" />
            <StatTile label="实际成本" :value="fmtMoney(detail.stats.data.total_actual_cost)" status="info" />
            <StatTile label="成本偏差率" :value="fmtNum(detail.stats.data.cost_variance_rate)" unit="%" :status="Math.abs(detail.stats.data.cost_variance_rate || 0) > 5 ? 'warning' : 'success'" />
            <StatTile label="未闭环缺陷" :value="detail.stats.data.open_defects" :status="detail.stats.data.open_defects > 0 ? 'warning' : 'success'" />
            <StatTile label="高级别缺陷" :value="detail.stats.data.high_level_defects" :status="detail.stats.data.high_level_defects > 0 ? 'danger' : 'success'" />
            <StatTile label="安全检查" :value="detail.stats.data.total_safety_checks" unit="次" status="info" />
          </div>
        </el-tab-pane>

        <!-- 任务 -->
        <el-tab-pane label="任务" name="tasks">
          <SkeletonBlock v-if="detail.tasks.loading" :rows="5" height="32px" />
          <EmptyState v-else-if="detail.tasks.degraded" title="服务未就绪" description="任务服务暂不可用" />
          <template v-else>
            <el-alert
              v-if="detail.tasks.delayedIds.length"
              type="warning"
              :title="`${detail.tasks.delayedIds.length} 个任务延期，已高亮标记`"
              :closable="false"
              class="mb12"
            />
            <el-table :data="detail.tasks.items" :row-class-name="taskRowClass" size="small">
              <template #empty><EmptyState title="暂无任务" /></template>
              <el-table-column label="任务" min-width="170" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ row.task_name }}
                  <el-tag v-if="row.is_critical_path" type="danger" size="small" effect="plain">关键路径</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <StatusTag :status="TASK_STATUS[row.status]?.[1] || 'info'" :text="TASK_STATUS[row.status]?.[0] || row.status" />
                </template>
              </el-table-column>
              <el-table-column label="计划" width="190">
                <template #default="{ row }">{{ row.planned_start || '-' }} ~ {{ row.planned_end || '-' }}</template>
              </el-table-column>
              <el-table-column label="进度(实/计)" width="110">
                <template #default="{ row }">{{ fmtNum(row.actual_progress) }}% / {{ fmtNum(row.planned_progress) }}%</template>
              </el-table-column>
              <el-table-column label="SPI" width="70">
                <template #default="{ row }">{{ fmtNum(row.spi) }}</template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <!-- 成本 -->
        <el-tab-pane label="成本" name="costs">
          <SkeletonBlock v-if="detail.costs.loading" :rows="5" height="32px" />
          <EmptyState v-else-if="detail.costs.degraded" title="服务未就绪" description="成本服务暂不可用" />
          <template v-else>
            <template v-if="costChartOption">
              <SectionTitle title="分类成本：计划 vs 实际" />
              <BaseChart :option="costChartOption" height="260px" />
            </template>
            <SectionTitle title="成本明细" :extra="`共 ${detail.costs.items.length} 条`" />
            <el-table :data="detail.costs.items" size="small">
              <template #empty><EmptyState title="暂无成本记录" /></template>
              <el-table-column label="类别" width="100">
                <template #default="{ row }">{{ COST_CATEGORY[row.cost_category] || row.cost_category }}</template>
              </el-table-column>
              <el-table-column prop="cost_item" label="成本项" min-width="140" show-overflow-tooltip />
              <el-table-column label="计划" width="120" align="right">
                <template #default="{ row }">{{ fmtMoney(row.planned_amount) }}</template>
              </el-table-column>
              <el-table-column label="实际" width="120" align="right">
                <template #default="{ row }">{{ fmtMoney(row.actual_amount) }}</template>
              </el-table-column>
              <el-table-column label="偏差率" width="90" align="right">
                <template #default="{ row }">
                  <span :class="{ over: (row.variance_rate || 0) > 0 }">{{ fmtNum(row.variance_rate) }}%</span>
                </template>
              </el-table-column>
              <el-table-column prop="cost_date" label="日期" width="110" />
            </el-table>
          </template>
        </el-tab-pane>

        <!-- 安全 -->
        <el-tab-pane label="安全" name="safety">
          <SkeletonBlock v-if="detail.safety.loading" :rows="5" height="32px" />
          <EmptyState v-else-if="detail.safety.degraded" title="服务未就绪" description="安全服务暂不可用" />
          <template v-else>
            <template v-if="detail.safety.openDefects.length">
              <SectionTitle title="未闭环安全问题" :extra="`${detail.safety.openDefects.length} 项`" />
              <div class="defect-list">
                <div v-for="d in detail.safety.openDefects" :key="d.record_id" class="defect-item">
                  <StatusTag :status="DEFECT_LEVEL[d.defect_level]?.[1] || 'info'" :text="DEFECT_LEVEL[d.defect_level]?.[0] || d.defect_level || '未分级'" />
                  <span class="defect-desc">{{ d.defect_description || d.defect_type || '未填写描述' }}</span>
                  <span class="defect-date">{{ d.check_date }}</span>
                </div>
              </div>
            </template>
            <template v-if="safetyStatRows.length">
              <SectionTitle title="缺陷统计（按类型 / 等级）" />
              <el-table :data="safetyStatRows" size="small" class="mb12">
                <el-table-column prop="type" label="缺陷类型" min-width="140" />
                <el-table-column prop="high" label="高" width="70" align="center" />
                <el-table-column prop="medium" label="中" width="70" align="center" />
                <el-table-column prop="low" label="低" width="70" align="center" />
                <el-table-column prop="total" label="合计" width="80" align="center" />
              </el-table>
            </template>
            <SectionTitle title="检查记录" :extra="`共 ${detail.safety.items.length} 条`" />
            <el-table :data="detail.safety.items" size="small">
              <template #empty><EmptyState title="暂无安全记录" /></template>
              <el-table-column prop="check_date" label="日期" width="110" />
              <el-table-column prop="check_type" label="检查类型" width="100" />
              <el-table-column prop="defect_type" label="缺陷类型" width="110" show-overflow-tooltip />
              <el-table-column label="等级" width="80">
                <template #default="{ row }">
                  <StatusTag v-if="row.defect_level" :status="DEFECT_LEVEL[row.defect_level]?.[1] || 'info'" :text="DEFECT_LEVEL[row.defect_level]?.[0] || row.defect_level" />
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <StatusTag :status="row.status === 'open' ? 'warning' : 'success'" :text="row.status === 'open' ? '未闭环' : '已闭环'" />
                </template>
              </el-table-column>
              <el-table-column prop="defect_description" label="描述" min-width="150" show-overflow-tooltip />
            </el-table>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </AppPage>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi } from '@/api'
import AppPage from '@/components/AppPage.vue'
import AppCard from '@/components/AppCard.vue'
import StatTile from '@/components/StatTile.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import SectionTitle from '@/components/SectionTitle.vue'
import BaseChart from '@/components/BaseChart.vue'

// ===== 字典 =====
const PROJECT_STATUS = {
  active: ['进行中', 'success'],
  planning: ['筹备中', 'info'],
  paused: ['已暂停', 'warning'],
  completed: ['已完成', 'primary'],
  archived: ['已归档', 'info'],
}
const TASK_STATUS = {
  not_started: ['未开始', 'info'],
  in_progress: ['进行中', 'primary'],
  completed: ['已完成', 'success'],
  delayed: ['延期', 'danger'],
}
const COST_CATEGORY = {
  material: '材料费',
  labor: '人工费',
  equipment: '机械费',
  subcontract: '分包费',
  management: '管理费',
  other: '其他',
}
const DEFECT_LEVEL = {
  high: ['高', 'danger'],
  medium: ['中', 'warning'],
  low: ['低', 'success'],
}

const statusText = (s) => PROJECT_STATUS[s]?.[0] || s || '-'
const statusSemantic = (s) => PROJECT_STATUS[s]?.[1] || 'info'

// ===== 列表 =====
const items = ref([])
const total = ref(0)
const loading = ref(false)
const degraded = ref(false)
const keyword = ref('')
const query = reactive({ page: 1, pageSize: 10, status: '' })

async function load() {
  loading.value = true
  degraded.value = false
  try {
    // 后端 Page 契约：skip/limit 入参，{items,total,page,page_size} 出参
    const res = await projectApi.list({
      skip: (query.page - 1) * query.pageSize,
      limit: query.pageSize,
      status: query.status || undefined,
    })
    items.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
    items.value = []
    total.value = 0
    if (e.httpStatus === 503) degraded.value = true
  } finally {
    loading.value = false
  }
}

function reload() {
  query.page = 1
  load()
}

// 关键词为前端过滤（后端列表无搜索参数）
const filteredItems = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return items.value
  return items.value.filter(
    (p) =>
      (p.project_name || '').toLowerCase().includes(kw) ||
      (p.project_id || '').toLowerCase().includes(kw),
  )
})

// ===== 新建 / 编辑 =====
const dialog = reactive({ visible: false, editing: false })
const saving = ref(false)
const dateRange = ref([])
const form = reactive({
  project_id: '',
  project_name: '',
  project_type: '',
  status: 'active',
  total_budget: null,
  project_manager: '',
})

function resetForm(row) {
  form.project_id = row?.project_id || ''
  form.project_name = row?.project_name || ''
  form.project_type = row?.project_type || ''
  form.status = row?.status || 'active'
  form.total_budget = row?.total_budget != null ? Number(row.total_budget) : null
  form.project_manager = row?.project_manager || ''
  dateRange.value = row?.start_date && row?.planned_end_date ? [row.start_date, row.planned_end_date] : []
}

function openCreate() {
  dialog.editing = false
  resetForm(null)
  dialog.visible = true
}

function openEdit(row) {
  dialog.editing = true
  resetForm(row)
  dialog.visible = true
}

async function save() {
  if (!form.project_id.trim()) return ElMessage.warning('请输入项目编号')
  if (!form.project_name.trim()) return ElMessage.warning('请输入项目名称')
  const payload = {
    project_name: form.project_name,
    project_type: form.project_type || null,
    status: form.status,
    start_date: dateRange.value?.[0] || null,
    planned_end_date: dateRange.value?.[1] || null,
    total_budget: form.total_budget,
    project_manager: form.project_manager || null,
  }
  saving.value = true
  try {
    if (dialog.editing) {
      await projectApi.update(form.project_id, payload)
      ElMessage.success('已更新')
    } else {
      await projectApi.create({ ...payload, project_id: form.project_id })
      ElMessage.success('创建成功')
    }
    dialog.visible = false
    load()
  } catch {
    // 拦截器已统一提示
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除项目「${row.project_name}」？关联任务/成本/安全数据将一并失效。`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  await projectApi.remove(row.project_id)
  ElMessage.success('已删除')
  load()
}

// ===== 详情抽屉 =====
const detail = reactive({
  visible: false,
  project: null,
  tab: 'overview',
  stats: { loading: false, degraded: false, data: null },
  tasks: { loading: false, degraded: false, loaded: false, items: [], delayedIds: [] },
  costs: { loading: false, degraded: false, loaded: false, items: [], summary: {} },
  safety: { loading: false, degraded: false, loaded: false, items: [], openDefects: [], stats: {} },
})

function openDetail(row) {
  detail.project = row
  detail.tab = 'overview'
  detail.stats = { loading: false, degraded: false, data: null }
  detail.tasks = { loading: false, degraded: false, loaded: false, items: [], delayedIds: [] }
  detail.costs = { loading: false, degraded: false, loaded: false, items: [], summary: {} }
  detail.safety = { loading: false, degraded: false, loaded: false, items: [], openDefects: [], stats: {} }
  detail.visible = true
  loadStats()
}

function onTabChange(name) {
  if (name === 'tasks' && !detail.tasks.loaded) loadTasks()
  if (name === 'costs' && !detail.costs.loaded) loadCosts()
  if (name === 'safety' && !detail.safety.loaded) loadSafety()
}

const pid = () => detail.project?.project_id

async function loadStats() {
  const s = detail.stats
  s.loading = true
  try {
    s.data = await projectApi.statistics(pid())
  } catch (e) {
    if (e.httpStatus === 503) s.degraded = true
  } finally {
    s.loading = false
  }
}

async function loadTasks() {
  const s = detail.tasks
  s.loading = true
  try {
    // 延期清单各自 catch：主列表可用时不因延期接口失败而空白
    const tasks = await projectApi.tasks(pid())
    s.items = tasks || []
    try {
      const delayed = await projectApi.delayedTasks(pid())
      s.delayedIds = (delayed || []).map((t) => t.task_id)
    } catch {
      s.delayedIds = []
    }
    s.loaded = true
  } catch (e) {
    if (e.httpStatus === 503) s.degraded = true
  } finally {
    s.loading = false
  }
}

async function loadCosts() {
  const s = detail.costs
  s.loading = true
  try {
    const [list, summary] = await Promise.all([
      projectApi.costs(pid()),
      projectApi.costSummary(pid()).catch(() => ({})),
    ])
    s.items = list || []
    s.summary = summary || {}
    s.loaded = true
  } catch (e) {
    if (e.httpStatus === 503) s.degraded = true
  } finally {
    s.loading = false
  }
}

async function loadSafety() {
  const s = detail.safety
  s.loading = true
  try {
    const [list, open, stats] = await Promise.all([
      projectApi.safety(pid()),
      projectApi.openDefects(pid()).catch(() => []),
      projectApi.safetyStatistics(pid()).catch(() => ({})),
    ])
    s.items = list || []
    s.openDefects = open || []
    s.stats = stats || {}
    s.loaded = true
  } catch (e) {
    if (e.httpStatus === 503) s.degraded = true
  } finally {
    s.loading = false
  }
}

// 延期任务高亮
function taskRowClass({ row }) {
  return detail.tasks.delayedIds.includes(row.task_id) ? 'row-delayed' : ''
}

// 成本柱图：各分类计划 vs 实际（无数据不渲染）
const costChartOption = computed(() => {
  const summary = detail.costs.summary || {}
  const cats = Object.keys(summary)
  if (!cats.length) return null
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['计划', '实际'] },
    xAxis: { type: 'category', data: cats.map((c) => COST_CATEGORY[c] || c) },
    yAxis: { type: 'value' },
    series: [
      { name: '计划', type: 'bar', barMaxWidth: 32, data: cats.map((c) => summary[c]?.planned ?? 0) },
      { name: '实际', type: 'bar', barMaxWidth: 32, data: cats.map((c) => summary[c]?.actual ?? 0) },
    ],
  }
})

// 缺陷统计 {type:{level:count}} → 行
const safetyStatRows = computed(() =>
  Object.entries(detail.safety.stats || {}).map(([type, levels]) => ({
    type,
    high: levels?.high || 0,
    medium: levels?.medium || 0,
    low: levels?.low || 0,
    total: Object.values(levels || {}).reduce((a, b) => a + (b || 0), 0),
  })),
)

// ===== 格式化 =====
const clampRate = (v) => Math.min(100, Math.max(0, Math.round(Number(v) || 0)))
const fmtMoney = (v) => (v == null ? '-' : `¥${Number(v).toLocaleString()}`)
const fmtNum = (v) => (v == null ? '-' : Number(v).toFixed(2).replace(/\.?0+$/, '') || '0')
const spiStatus = (v) => (v == null ? 'info' : v < 0.85 ? 'danger' : v < 0.95 ? 'warning' : 'success')

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.proj-table :deep(.el-table__row) {
  cursor: pointer;
}
.pager {
  margin-top: var(--sp-4);
  justify-content: flex-end;
}
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: var(--sp-3);
}
.mb12 {
  margin-bottom: 12px;
}
.over {
  color: var(--c-danger);
}
:deep(.row-delayed) {
  background: rgba(207, 34, 46, 0.06);
}
.defect-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin-bottom: var(--sp-4);
}
.defect-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--c-border);
  border-left: 3px solid var(--c-warning);
  border-radius: var(--r-sm);
  background: var(--c-surface-2);
}
.defect-desc {
  flex: 1;
  font-size: 13px;
  color: var(--c-text);
}
.defect-date {
  font-size: 12px;
  color: var(--c-text-3);
}
</style>
