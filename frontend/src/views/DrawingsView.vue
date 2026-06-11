<template>
  <div class="page-container">
    <div class="page-header">
      <h2>施工图处理</h2>
      <p>上传施工图 PDF，自动解析构件、材料、规范并同步知识图谱</p>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-select v-model="drawingType" style="width: 150px">
          <el-option label="结构图" value="structural" />
          <el-option label="建筑图" value="architectural" />
          <el-option label="机电图" value="mep" />
          <el-option label="其他" value="other" />
        </el-select>
        <el-checkbox v-model="enableOcr">启用 OCR</el-checkbox>
        <el-checkbox v-model="syncNeo4j">同步知识图谱</el-checkbox>
        <el-upload :show-file-list="false" :http-request="handleUpload" accept=".pdf">
          <el-button type="primary" :loading="uploading"><el-icon><Upload /></el-icon>上传图纸</el-button>
        </el-upload>
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" stripe>
        <template #empty><el-empty description="暂无施工图，请上传 PDF 图纸" /></template>
        <el-table-column prop="filename" label="图纸" min-width="200" show-overflow-tooltip />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="200">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.progress || 0)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :loading="entityLoading" @click="viewEntities(row)">查看实体</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawer" title="提取实体" size="46%">
      <el-descriptions v-if="summary" :column="2" border size="small" class="mb">
        <el-descriptions-item label="构件">{{ summary.components }}</el-descriptions-item>
        <el-descriptions-item label="材料">{{ summary.materials }}</el-descriptions-item>
        <el-descriptions-item label="尺寸">{{ summary.dimensions }}</el-descriptions-item>
        <el-descriptions-item label="规范">{{ summary.specifications }}</el-descriptions-item>
      </el-descriptions>
      <el-tabs v-model="entityTab">
        <el-tab-pane v-for="(list, key) in entities" :key="key" :label="`${tabLabel(key)} (${list.length})`" :name="key">
          <el-table :data="list" size="small" max-height="460">
            <el-table-column prop="id" label="ID" width="120" show-overflow-tooltip />
            <el-table-column label="属性">
              <template #default="{ row }">
                <span v-for="(v, k) in row.properties || row" :key="k" class="prop">{{ k }}: {{ v }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { drawingApi } from '@/api'

const rows = ref([])
const loading = ref(false)
const uploading = ref(false)
const entityLoading = ref(false)
const drawingType = ref('structural')
const enableOcr = ref(true)
const syncNeo4j = ref(true)

const drawer = ref(false)
const entityTab = ref('components')
const entities = reactive({ components: [], materials: [], dimensions: [], specifications: [] })
const summary = ref(null)

async function load() {
  loading.value = true
  try {
    const res = await drawingApi.list({ page: 1, page_size: 50 })
    // 后端真实返回键：drawings
    rows.value = res.drawings || []
  } finally {
    loading.value = false
  }
}

async function handleUpload({ file }) {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    await drawingApi.upload(fd, {
      drawing_type: drawingType.value,
      enable_ocr: enableOcr.value,
      sync_to_neo4j: syncNeo4j.value,
    })
    ElMessage.success('上传成功，正在解析')
    load()
  } finally {
    uploading.value = false
  }
}

async function viewEntities(row) {
  entityLoading.value = true
  try {
    const res = await drawingApi.entities(row.document_id)
    const e = res.entities || {}
    entities.components = e.components || []
    entities.materials = e.materials || []
    entities.dimensions = e.dimensions || []
    entities.specifications = e.specifications || []
    summary.value = res.summary || null
    entityTab.value = 'components'
    drawer.value = true
  } finally {
    entityLoading.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除「${row.filename}」？`, '提示', { type: 'warning' })
  await drawingApi.remove(row.document_id)
  ElMessage.success('已删除')
  load()
}

const labels = { components: '构件', materials: '材料', dimensions: '尺寸', specifications: '规范' }
const tabLabel = (k) => labels[k] || k

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.mb {
  margin-bottom: 16px;
}
.prop {
  display: inline-block;
  margin-right: 12px;
  color: #555;
}
</style>
