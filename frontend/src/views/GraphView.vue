<template>
  <div class="graph-board">
    <div class="board-head">
      <div>
        <h2>知识图谱</h2>
        <p>施工图实体关系网络 · Neo4j 暗色看板</p>
      </div>
      <el-button v-if="healthOk" class="ghost-btn" :loading="refreshing" @click="initAll">刷新</el-button>
    </div>

    <!-- Neo4j 不可用：整页空态 -->
    <div v-if="!healthOk" class="board-down">
      <EmptyState title="Neo4j 未就绪" description="图数据库连接不可用，请确认 Neo4j 服务已启动后重试">
        <el-button type="primary" :loading="refreshing" @click="initAll">重试</el-button>
      </EmptyState>
    </div>

    <template v-else>
      <!-- 指标行 -->
      <div class="tile-row">
        <div v-for="t in tiles" :key="t.label" class="d-tile">
          <span class="tile-strip" :style="{ background: t.color }" />
          <div class="tile-label">{{ t.label }}</div>
          <div class="tile-value" :style="{ color: t.color }">{{ t.value }}</div>
        </div>
      </div>

      <div class="board-main">
        <!-- 左：文档子图可视化 -->
        <div class="board-card viz-card">
          <div class="card-head">
            <span class="card-title">文档子图</span>
            <div class="viz-tools">
              <el-select
                v-model="docId"
                class="doc-select"
                filterable
                allow-create
                default-first-option
                clearable
                :teleported="false"
                placeholder="输入或选择文档 ID"
              >
                <el-option v-for="d in docOptions" :key="d.value" :label="d.label" :value="d.value" />
              </el-select>
              <el-button type="primary" :loading="vizLoading" @click="loadGraph">加载</el-button>
            </div>
          </div>
          <div class="viz-body" v-loading="vizLoading" element-loading-background="rgba(13,17,23,.7)">
            <BaseChart v-if="hasGraph" ref="chartRef" :option="graphOption" height="520px" />
            <EmptyState
              v-else
              title="暂无图谱数据"
              description="输入文档 ID 加载力导向图；节点按类型分色，可缩放拖拽，点击节点查看关联"
            />
          </div>
          <!-- 节点关联结果 -->
          <div v-if="connected.visible" class="connected-bar">
            <div class="connected-head">
              <span>「{{ connected.name }}」关联节点 · {{ connected.items.length }}</span>
              <el-button link @click="connected.visible = false">收起</el-button>
            </div>
            <div class="connected-list" v-loading="connected.loading" element-loading-background="rgba(13,17,23,.7)">
              <el-tag v-for="c in connected.items" :key="c.id" class="connected-tag">
                {{ c.code || c.id }}{{ c.type ? ` · ${c.type}` : '' }}
              </el-tag>
              <span v-if="!connected.loading && !connected.items.length" class="connected-none">无关联节点</span>
            </div>
          </div>
        </div>

        <!-- 右：检索面板 -->
        <div class="board-card panel-card">
          <el-tabs v-model="panelTab" @tab-change="onTabChange">
            <el-tab-pane label="构件" name="components">
              <div class="panel-tools">
                <el-input
                  v-model="comp.keyword"
                  placeholder="按编号搜索，如 KZ1"
                  clearable
                  @keyup.enter="searchComponents"
                  @clear="resetComponents"
                />
                <el-button :loading="comp.loading" @click="searchComponents">搜索</el-button>
              </div>
              <el-table
                :data="comp.items"
                size="small"
                max-height="400"
                v-loading="comp.loading"
                element-loading-background="rgba(13,17,23,.7)"
              >
                <template #empty><EmptyState title="暂无构件" /></template>
                <el-table-column prop="code" label="编号" width="110" show-overflow-tooltip />
                <el-table-column prop="type" label="类型" width="100" />
                <el-table-column label="属性">
                  <template #default="{ row }">{{ propText(row.properties, ['code', 'type']) }}</template>
                </el-table-column>
              </el-table>
              <el-pagination
                v-if="!comp.keyword"
                class="panel-pager"
                small
                layout="prev, pager, next"
                :total="comp.total"
                :page-size="comp.pageSize"
                :current-page="comp.page"
                @current-change="(p) => { comp.page = p; loadComponents() }"
              />
            </el-tab-pane>

            <el-tab-pane label="材料" name="materials">
              <el-table
                :data="mat.items"
                size="small"
                max-height="440"
                v-loading="mat.loading"
                element-loading-background="rgba(13,17,23,.7)"
              >
                <template #empty><EmptyState title="暂无材料" /></template>
                <el-table-column prop="grade" label="等级" width="110" show-overflow-tooltip />
                <el-table-column prop="type" label="类型" width="100" />
                <el-table-column label="属性">
                  <template #default="{ row }">{{ propText(row.properties, ['grade', 'type']) }}</template>
                </el-table-column>
              </el-table>
              <el-pagination
                class="panel-pager"
                small
                layout="prev, pager, next"
                :total="mat.total"
                :page-size="mat.pageSize"
                :current-page="mat.page"
                @current-change="(p) => { mat.page = p; loadMaterials() }"
              />
            </el-tab-pane>

            <el-tab-pane label="规范" name="specifications">
              <el-table
                class="spec-table"
                :data="spec.items"
                size="small"
                max-height="280"
                v-loading="spec.loading"
                element-loading-background="rgba(13,17,23,.7)"
                @row-click="(row) => loadSpecDocs(row.code)"
              >
                <template #empty><EmptyState title="暂无规范" /></template>
                <el-table-column prop="code" label="编号" width="150" show-overflow-tooltip />
                <el-table-column prop="name" label="名称" show-overflow-tooltip />
              </el-table>
              <el-pagination
                class="panel-pager"
                small
                layout="prev, pager, next"
                :total="spec.total"
                :page-size="spec.pageSize"
                :current-page="spec.page"
                @current-change="(p) => { spec.page = p; loadSpecifications() }"
              />
              <div v-if="spec.selected" class="spec-docs">
                <div class="spec-docs-head">规范 {{ spec.selected }} 关联文档 · {{ spec.docs.length }}</div>
                <el-table
                  :data="spec.docs"
                  size="small"
                  max-height="180"
                  v-loading="spec.docsLoading"
                  element-loading-background="rgba(13,17,23,.7)"
                >
                  <template #empty><EmptyState title="无关联文档" /></template>
                  <el-table-column label="文档" show-overflow-tooltip>
                    <template #default="{ row }">{{ row.document?.name || row.document?.id || '-' }}</template>
                  </el-table-column>
                  <el-table-column prop="components_count" label="构件数" width="80" align="center" />
                </el-table>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { graphApi, drawingApi } from '@/api'
