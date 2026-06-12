<template>
  <AppPage title="系统管理" description="系统状态、组件健康、数据统计与运维操作">
    <template #actions>
      <el-button :icon="Refresh" :loading="refreshing" @click="refresh">刷新</el-button>
    </template>

    <!-- 指标行：CPU / 内存 / 磁盘 / 运行时长 -->
    <el-row :gutter="16">
      <el-col v-for="m in metrics" :key="m.label" :xs="12" :md="6" class="grid-col">
        <StatTile
          :label="m.label"
          :value="m.value"
          :unit="m.unit"
          :status="m.status"
          :icon="m.icon"
        />
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 组件健康 -->
      <el-col :xs="24" :md="12" class="grid-col">
        <AppCard title="组件健康" :status="healthStrip" :loading="healthLoading">
          <EmptyState
            v-if="healthError"
            :title="healthError.unready ? '服务未就绪' : '加载失败'"
            :description="healthError.message"
          />
          <template v-else-if="health">
            <el-alert
              v-if="health.status !== 'healthy'"
              type="warning"
              :closable="false"
              show-icon
              title="部分组件离线，系统降级运行"
              class="health-alert"
            />
            <ul class="comp-list">
              <li v-for="c in components" :key="c.key" class="comp-item">
                <span class="comp-name">{{ c.name }}</span>
                <span v-if="c.detail" class="comp-detail" :title="c.detail">{{ c.detail }}</span>
                <StatusTag :status="c.ok ? 'success' : 'danger'" :text="c.ok ? '在线' : '离线'" />
              </li>
            </ul>
          </template>
        </AppCard>
      </el-col>

      <!-- 运维操作 -->
      <el-col :xs="24" :md="12" class="grid-col">
        <AppCard title="运维操作" status="warning">
          <el-alert
            v-if="opNotice"
            type="warning"
            :closable="true"
            show-icon
            :title="opNotice"
            class="op-alert"
            @close="opNotice = ''"
          />
          <div class="op-row">
            <div class="op-text">
              <div class="op-name">重建检索索引</div>
              <div class="op-desc">全量重建 BM25 与向量索引，耗时较长</div>
            </div>
            <el-button type="primary" :loading="rebuilding" @click="rebuild">重建</el-button>
          </div>
          <div class="op-row">
            <div class="op-text">
              <div class="op-name">清空缓存</div>
              <div class="op-desc">清理 Redis 查询缓存，下次查询重新计算</div>
            </div>
            <el-button type="danger" plain :loading="clearing" @click="clearCache">清空</el-button>
          </div>
        </AppCard>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 数据统计 -->
      <el-col :xs="24" :md="12" class="grid-col">
        <AppCard title="数据统计" status="info" :loading="statsLoading">
          <template #extra>
            <span class="card-extra-text">近 7 天</span>
          </template>
          <EmptyState
            v-if="statsError"
            :title="statsError.unready ? '服务未就绪' : '加载失败'"
            :description="statsError.message"
          />
          <template v-else>
            <el-alert
              v-if="statsDegraded"
              type="warning"
              :closable="false"
              show-icon
              :title="`统计降级：${stats?.reason || indexStats?.reason || '数据库不可用'}`"
              class="stats-alert"
            />
            <ul class="kv-list">
              <li v-for="row in statRows" :key="row.label" class="kv-item">
                <span class="kv-label">{{ row.label }}</span>
                <b class="kv-value">{{ row.value }}</b>
              </li>
            </ul>
            <template v-if="popularQueries.length">
              <div class="popular-title">热门问题</div>
              <ul class="popular-list">
                <li v-for="(q, i) in popularQueries" :key="i" class="popular-item">
                  <span class="popular-rank">{{ i + 1 }}</span>
                  <span class="popular-text">{{ q.query }}</span>
                  <span class="popular-count">{{ q.count }} 次</span>
                </li>
              </ul>
            </template>
          </template>
        </AppCard>
      </el-col>

      <!-- 系统配置 -->
      <el-col :xs="24" :md="12" class="grid-col">
        <AppCard title="系统配置" status="primary" :loading="configLoading">
          <template #extra>
            <span class="card-extra-text">只读</span>
          </template>
          <EmptyState
            v-if="configError"
            :title="configError.unready ? '服务未就绪' : '加载失败'"
            :description="configError.message"
          />
          <el-descriptions v-else-if="config" :column="1" border size="small">
            <el-descriptions-item label="应用名称">{{ config.app_name }}</el-descriptions-item>
            <el-descriptions-item label="版本">{{ config.app_version }}</el-descriptions-item>
            <el-descriptions-item label="环境">{{ config.environment }}</el-descriptions-item>
            <el-descriptions-item label="调试模式">{{ config.debug ? '开启' : '关闭' }}</el-descriptions-item>
            <el-descriptions-item label="LLM 模型">{{ config.llm_model || '—' }}</el-descriptions-item>
            <el-descriptions-item label="嵌入模型">{{ config.embedding_model || '—' }}</el-descriptions-item>
            <el-descriptions-item label="向量维度">{{ config.vector_dimension }}</el-descriptions-item>
          </el-descriptions>
        </AppCard>
      </el-col>
    </el-row>
  </AppPage>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Cpu, Odometer, Coin, Timer } from '@element-plus/icons-vue'
