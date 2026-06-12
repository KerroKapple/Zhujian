<template>
  <AppPage title="文档管理" description="上传、检索与管理知识库文档">
    <template #actions>
      <el-button type="primary" :icon="Upload" @click="uploadVisible = true">上传文档</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </template>

    <AppCard title="文档列表">
      <SkeletonBlock v-if="!firstLoaded" :rows="6" height="18px" />

      <!-- 503/失败降级态：明确原因，绝不空白 -->
      <EmptyState v-else-if="errorState" :title="errorState.title" :description="errorState.desc">
        <el-button size="small" type="primary" plain @click="load">重试</el-button>
      </EmptyState>

      <template v-else>
        <div class="filters">
          <el-select v-model="fCategory" placeholder="类别" clearable style="width: 130px" @change="onFilter">
            <el-option v-for="c in CATEGORIES" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
          <el-select v-model="fStatus" placeholder="状态" clearable style="width: 130px" @change="onFilter">
            <el-option v-for="(s, k) in STATUS" :key="k" :label="s.label" :value="k" />
          </el-select>
          <el-input
            v-model="keyword"
            placeholder="搜索文件名（当前页）"
            clearable
            :prefix-icon="Search"
            style="width: 220px"
          />
        </div>

        <el-table :data="visibleRows" v-loading="loading" stripe @selection-change="onSelect">
          <el-table-column type="selection" width="44" />
          <el-table-column prop="filename" label="名称" min-width="220" show-overflow-tooltip />
          <el-table-column label="类别" width="110">
            <template #default="{ row }">{{ categoryLabel(row) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <StatusTag :status="STATUS[row.status]?.tag || 'info'" :text="STATUS[row.status]?.label || row.status" />
            </template>
          </el-table-column>
          <el-table-column label="大小" width="100" align="right">
            <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
          </el-table-column>
          <el-table-column label="分块数" width="90" align="right">
            <template #default="{ row }">{{ row.metadata?.chunk_count ?? '-' }}</template>
          </el-table-column>
          <el-table-column label="上传时间" width="160">
            <template #default="{ row }">{{ formatTime(row.uploaded_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
              <el-button link type="danger" size="small" @click="removeRow(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <EmptyState title="暂无文档" description="点击右上角「上传文档」开始构建知识库" />
          </template>
        </el-table>

        <div class="table-foot">
          <el-button size="small" type="danger" plain :disabled="!selected.length" @click="batchRemove">
            批量删除{{ selected.length ? `（${selected.length}）` : '' }}
          </el-button>
          <el-pagination
            v-model:current-page="page"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @change="load"
          />
        </div>
      </template>
    </AppCard>

    <!-- 上传：拖拽 + 类别选择 -->
    <el-dialog v-model="uploadVisible" title="上传文档" width="540px" :close-on-click-modal="false">
      <div class="upload-row">
        <span class="upload-label">文档类别</span>
        <el-select v-model="uploadCategory" style="width: 180px">
          <el-option v-for="c in CATEGORIES" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
      </div>
      <el-upload drag multiple :show-file-list="false" :http-request="doUpload" accept=".pdf,.docx,.doc,.txt,.md">
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF / Word / TXT / Markdown，单文件不超过 50MB</div>
        </template>
      </el-upload>
      <div v-if="uploadingCount" class="uploading-hint">正在上传 {{ uploadingCount }} 个文件…</div>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="文档详情" size="440px">
      <SkeletonBlock v-if="detailLoading" :rows="8" height="16px" />
      <EmptyState v-else-if="!detail" title="加载失败" description="无法获取文档详情，请稍后重试" />
      <el-descriptions v-else :column="1" border size="small">
        <el-descriptions-item label="文档 ID">{{ detail.doc_id }}</el-descriptions-item>
        <el-descriptions-item label="文件名">{{ detail.filename }}</el-descriptions-item>
        <el-descriptions-item label="类别">{{ categoryLabel(detail) }}</el-descriptions-item>
        <el-descriptions-item label="文件类型">{{ detail.file_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="大小">{{ formatSize(detail.file_size) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag
            :status="STATUS[detail.status]?.tag || 'info'"
            :text="STATUS[detail.status]?.label || detail.status"
          />
        </el-descriptions-item>
        <el-descriptions-item label="分块数">{{ detail.metadata?.chunk_count ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="上传时间">{{ formatTime(detail.uploaded_at) }}</el-descriptions-item>
        <el-descriptions-item label="处理完成">{{ formatTime(detail.processed_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </AppPage>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Refresh, Search, UploadFilled } from '@element-plus/icons-vue'
import { documentApi } from '@/api'
import AppPage from '@/components/AppPage.vue'
import AppCard from '@/components/AppCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'

// 类别取值对齐后端 DocumentType
const CATEGORIES = [
  { label: '标准规范', value: 'standard' },
  { label: '项目文档', value: 'project' },
  { label: '合同', value: 'contract' },
]
const STATUS = {
  pending: { label: '待处理', tag: 'info' },
  processing: { label: '处理中', tag: 'warning' },
  completed: { label: '已完成', tag: 'success' },
  failed: { label: '失败', tag: 'danger' },
}

// ===== 列表（Page 契约：items/total/page/page_size） =====

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const fCategory = ref('')
const fStatus = ref('')
const keyword = ref('')
const loading = ref(false)
const firstLoaded = ref(false)
const errorState = ref(null)
const selected = ref([])

// 后端列表暂不支持关键词，前端就地过滤当前页
const visibleRows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return rows.value
  return rows.value.filter((r) => (r.filename || '').toLowerCase().includes(kw))
})

async function load() {
  loading.value = true
  try {
    const res = await documentApi.list({
      page: page.value,
      page_size: pageSize.value,
      category: fCategory.value || undefined,
      status: fStatus.value || undefined,
    })
    rows.value = res.items || []
    total.value = res.total || 0
    errorState.value = null
  } catch (e) {
    rows.value = []
    total.value = 0
    errorState.value =
      e.httpStatus === 503
        ? { title: '服务未就绪', desc: e.apiError?.message || '数据库等依赖不可用，请稍后重试' }
        : { title: '加载失败', desc: e.apiError?.message || e.message || '请稍后重试' }
  } finally {
    loading.value = false
    firstLoaded.value = true
  }
}

function onFilter() {
  page.value = 1
  load()
}

function onSelect(sel) {
  selected.value = sel
}

// ===== 上传 + 状态轮询 =====

const uploadVisible = ref(false)
const uploadCategory = ref('standard')
const uploadingCount = ref(0)

async function doUpload({ file }) {
  uploadingCount.value += 1
  try {
    const fd = new FormData()
    fd.append('file', file)
    const info = await documentApi.upload(fd, { category: uploadCategory.value })
    ElMessage.success(`「${file.name}」上传成功，已排队处理`)
    await load()
    if (info?.doc_id) pollStatus(info.doc_id)
  } catch {
    /* 错误提示由拦截器统一处理 */
  } finally {
    uploadingCount.value -= 1
  }
}

const pollers = new Map()

function pollStatus(docId) {
  stopPoll(docId)
  let attempts = 0
  const timer = setInterval(async () => {
    attempts += 1
    if (attempts > 60) return stopPoll(docId)
    try {
      const st = await documentApi.status(docId)
      const row = rows.value.find((r) => r.doc_id === docId)
      if (row && st?.status) row.status = st.status
      if (st?.status === 'completed' || st?.status === 'failed') stopPoll(docId)
    } catch {
      stopPoll(docId)
    }
  }, 3000)
  pollers.set(docId, timer)
}

function stopPoll(docId) {
  clearInterval(pollers.get(docId))
  pollers.delete(docId)
}

onBeforeUnmount(() => {
  for (const t of pollers.values()) clearInterval(t)
  pollers.clear()
})

// ===== 详情 / 删除 =====

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await documentApi.detail(row.doc_id)
  } catch {
    /* 错误提示由拦截器统一处理 */
  } finally {
    detailLoading.value = false
  }
}

function removeRow(row) {
  ElMessageBox.confirm(`确认删除「${row.filename}」？删除后不可恢复`, '删除文档', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
    .then(async () => {
      await documentApi.remove(row.doc_id)
      ElMessage.success('已删除')
      load()
    })
    .catch(() => {})
}

function batchRemove() {
  const ids = selected.value.map((r) => r.doc_id)
  if (!ids.length) return
  ElMessageBox.confirm(`确认删除选中的 ${ids.length} 个文档？删除后不可恢复`, '批量删除', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
    .then(async () => {
      const res = await documentApi.batchRemove(ids)
      ElMessage.success(`删除完成：成功 ${res.success_count}/${res.total}`)
      load()
    })
    .catch(() => {})
}

// ===== 格式化 =====

function categoryLabel(row) {
  const v = row?.metadata?.category
  const hit = CATEGORIES.find((c) => c.value === v)
  return hit ? hit.label : v || '-'
}

function formatSize(bytes) {
  if (!bytes) return '-'
  const kb = bytes / 1024
  return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
}

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

onMounted(load)
</script>

<style scoped>
.filters {
  display: flex;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  flex-wrap: wrap;
}
.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
  margin-top: var(--sp-4);
}
.upload-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}
.upload-label {
  font-size: 13px;
  color: var(--c-text-2);
}
.upload-icon {
  font-size: 48px;
  color: var(--c-text-3);
}
.uploading-hint {
  margin-top: var(--sp-3);
  font-size: 13px;
  color: var(--c-text-2);
}
</style>
