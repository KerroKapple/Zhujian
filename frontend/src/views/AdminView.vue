<template>
  <div class="page-container">
    <div class="page-header">
      <h2>系统管理</h2>
      <p>系统状态、索引与缓存运维</p>
    </div>

    <el-row :gutter="16" class="mb">
      <el-col :span="6" v-for="m in metrics" :key="m.label">
        <el-card shadow="never">
          <div class="metric-value">{{ m.value }}</div>
          <div class="metric-label">{{ m.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" header="组件健康">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item v-for="(v, k) in health" :key="k" :label="k">
              <el-tag :type="String(v).includes('ok') || v === true ? 'success' : 'danger'">{{ v }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" header="运维操作">
          <el-space direction="vertical" alignment="flex-start" :size="14">
            <el-button type="primary" :loading="rebuilding" @click="rebuild">重建检索索引</el-button>
            <el-button :loading="clearing" @click="clearCache">清空缓存</el-button>
            <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新状态</el-button>
          </el-space>
          <el-divider />
          <div class="index-stats" v-if="indexStats">
            <div>文档总数：<b>{{ indexStats.total_documents ?? '-' }}</b></div>
            <div>分块总数：<b>{{ indexStats.total_chunks ?? '-' }}</b></div>
            <div>向量维度：<b>{{ indexStats.vector_dimension ?? '-' }}</b></div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api'

const metrics = ref([
  { label: 'CPU 使用率', value: '-' },
  { label: '内存使用率', value: '-' },
  { label: '磁盘使用率', value: '-' },
  { label: '运行时长(h)', value: '-' },
])
const health = reactive({})
const indexStats = ref(null)
const rebuilding = ref(false)
const clearing = ref(false)

async function refresh() {
  try {
    const s = await adminApi.status()
    metrics.value[0].value = fmt(s.cpu_percent)
    metrics.value[1].value = fmt(s.memory_percent)
    metrics.value[2].value = fmt(s.disk_percent)
    metrics.value[3].value = s.uptime != null ? (s.uptime / 3600).toFixed(1) : '-'
  } catch (e) {
    /* ignore */
  }
  try {
    const h = await adminApi.health()
    Object.keys(health).forEach((k) => delete health[k])
    Object.assign(health, h.components || h)
  } catch (e) {
    /* ignore */
  }
  try {
    indexStats.value = await adminApi.indexStats()
  } catch (e) {
    /* ignore */
  }
}

async function rebuild() {
  rebuilding.value = true
  try {
    await adminApi.rebuildIndex()
    ElMessage.success('已触发索引重建')
  } finally {
    rebuilding.value = false
  }
}

async function clearCache() {
  clearing.value = true
  try {
    await adminApi.clearCache({})
    ElMessage.success('缓存已清空')
  } finally {
    clearing.value = false
  }
}

const fmt = (v) => (v != null ? `${Number(v).toFixed(1)}%` : '-')

onMounted(refresh)
</script>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.metric-label {
  color: #8a8f99;
  font-size: 13px;
}
.index-stats div {
  padding: 4px 0;
  color: #555;
}
</style>
