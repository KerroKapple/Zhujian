<template>
  <AppPage class="qa-root" title="智能问答" description="基于知识库的 RAG 检索问答，支持流式输出与引用溯源">
    <template #actions>
      <div class="toolbar">
        <span class="tool-label">流式</span>
        <el-switch v-model="streamMode" :disabled="sending" />
        <el-divider direction="vertical" />
        <span class="tool-label">召回 {{ topK }}</span>
        <el-slider v-model="topK" :min="3" :max="10" :step="1" show-stops class="topk" :disabled="sending" />
        <el-divider direction="vertical" />
        <span class="tool-label">重排序</span>
        <el-switch v-model="useRerank" :disabled="sending" />
        <el-divider direction="vertical" />
        <el-button :icon="Delete" :disabled="!messages.length" @click="clearChat">清空对话</el-button>
      </div>
    </template>

    <div class="qa-panel">
      <!-- 消息流 -->
      <div ref="chatRef" class="chat">
        <EmptyState
          v-if="!messages.length"
          :icon="ChatDotRound"
          title="向知识库提问"
          description="答案基于规范 / 合同 / 项目文档检索生成，并附引用来源"
        >
          <div class="examples">
            <el-button v-for="q in EXAMPLES" :key="q" round size="small" @click="sendQuestion(q)">
              {{ q }}
            </el-button>
          </div>
        </EmptyState>

        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="bubble">
            <!-- 降级/失败警示：保留对话不清空 -->
            <el-alert
              v-if="m.degraded"
              type="warning"
              show-icon
              :closable="false"
              title="服务未就绪 / 已降级"
              :description="m.degradedReason"
              class="degraded"
            />

            <div v-if="m.content" class="content">{{ m.content }}<span v-if="m.streaming" class="cursor">▍</span></div>
            <div v-else-if="m.streaming" class="content thinking">检索生成中…<span class="cursor">▍</span></div>

            <!-- 引用来源（meta 事件后渲染，可折叠） -->
            <div v-if="m.sources && m.sources.length" class="sources">
              <el-collapse>
                <el-collapse-item name="src">
                  <template #title>
                    <span class="src-summary">引用来源（{{ m.sources.length }}）</span>
                  </template>
                  <div v-for="(s, si) in m.sources" :key="si" class="src-item">
                    <div class="src-head">
                      <el-tag size="small" effect="plain" type="info">#{{ si + 1 }}</el-tag>
                      <span class="src-doc" :title="s.doc_id">{{ s.doc_id || '未知文档' }}</span>
                      <el-tag v-if="s.from_graph" size="small" effect="plain" type="success">图谱</el-tag>
                      <span class="src-score">相关度 {{ formatScore(s.score) }}</span>
                    </div>
                    <div class="src-text">{{ s.text }}</div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 助手消息脚部：评分反馈 + 复制 + query_id -->
            <div v-if="m.role === 'assistant' && !m.streaming" class="foot">
              <template v-if="!m.degraded">
                <el-tooltip
                  content="未关联查询记录（数据库未就绪），无法提交反馈"
                  :disabled="!!m.queryId"
                  placement="top"
                >
                  <span class="rate-wrap">
                    <el-rate v-model="m.rating" :max="5" size="small" :disabled="!m.queryId || m.fbDone" />
                  </span>
                </el-tooltip>
                <el-input
                  v-if="m.queryId && m.rating && !m.fbDone"
                  v-model="m.comment"
                  size="small"
                  class="fb-comment"
                  placeholder="补充评论（可选）"
                  maxlength="200"
                />
                <el-button
                  v-if="m.queryId && m.rating"
                  link
                  type="primary"
                  size="small"
                  :loading="m.fbLoading"
                  :disabled="m.fbDone"
                  @click="submitFeedback(m)"
                >
                  {{ m.fbDone ? '已反馈' : '提交反馈' }}
                </el-button>
              </template>
              <el-tag v-if="m.stopped" size="small" type="info" effect="plain">已中断</el-tag>
              <el-button v-if="m.content" link size="small" :icon="CopyDocument" @click="copyText(m.content)">
                复制
              </el-button>
              <span v-if="m.queryId" class="qid" :title="m.queryId">ID {{ m.queryId.slice(0, 8) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          class="composer-input"
          placeholder="输入问题，Enter 发送 / Shift+Enter 换行"
          @keydown.enter.exact.prevent="send"
        />
        <div class="composer-btns">
          <el-button v-if="sending && streamMode" type="danger" plain :icon="CircleClose" @click="stop">
            停止
          </el-button>
          <el-button type="primary" :icon="Promotion" :loading="sending && !streamMode" :disabled="sending" @click="send">
            发送
          </el-button>
        </div>
      </div>
    </div>
  </AppPage>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Delete, CopyDocument, Promotion, CircleClose, ChatDotRound } from '@element-plus/icons-vue'
import { qaApi } from '@/api'
import AppPage from '@/components/AppPage.vue'
import EmptyState from '@/components/EmptyState.vue'

// 建筑领域引导示例
const EXAMPLES = [
  'C30 混凝土保护层最小厚度是多少？',
  '楼面活荷载标准值如何取值？',
  '大体积混凝土施工温控措施有哪些？',
  '施工现场临时用电有哪些安全要求？',
]

const route = useRoute()
const router = useRouter()

const messages = ref([])
const input = ref('')
const topK = ref(5)
const useRerank = ref(true)
const streamMode = ref(true)
const sending = ref(false)
const chatRef = ref(null)
let controller = null // 当前流式请求的中断控制器

async function scrollBottom() {
  await nextTick()
  const el = chatRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function send() {
  if (sending.value) return
  const q = input.value.trim()
  if (!q) return
  input.value = ''
  sendQuestion(q)
}

async function sendQuestion(q) {
  const query = (q || '').trim()
  if (!query || sending.value) return
  // 多轮历史在追加本轮前采集（普通模式 chat 用）
  const history = messages.value
    .filter((m) => m.content && !m.degraded)
    .map((m) => ({ role: m.role, content: m.content }))
  messages.value.push({ role: 'user', content: query })
  const msg = reactive({
    role: 'assistant',
    content: '',
    sources: [],
    metadata: null,
    queryId: null,
    streaming: streamMode.value,
    degraded: false,
    degradedReason: '',
    stopped: false,
    rating: 0,
    comment: '',
    fbLoading: false,
    fbDone: false,
  })
  messages.value.push(msg)
  sending.value = true
  scrollBottom()
  try {
    if (streamMode.value) await runStream(query, msg)
    else await runChat(query, history, msg)
  } finally {
    msg.streaming = false
    sending.value = false
    controller = null
    scrollBottom()
  }
}

// ===== 流式：fetch + ReadableStream 解析 SSE =====

async function runStream(query, msg) {
  controller = new AbortController()
  let res
  try {
    res = await qaApi.askStream(
      { query, top_k: topK.value, use_rerank: useRerank.value },
      controller.signal,
    )
  } catch (e) {
    if (e.name === 'AbortError') return void (msg.stopped = true)
    msg.degraded = true
    msg.degradedReason = `网络错误：${e.message || '无法连接服务'}`
    return
  }
  if (!res.ok) {
    msg.degraded = true
    msg.degradedReason = await readErrorBody(res)
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) !== -1) {
        const block = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        if (handleSseBlock(block, msg)) {
          await reader.cancel()
          return
        }
      }
      scrollBottom()
    }
    buf += decoder.decode()
    if (buf.trim()) handleSseBlock(buf, msg)
  } catch (e) {
    if (e.name === 'AbortError') return void (msg.stopped = true)
    msg.degraded = true
    msg.degradedReason = `流式连接中断：${e.message || '请重试'}`
  }
}