import request from '@/api/request'
import BaseChart from '@/components/BaseChart.vue'
import EmptyState from '@/components/EmptyState.vue'

// 节点标签 → 暗色看板配色
const LABEL_COLORS = {
  Document: '#e6edf3',
  Component: '#2dd4bf',
  Material: '#f59e0b',
  Specification: '#1f6feb',
  Dimension: '#8b96a5',
}

const healthOk = ref(true)
const refreshing = ref(false)
const stats = ref(null)

const docId = ref('')
const docOptions = ref([])
const vizLoading = ref(false)
const viz = reactive({ nodes: [], edges: [], categories: [] })
const chartRef = ref(null)

const connected = reactive({ visible: false, loading: false, name: '', items: [] })

const panelTab = ref('components')
const comp = reactive({ items: [], total: 0, page: 1, pageSize: 10, keyword: '', loading: false, loaded: false })
const mat = reactive({ items: [], total: 0, page: 1, pageSize: 10, loading: false, loaded: false })
const spec = reactive({ items: [], total: 0, page: 1, pageSize: 10, loading: false, loaded: false, selected: '', docs: [], docsLoading: false })

const tiles = computed(() => [
  { label: '节点总数', value: stats.value?.total_nodes ?? 0, color: 'var(--d-accent)' },
  { label: '关系总数', value: stats.value?.total_relationships ?? 0, color: 'var(--d-accent-2)' },
  { label: '构件', value: stats.value?.node_labels?.Component ?? 0, color: 'var(--d-accent)' },
  { label: '材料', value: stats.value?.node_labels?.Material ?? 0, color: 'var(--d-accent-2)' },
])

const hasGraph = computed(() => viz.nodes.length > 0)