import { adminApi } from '@/api'
import AppPage from '@/components/AppPage.vue'
import AppCard from '@/components/AppCard.vue'
import StatTile from '@/components/StatTile.vue'
import StatusTag from '@/components/StatusTag.vue'
import EmptyState from '@/components/EmptyState.vue'

// 错误归一：503 = 服务未就绪（降级）
function errInfo(e) {
  return {
    unready: e?.httpStatus === 503,
    message: e?.apiError?.message || e?.message || '请求失败',
  }
}

// 占用率 → 语义色
const usageStatus = (v) => (v == null ? 'info' : v >= 90 ? 'danger' : v >= 70 ? 'warning' : 'success')

// ===== 系统状态指标 =====
const status = ref(null)
const metrics = computed(() => {
  const s = status.value
  const fmt = (v) => (v == null ? '—' : Number(v).toFixed(1))
  return [
    { label: 'CPU 使用率', value: fmt(s?.cpu_percent), unit: '%', status: usageStatus(s?.cpu_percent), icon: Cpu },
    { label: '内存使用率', value: fmt(s?.memory_percent), unit: '%', status: usageStatus(s?.memory_percent), icon: Odometer },
    { label: '磁盘使用率', value: fmt(s?.disk_percent), unit: '%', status: usageStatus(s?.disk_percent), icon: Coin },
    {
      label: '运行时长',
      value: s?.uptime != null ? (s.uptime / 3600).toFixed(1) : '—',
      unit: 'h',
      status: 'info',
      icon: Timer,
    },
  ]
})

async function loadStatus() {
  try {
    status.value = await adminApi.status()
  } catch {
    status.value = null
  }
}

// ===== 组件健康 =====
const COMPONENT_NAMES = [
  ['database', 'PostgreSQL'],
  ['redis', 'Redis'],
  ['vector_db', 'Milvus'],
  ['graph_db', 'Neo4j'],
]
const health = ref(null)
const healthLoading = ref(true)
const healthError = ref(null)

const components = computed(() =>
  COMPONENT_NAMES.map(([key, name]) => {
    const c = health.value?.components?.[key] || {}
    return { key, name, ok: !!c.ok, detail: c.detail || '' }
  })
)
const healthStrip = computed(() =>
  !health.value ? 'info' : health.value.status === 'healthy' ? 'success' : 'warning'
)

async function loadHealth() {
  healthLoading.value = true
  healthError.value = null
  try {
    health.value = await adminApi.health()
  } catch (e) {
    health.value = null
    healthError.value = errInfo(e)
  } finally {
    healthLoading.value = false
  }
}

// ===== 数据统计（statistics + indexStats，degraded 字段显示未就绪） =====
const stats = ref(null)
const indexStats = ref(null)
const statsLoading = ref(true)
const statsError = ref(null)

const statsDegraded = computed(() => !!(stats.value?.degraded || indexStats.value?.degraded))
const NA = '未就绪'
const statRows = computed(() => {
  const s = stats.value
  const ix = indexStats.value
  const pick = (src, key, fmt = (v) => v) => (src && !src.degraded && src[key] != null ? fmt(src[key]) : NA)
  return [
    { label: '文档总数', value: pick(ix, 'total_documents') },
    { label: '分块总数', value: pick(ix, 'total_chunks') },
    { label: '向量维度', value: ix?.vector_dimension ?? NA },
    { label: '查询总数', value: pick(s, 'total_queries') },
    { label: '平均响应', value: pick(s, 'avg_response_time', (v) => `${v} s`) },
    { label: '成功率', value: pick(s, 'success_rate', (v) => `${(v * 100).toFixed(1)}%`) },
  ]
})
const popularQueries = computed(() => (stats.value?.popular_queries || []).slice(0, 5))