// 解析单个 SSE 事件块；返回 true 表示流结束（[DONE]）
function handleSseBlock(block, msg) {
  let event = 'message'
  const dataLines = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  const data = dataLines.join('\n')
  if (!data) return false
  if (data === '[DONE]') return true
  let payload
  try {
    payload = JSON.parse(data)
  } catch {
    return false
  }
  if (event === 'meta') {
    msg.sources = payload.sources || []
    msg.metadata = payload.metadata || null
    msg.queryId = payload.query_id || null
  } else if (event === 'degraded') {
    msg.degraded = true
    msg.degradedReason = payload.reason || '问答依赖未就绪'
  } else if (payload.delta) {
    msg.content += payload.delta
  }
  return false
}

async function readErrorBody(res) {
  try {
    const body = await res.json()
    return body?.error?.message || body?.detail || `请求失败（HTTP ${res.status}）`
  } catch {
    return `请求失败（HTTP ${res.status}）`
  }
}

// ===== 普通：chat 多轮 =====

async function runChat(query, history, msg) {
  try {
    const res = await qaApi.chat({ query, history, top_k: topK.value, use_rerank: useRerank.value })
    msg.content = res.answer || '（无答案）'
    msg.sources = res.sources || []
    msg.metadata = res.metadata || null
    msg.queryId = res.query_id || null
  } catch (e) {
    msg.degraded = true
    msg.degradedReason =
      e?.apiError?.message || (e.httpStatus === 503 ? '依赖服务不可用，请稍后重试' : '请求失败，请稍后重试')
  }
}