// 空数据守卫：nodes/edges 全部兜底为空数组
const graphOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: '#1b2433',
    borderColor: '#232b38',
    textStyle: { color: '#e6edf3' },
  },
  legend: {
    top: 0,
    left: 0,
    itemWidth: 10,
    itemHeight: 10,
    textStyle: { color: '#8b96a5', fontSize: 12 },
    data: (viz.categories || []).map((c) => c.name),
  },
  series: [
    {
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      label: { show: true, position: 'right', color: '#e6edf3', fontSize: 11 },
      lineStyle: { color: '#3a4659', curveness: 0.1 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 2 } },
      force: { repulsion: 160, edgeLength: 90, gravity: 0.08 },
      categories: viz.categories || [],
      data: (viz.nodes || []).map((n) => ({
        id: String(n.id),
        name: n.name,
        category: n.category,
        symbolSize: n.symbolSize || 20,
      })),
      links: (viz.edges || []).map((e) => ({
        source: String(e.source),
        target: String(e.target),
        value: e.value,
      })),
    },
  ],
}))

// ===== 初始化 / 健康检查 =====

async function initAll() {
  refreshing.value = true
  try {
    const h = await graphApi.health()
    healthOk.value = !!h.connected
  } catch (e) {
    healthOk.value = false
  }
  if (healthOk.value) {
    loadStats()
    loadDocOptions()
    comp.loaded = false
    mat.loaded = false
    spec.loaded = false
    onTabChange(panelTab.value)
  }
  refreshing.value = false
}

async function loadStats() {
  try {
    stats.value = await graphApi.statistics()
  } catch (e) {
    if (e.httpStatus === 503) healthOk.value = false
  }
}

// 文档下拉：取已完成施工图（失败静默，仍可手输 ID）
async function loadDocOptions() {
  try {
    const res = await drawingApi.list({ page: 1, page_size: 50 })
    docOptions.value = (res.items || [])
      .filter((i) => i.status === 'completed')
      .map((i) => ({ value: i.document_id, label: `${i.filename}（${i.document_id}）` }))
  } catch (e) {
    docOptions.value = []
  }
}

// ===== 可视化 =====

async function loadGraph() {
  const id = (docId.value || '').trim()
  if (!id) {
    ElMessage.warning('请输入文档 ID')
    return
  }
  vizLoading.value = true
  try {
    const res = await graphApi.visualization(id, { max_nodes: 200 })
    viz.nodes = res.nodes || []
    viz.edges = res.edges || []
    viz.categories = (res.categories || []).map((c) => ({
      name: c.name,
      itemStyle: { color: LABEL_COLORS[c.name] || '#8b96a5' },
    }))
    connected.visible = false
    if (!viz.nodes.length) ElMessage.info('该文档暂无图谱数据')
  } catch (e) {
    if (e.httpStatus === 503) healthOk.value = false
  } finally {
    vizLoading.value = false
  }
}

// 图渲染后绑定节点点击（重复绑定前先 off）
function onChartClick(params) {
  if (params.dataType !== 'node') return
  loadConnected(params.data.id, params.data.name)
}

watch(hasGraph, async (v) => {
  if (!v) return
  await nextTick()
  const chart = chartRef.value?.getChart?.()
  if (chart) {
    chart.off('click', onChartClick)
    chart.on('click', onChartClick)
  }
})

async function loadConnected(nodeId, name) {
  connected.visible = true
  connected.loading = true
  connected.name = name || nodeId
  try {
    const res = await graphApi.connected(nodeId, { depth: 2 })
    connected.items = res.items || []
  } catch (e) {
    connected.items = []
  } finally {
    connected.loading = false
  }
}

// ===== 检索面板 =====

function onTabChange(name) {
  if (name === 'components' && !comp.loaded) loadComponents()
  if (name === 'materials' && !mat.loaded) loadMaterials()
  if (name === 'specifications' && !spec.loaded) loadSpecifications()
}

async function loadComponents() {
  comp.loading = true
  try {
    const res = await graphApi.components({ page: comp.page, page_size: comp.pageSize })
    comp.items = res.items || []
    comp.total = res.total || 0
    comp.loaded = true
  } catch (e) {
    if (e.httpStatus === 503) healthOk.value = false
  } finally {
    comp.loading = false
  }
}

