<template>
  <div class="page-container">
    <div class="page-header">
      <h2>文档管理</h2>
      <p>上传、查看与管理知识库文档</p>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 140px" @change="load">
          <el-option label="待处理" value="pending" />
          <el-option label="处理中" value="processing" />
          <el-option label="已完成" value="completed" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-upload
          :show-file-list="false"
          :http-request="handleUpload"
          accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg"
        >
          <el-button type="primary" :loading="uploading"><el-icon><Upload /></el-icon>上传文档</el-button>
        </el-upload>
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>

      <el-table :data="docs" v-loading="loading" stripe>
        <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="90" />
        <el-table-column label="大小" width="110">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="uploaded_at" label="上传时间" width="190" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
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
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { documentApi } from '@/api'

const docs = ref([])
const total = ref(0)
const loading = ref(false)
const uploading = ref(false)
const filters = reactive({ page: 1, page_size: 10, status: '' })

async function load() {
  loading.value = true
  try {
    const res = await documentApi.list({ ...filters })
    docs.value = res.documents || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

function onPage(p) {
  filters.page = p
  load()
}

async function handleUpload({ file }) {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    await documentApi.upload(fd, { category: '规范标准' })
    ElMessage.success('上传成功，正在后台处理')
    load()
  } finally {
    uploading.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除「${row.filename}」？`, '提示', { type: 'warning' })
  await documentApi.remove(row.doc_id)
  ElMessage.success('已删除')
  load()
}

function formatSize(bytes) {
  if (!bytes) return '-'
  const kb = bytes / 1024
  return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
}
const statusMap = {
  pending: ['待处理', 'info'],
  processing: ['处理中', 'warning'],
  completed: ['已完成', 'success'],
  failed: ['失败', 'danger'],
}
const statusText = (s) => statusMap[s]?.[0] || s
const statusType = (s) => statusMap[s]?.[1] || 'info'

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
