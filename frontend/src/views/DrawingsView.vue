<template>
  <AppPage title="施工图处理" description="上传施工图 PDF，自动解析构件、材料、规范并同步知识图谱">
    <template #actions>
      <el-button :loading="loading" @click="load">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </template>

    <!-- 503 降级：服务未就绪 -->
    <AppCard v-if="serviceDown">
      <EmptyState title="服务未就绪" description="施工图服务暂不可用，请稍后重试">
        <el-button type="primary" @click="load">重试</el-button>
      </EmptyState>
    </AppCard>

    <template v-else>
      <!-- 解析依赖缺失警示条 -->
      <el-alert
        v-if="hasDegraded"
        type="warning"
        :closable="false"
        show-icon
        title="OCR/解析依赖未安装，已降级"
        description="部分图纸标记为「依赖未就绪」：PDF/OCR 解析依赖缺失，安装后可点击「重新处理」恢复。"
      />

      <AppCard title="上传施工图">
        <div class="upload-row">
          <el-upload
            class="uploader"
            drag
            accept=".pdf"
            :show-file-list="false"
            :disabled="uploading"
            :before-upload="beforeUpload"
            :http-request="handleUpload"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽 PDF 到此处，或 <em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">仅支持 PDF 格式，单文件不超过 100MB</div>
            </template>
          </el-upload>
          <div class="upload-opts">
            <el-select v-model="uploadOpts.drawing_type" style="width: 150px">
              <el-option label="结构图" value="structural" />
              <el-option label="建筑图" value="architectural" />
              <el-option label="机电图" value="mep" />
              <el-option label="其他" value="other" />
            </el-select>
            <el-checkbox v-model="uploadOpts.enable_ocr">启用 OCR</el-checkbox>
            <el-checkbox v-model="uploadOpts.sync_to_neo4j">同步知识图谱</el-checkbox>
          </div>
        </div>
      </AppCard>

      <AppCard title="处理列表">
        <template #extra>
          <el-select
            v-model="filters.status"
            placeholder="状态筛选"
            clearable
            style="width: 150px"
            @change="onFilter"
          >
            <el-option v-for="(m, key) in STATUS_META" :key="key" :label="m.text" :value="key" />
          </el-select>
        </template>

        <el-table :data="rows" v-loading="loading">
          <template #empty>
            <EmptyState title="暂无施工图" description="上传 PDF 图纸后自动开始解析" />
          </template>
          <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
          <el-table-column label="状态" width="170">
            <template #default="{ row }">
              <StatusTag :status="statusMeta(row.status).tag" :text="statusMeta(row.status).text" />
              <el-progress
                v-if="isRunning(row.status)"
                class="row-progress"
                :percentage="Math.round(row.progress || 0)"
                :stroke-width="4"
              />
            </template>
          </el-table-column>
          <el-table-column label="页数" width="80" align="center">
            <template #default="{ row }">{{ pagesOf(row) }}</template>
          </el-table-column>
          <el-table-column label="实体数" width="90" align="center">
            <template #default="{ row }">{{ entitiesOf(row) }}</template>
          </el-table-column>
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                :disabled="!['completed', 'degraded'].includes(row.status)"
                @click="viewEntities(row)"
              >查看实体</el-button>
              <el-button
                link
                type="primary"
                :disabled="row.status !== 'completed'"
                @click="viewResult(row)"
              >处理结果</el-button>
              <el-button link :disabled="isRunning(row.status)" @click="reprocess(row)">重新处理</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="pager"
          layout="total, prev, pager, next"
          :total="total"
          :page-size="filters.page_size"
          :current-page="filters.page"
          @current-change="onPage"
        />
      </AppCard>
    </template>

    <!-- 实体抽屉 -->
    <el-drawer v-model="entityVisible" title="提取实体" size="52%">
      <el-alert
        v-if="entityData?.degraded"
        type="warning"
        :closable="false"
        show-icon
        class="drawer-alert"
        title="知识图谱不可用，实体结果已降级为空"
      />
      <el-descriptions v-if="entityData?.summary" :column="4" border size="small" class="drawer-summary">
        <el-descriptions-item label="构件">{{ entityData.summary.components }}</el-descriptions-item>
        <el-descriptions-item label="材料">{{ entityData.summary.materials }}</el-descriptions-item>
        <el-descriptions-item label="规范">{{ entityData.summary.specifications }}</el-descriptions-item>
        <el-descriptions-item label="尺寸">{{ entityData.summary.dimensions }}</el-descriptions-item>
      </el-descriptions>
      <el-tabs v-model="entityTab">
        <el-tab-pane
          v-for="tab in ENTITY_TABS"
          :key="tab.key"
          :name="tab.key"
          :label="`${tab.label} (${(entityData?.entities?.[tab.key] || []).length})`"
        >
          <el-table :data="entityData?.entities?.[tab.key] || []" size="small" max-height="480">
            <template #empty>
              <EmptyState :title="`暂无${tab.label}实体`" />
            </template>
            <el-table-column
              v-for="col in tab.cols"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              width="120"
              show-overflow-tooltip
            />
            <el-table-column label="属性">
              <template #default="{ row }">{{ propText(row, tab.cols) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

    <!-- 处理结果对话框 -->
    <el-dialog v-model="resultVisible" title="处理结果" width="640px">
      <template v-if="resultData">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="文件名" :span="2">{{ resultData.filename }}</el-descriptions-item>
          <el-descriptions-item label="是否成功">
            <StatusTag :status="resultData.success ? 'success' : 'danger'" :text="resultData.success ? '成功' : '失败'" />
          </el-descriptions-item>
          <el-descriptions-item label="耗时">{{ (resultData.processing_time_ms / 1000).toFixed(1) }}s</el-descriptions-item>
          <el-descriptions-item label="实体数">{{ resultData.entities_count }}</el-descriptions-item>
          <el-descriptions-item label="关系数">{{ resultData.relations_count }}</el-descriptions-item>
          <el-descriptions-item label="图谱同步">{{ resultData.neo4j_synced ? '已同步' : '未同步' }}</el-descriptions-item>
          <el-descriptions-item label="页数">{{ resultData.drawing_info?.total_pages ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="图纸编号">{{ resultData.drawing_info?.drawing_number || '-' }}</el-descriptions-item>
          <el-descriptions-item label="图纸名称">{{ resultData.drawing_info?.drawing_name || '-' }}</el-descriptions-item>
        </el-descriptions>
        <SectionTitle title="处理步骤" class="steps-title" />
        <el-table :data="resultData.steps || []" size="small">
          <el-table-column prop="step" label="步骤" width="140" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusTag :status="row.status === 'success' ? 'success' : 'danger'" :text="row.status === 'success' ? '成功' : '失败'" />
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="90">
            <template #default="{ row }">{{ row.duration_ms != null ? `${row.duration_ms}ms` : '-' }}</template>
          </el-table-column>
          <el-table-column label="详情">
            <template #default="{ row }">{{ stepDetail(row) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-dialog>
  </AppPage>
</template>

<script setup>
import { reactive, ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { drawingApi } from '@/api'
import AppPage from '@/components/AppPage.vue'
import AppCard from '@/components/AppCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import SectionTitle from '@/components/SectionTitle.vue'

// 状态语义：degraded = 解析依赖未就绪
const STATUS_META = {
  pending: { tag: 'info', text: '待处理' },
  parsing: { tag: 'primary', text: '解析中' },
  extracting: { tag: 'primary', text: '提取中' },
  syncing: { tag: 'primary', text: '同步中' },
  completed: { tag: 'success', text: '已完成' },
  failed: { tag: 'danger', text: '失败' },
  degraded: { tag: 'warning', text: '依赖未就绪' },
}
const RUNNING = ['pending', 'parsing', 'extracting', 'syncing']

const ENTITY_TABS = [
  { key: 'components', label: '构件', cols: [{ prop: 'code', label: '编号' }, { prop: 'type', label: '类型' }] },
  { key: 'materials', label: '材料', cols: [{ prop: 'grade', label: '等级' }, { prop: 'type', label: '类型' }] },
  { key: 'specifications', label: '规范', cols: [{ prop: 'code', label: '编号' }, { prop: 'name', label: '名称' }] },
  { key: 'dimensions', label: '尺寸', cols: [{ prop: 'value', label: '数值' }, { prop: 'type', label: '类型' }] },
]

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const uploading = ref(false)
const serviceDown = ref(false)
const filters = reactive({ page: 1, page_size: 10, status: '' })
const uploadOpts = reactive({ drawing_type: 'structural', enable_ocr: true, sync_to_neo4j: true })

// 完成结果缓存（填充页数/实体数列）
const resultCache = reactive({})

const entityVisible = ref(false)
const entityTab = ref('components')
const entityData = ref(null)

const resultVisible = ref(false)
const resultData = ref(null)

const hasDegraded = computed(() => rows.value.some((r) => r.status === 'degraded'))

const statusMeta = (s) => STATUS_META[s] || { tag: 'info', text: s || '-' }
const isRunning = (s) => RUNNING.includes(s)

// ===== 列表 =====

async function load() {
  loading.value = true
  try {
    const res = await drawingApi.list({
      page: filters.page,
      page_size: filters.page_size,
      status: filters.status || undefined,
    })
    rows.value = res.items || []
    total.value = res.total || 0
    serviceDown.value = false
    rows.value.filter((r) => r.status === 'completed').forEach((r) => fetchResult(r.document_id))
    ensurePolling()
  } catch (e) {
    if (e.httpStatus === 503) serviceDown.value = true
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onPage(p) {
  filters.page = p
  load()
}

function onFilter() {
  filters.page = 1
  load()
}

async function fetchResult(docId) {
  if (resultCache[docId] !== undefined) return
  resultCache[docId] = null
  try {
    resultCache[docId] = await drawingApi.result(docId)
  } catch (e) {
    /* 结果缺失时保持空 */
  }
}

const pagesOf = (row) => resultCache[row.document_id]?.drawing_info?.total_pages ?? '-'
const entitiesOf = (row) => resultCache[row.document_id]?.entities_count ?? '-'

// ===== 轮询处理中状态（卸载时清理） =====

let pollTimer = null
let polling = false

function ensurePolling() {
  if (!pollTimer && rows.value.some((r) => isRunning(r.status))) {
    pollTimer = setInterval(poll, 3000)
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function poll() {
  if (polling) return
  polling = true
  try {
    const running = rows.value.filter((r) => isRunning(r.status))
    if (!running.length) {
      stopPolling()
      return
    }
    for (const row of running) {
      const s = await drawingApi.status(row.document_id)
      row.status = s.status
      row.progress = s.progress
      row.completed_at = s.completed_at
      if (s.status === 'completed') fetchResult(row.document_id)
    }
  } catch (e) {
    stopPolling() // 轮询异常即停，避免重复报错
  } finally {
    polling = false
  }
}

// ===== 上传 =====

function beforeUpload(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.error('仅支持 PDF 格式')
    return false
  }
  if (file.size > 100 * 1024 * 1024) {
    ElMessage.error('文件过大，限制 100MB')
    return false
  }
  return true
}

async function handleUpload({ file }) {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    await drawingApi.upload(fd, { ...uploadOpts })
    ElMessage.success('上传成功，正在后台解析')
    filters.page = 1
    await load()
  } finally {
    uploading.value = false
  }
}

// ===== 行操作 =====

async function viewEntities(row) {
  const res = await drawingApi.entities(row.document_id)
  entityData.value = res
  entityTab.value = 'components'
  entityVisible.value = true
}

async function viewResult(row) {
  resultData.value = resultCache[row.document_id] || (await drawingApi.result(row.document_id))
  resultVisible.value = true
}

async function reprocess(row) {
  await ElMessageBox.confirm(`将清除「${row.filename}」旧结果并重新解析，确认？`, '重新处理', { type: 'warning' })
  await drawingApi.reprocess(row.document_id)
  ElMessage.success('已开始重新处理')
  delete resultCache[row.document_id]
  row.status = 'pending'
  row.progress = 0
  ensurePolling()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除「${row.filename}」及其图谱数据？`, '删除', { type: 'warning' })
  await drawingApi.remove(row.document_id)
  ElMessage.success('已删除')
  load()
}

// ===== 工具 =====

function fmtTime(s) {
  if (!s) return '-'
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleString('zh-CN', { hour12: false })
}

function propText(row, cols) {
  const skip = new Set(['id', 'doc_id', ...cols.map((c) => c.prop)])
  const parts = Object.entries(row || {})
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== '' && typeof v !== 'object')
    .map(([k, v]) => `${k}: ${v}`)
  return parts.length ? parts.join('；') : '-'
}

function stepDetail(step) {
  const skip = new Set(['step', 'status', 'duration_ms'])
  const parts = Object.entries(step || {})
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== '')
    .map(([k, v]) => `${k}: ${v}`)
  return parts.length ? parts.join('；') : '-'
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.upload-row {
  display: flex;
  gap: var(--sp-5);
  align-items: flex-start;
  flex-wrap: wrap;
}
.uploader {
  flex: 1;
  min-width: 320px;
}
.uploader :deep(.el-upload-dragger) {
  padding: var(--sp-6);
}
.upload-icon {
  font-size: 40px;
  color: var(--c-text-3);
}
.upload-opts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding-top: var(--sp-2);
}
.row-progress {
  margin-top: 4px;
  width: 130px;
}
.pager {
  margin-top: var(--sp-4);
  justify-content: flex-end;
}
.drawer-alert,
.drawer-summary {
  margin-bottom: var(--sp-4);
}
.steps-title {
  margin-top: var(--sp-4);
}
</style>