// 按 code 关键词搜索构件（清空则回到分页列表）
async function searchComponents() {
  const kw = comp.keyword.trim()
  if (!kw) {
    resetComponents()
    return
  }
  comp.loading = true
  try {
    const res = await graphApi.search({ query: kw, node_types: ['Component'], limit: 50 })
    comp.items = (res.items || []).map((n) => ({
      id: n.id,
      code: n.properties?.code || '',
      type: n.properties?.type || '',
      properties: n.properties || {},
    }))
    comp.total = res.total || 0
  } catch (e) {
    if (e.httpStatus === 503) healthOk.value = false
  } finally {
    comp.loading = false
  }
}

function resetComponents() {
  comp.keyword = ''
  comp.page = 1
  loadComponents()
}

async function loadMaterials() {
  mat.loading = true
  try {
    const res = await graphApi.materials({ page: mat.page, page_size: mat.pageSize })
    mat.items = res.items || []
    mat.total = res.total || 0
    mat.loaded = true
  } catch (e) {
    if (e.httpStatus === 503) healthOk.value = false
  } finally {
    mat.loading = false
  }
}

async function loadSpecifications() {
  spec.loading = true
  try {
    const res = await graphApi.specifications({ page: spec.page, page_size: spec.pageSize })
    spec.items = res.items || []
    spec.total = res.total || 0
    spec.loaded = true
  } catch (e) {
    if (e.httpStatus === 503) healthOk.value = false
  } finally {
    spec.loading = false
  }
}

// 规范关联文档（graphApi 未封装该端点，直接走统一 request）
async function loadSpecDocs(code) {
  if (!code) return
  spec.selected = code
  spec.docsLoading = true
  try {
    const res = await request.get(`/graph/specification/${encodeURIComponent(code)}/documents`)
    spec.docs = res.items || []
  } catch (e) {
    spec.docs = []
  } finally {
    spec.docsLoading = false
  }
}

// ===== 工具 =====

function propText(props, skipKeys = []) {
  if (!props) return '-'
  const skip = new Set(['id', 'doc_id', ...skipKeys])
  const parts = Object.entries(props)
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== '' && typeof v !== 'object')
    .map(([k, v]) => `${k}: ${v}`)
  return parts.length ? parts.join('；') : '-'
}

onMounted(initAll)
</script>

<style scoped>
/* 整页暗色看板：覆盖共享组件与 Element Plus 的 CSS 变量 */
.graph-board {
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
  --el-pagination-bg-color: transparent;
  --el-pagination-button-disabled-bg-color: transparent;
  --el-pagination-text-color: var(--d-text-2);
  --el-pagination-button-color: var(--d-text-2);
  --el-disabled-bg-color: #131926;
}
.board-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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
.ghost-btn {
  background: transparent;
  border-color: var(--d-border);
  color: var(--d-text-2);
}
.board-down {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--d-border);
  border-radius: var(--r-lg);
  background: var(--d-surface);
}

/* 指标行 */
.tile-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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
.tile-label {
  font-size: 13px;
  color: var(--d-text-2);
}
.tile-value {
  margin-top: 6px;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
}

/* 主区 */
.board-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: var(--sp-4);
  align-items: start;
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
.viz-tools {
  display: flex;
  gap: var(--sp-2);
}
.doc-select {
  width: 300px;
}
.viz-body {
  min-height: 520px;
}

/* 关联节点条 */
.connected-bar {
  margin-top: var(--sp-4);
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--d-border);
  border-radius: var(--r-sm);
  background: #131926;
}
.connected-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: var(--d-text);
  margin-bottom: var(--sp-2);
}
.connected-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  min-height: 28px;
}
.connected-tag {
  --el-tag-bg-color: rgba(45, 212, 191, 0.1);
  --el-tag-border-color: rgba(45, 212, 191, 0.35);
  --el-tag-text-color: var(--d-accent);
}
.connected-none {
  font-size: 12px;
  color: var(--d-text-2);
}

/* 检索面板 */
.panel-tools {
  display: flex;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
}
.panel-pager {
  margin-top: var(--sp-3);
  justify-content: flex-end;
}
.spec-table :deep(tbody tr) {
  cursor: pointer;
}
.spec-docs {
  margin-top: var(--sp-4);
  padding-top: var(--sp-3);
  border-top: 1px dashed var(--d-border);
}
.spec-docs-head {
  font-size: 13px;
  color: var(--d-accent-2);
  margin-bottom: var(--sp-2);
}

@media (max-width: 1280px) {
  .board-main {
    grid-template-columns: 1fr;
  }
}
</style>