async function loadStats() {
  statsLoading.value = true
  statsError.value = null
  try {
    const [s, ix] = await Promise.all([adminApi.statistics({ days: 7 }), adminApi.indexStats()])
    stats.value = s
    indexStats.value = ix
  } catch (e) {
    stats.value = null
    indexStats.value = null
    statsError.value = errInfo(e)
  } finally {
    statsLoading.value = false
  }
}

// ===== 系统配置 =====
const config = ref(null)
const configLoading = ref(true)
const configError = ref(null)

async function loadConfig() {
  configLoading.value = true
  configError.value = null
  try {
    config.value = await adminApi.config()
  } catch (e) {
    config.value = null
    configError.value = errInfo(e)
  } finally {
    configLoading.value = false
  }
}

// ===== 运维操作（confirm + loading + 503 降级提示） =====
const rebuilding = ref(false)
const clearing = ref(false)
const opNotice = ref('')

function opFail(e, action) {
  const info = errInfo(e)
  opNotice.value = info.unready ? `服务未就绪，无法${action}：${info.message}` : `${action}失败：${info.message}`
}

async function rebuild() {
  try {
    await ElMessageBox.confirm('将全量重建 BM25 与向量索引，期间检索可能不可用，确认继续？', '重建检索索引', {
      type: 'warning',
      confirmButtonText: '确认重建',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  rebuilding.value = true
  opNotice.value = ''
  try {
    await adminApi.rebuildIndex()
    ElMessage.success('已触发索引重建')
    loadStats()
  } catch (e) {
    opFail(e, '重建索引')
  } finally {
    rebuilding.value = false
  }
}

async function clearCache() {
  try {
    await ElMessageBox.confirm('将清空 Redis 查询缓存，确认继续？', '清空缓存', {
      type: 'warning',
      confirmButtonText: '确认清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  clearing.value = true
  opNotice.value = ''
  try {
    await adminApi.clearCache({})
    ElMessage.success('缓存已清空')
  } catch (e) {
    opFail(e, '清空缓存')
  } finally {
    clearing.value = false
  }
}

// ===== 刷新（各自独立，不连坐） =====
const refreshing = ref(false)
async function refresh() {
  refreshing.value = true
  await Promise.allSettled([loadStatus(), loadHealth(), loadStats(), loadConfig()])
  refreshing.value = false
}

onMounted(refresh)
</script>

<style scoped>
.grid-col {
  margin-bottom: var(--sp-4);
}
.el-row {
  margin-bottom: calc(var(--sp-4) * -1);
}

/* 组件健康 */
.health-alert {
  margin-bottom: var(--sp-3);
}
.comp-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.comp-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 10px 4px;
  border-bottom: 1px solid var(--c-border);
}
.comp-item:last-child {
  border-bottom: none;
}
.comp-name {
  flex: 1;
  font-size: 14px;
  color: var(--c-text);
  font-weight: 500;
}
.comp-detail {
  max-width: 50%;
  font-size: 12px;
  color: var(--c-text-3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 运维操作 */
.op-alert {
  margin-bottom: var(--sp-3);
}
.op-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: 12px 4px;
  border-bottom: 1px solid var(--c-border);
}
.op-row:last-child {
  border-bottom: none;
}
.op-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--c-text);
}
.op-desc {
  margin-top: 2px;
  font-size: 12px;
  color: var(--c-text-3);
}

/* 数据统计 */
.stats-alert {
  margin-bottom: var(--sp-3);
}
.kv-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--sp-5);
}
.kv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px;
  border-bottom: 1px solid var(--c-border);
  font-size: 13px;
}
.kv-label {
  color: var(--c-text-2);
}
.kv-value {
  color: var(--c-text);
}
.popular-title {
  margin: var(--sp-4) 0 var(--sp-2);
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text);
}
.popular-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.popular-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: 6px 4px;
  font-size: 13px;
}
.popular-rank {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 4px;
  background: var(--c-surface-2);
  color: var(--c-text-2);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.popular-text {
  flex: 1;
  min-width: 0;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.popular-count {
  flex-shrink: 0;
  color: var(--c-text-3);
  font-size: 12px;
}

.card-extra-text {
  font-size: 12px;
  color: var(--c-text-3);
}
</style>
