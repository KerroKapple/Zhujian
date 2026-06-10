<template>
  <div class="page-container">
    <div class="page-header">
      <h2>项目管理</h2>
      <p>管理工程项目，作为智能分析的数据维度</p>
    </div>

    <el-card shadow="never">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建项目</el-button>
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="项目ID" width="120" show-overflow-tooltip />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="预算" width="140">
          <template #default="{ row }">{{ row.budget != null ? `¥${row.budget}` : '-' }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始" width="130" />
        <el-table-column prop="end_date" label="结束" width="130" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialog" title="新建项目" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
        <el-form-item label="预算"><el-input-number v-model="form.budget" :min="0" /></el-form-item>
        <el-form-item label="周期">
          <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi } from '@/api'

const rows = ref([])
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const dateRange = ref([])
const form = reactive({ name: '', description: '', budget: 0 })

async function load() {
  loading.value = true
  try {
    const res = await projectApi.list({ skip: 0, limit: 100 })
    rows.value = res.data || res.items || res.projects || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.name = ''
  form.description = ''
  form.budget = 0
  dateRange.value = []
  dialog.value = true
}

async function create() {
  if (!form.name.trim()) return ElMessage.warning('请输入项目名称')
  saving.value = true
  try {
    await projectApi.create({
      name: form.name,
      description: form.description,
      budget: form.budget,
      start_date: dateRange.value?.[0],
      end_date: dateRange.value?.[1],
    })
    ElMessage.success('创建成功')
    dialog.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
  await projectApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