function stop() {
  if (controller) controller.abort()
}

function clearChat() {
  stop()
  messages.value = []
}

// ===== 反馈 / 复制 =====

async function submitFeedback(m) {
  if (!m.queryId) return
  if (!m.rating) return void ElMessage.warning('请先评分')
  m.fbLoading = true
  try {
    await qaApi.feedback(m.queryId, { rating: m.rating, comment: m.comment || undefined })
    m.fbDone = true
    ElMessage.success('感谢您的反馈')
  } catch {
    /* 错误提示由拦截器统一处理 */
  } finally {
    m.fbLoading = false
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    ta.remove()
    ElMessage.success('已复制')
  }
}

function formatScore(score) {
  return Number(score ?? 0).toFixed(3)
}

// ===== URL ?query= 预填并自动发送（工作台跳转） =====

function consumeUrlQuery() {
  const raw = route.query.query
  const q = typeof raw === 'string' ? raw.trim() : ''
  if (!q) return
  router.replace({ query: {} })
  sendQuestion(q)
}

onMounted(consumeUrlQuery)
watch(
  () => route.query.query,
  () => {
    if (route.name === 'qa') consumeUrlQuery()
  },
)
</script>

<style scoped>
.qa-root {
  height: 100%;
}
.qa-root :deep(.app-page-body) {
  flex: 1;
  min-height: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  justify-content: flex-end;
}
.tool-label {
  font-size: 12px;
  color: var(--c-text-2);
  white-space: nowrap;
}
.topk {
  width: 120px;
  margin: 0 var(--sp-2);
}

.qa-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--r-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.chat {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--sp-5);
}

.msg {
  display: flex;
  margin-bottom: var(--sp-4);
}
.msg.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 78%;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-md);
  background: var(--c-surface-2);
  border: 1px solid var(--c-border);
}
.msg.user .bubble {
  background: var(--c-primary);
  border-color: var(--c-primary);
  color: #fff;
}
.content {
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}
.thinking {
  color: var(--c-text-3);
}
.cursor {
  display: inline-block;
  color: var(--c-primary);
  animation: blink 1s steps(1) infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
.degraded {
  margin-bottom: var(--sp-2);
}

.sources {
  margin-top: var(--sp-3);
}
.src-summary {
  font-size: 13px;
  color: var(--c-text-2);
}
.src-item {
  padding: var(--sp-2) 0;
  border-bottom: 1px dashed var(--c-border);
}
.src-item:last-child {
  border-bottom: none;
}
.src-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: 4px;
}
.src-doc {
  font-size: 13px;
  color: var(--c-text);
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.src-score {
  margin-left: auto;
  font-size: 12px;
  color: var(--c-text-3);
}
.src-text {
  font-size: 13px;
  color: var(--c-text-2);
  line-height: 1.6;
}

.foot {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  margin-top: var(--sp-3);
  padding-top: var(--sp-2);
  border-top: 1px dashed var(--c-border);
}
.rate-wrap {
  display: inline-flex;
  align-items: center;
}
.fb-comment {
  width: 200px;
}
.qid {
  margin-left: auto;
  font-size: 11px;
  color: var(--c-text-3);
}

.examples {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  justify-content: center;
  max-width: 560px;
}

.composer {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--c-border);
  background: var(--c-surface);
}
.composer-input {
  flex: 1;
}
.composer-btns {
  display: flex;
  gap: var(--sp-2);
  flex-shrink: 0;
}
</style>
