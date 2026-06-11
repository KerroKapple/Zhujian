<template>
  <div class="qa-wrap">
    <div class="chat" ref="chatRef">
      <el-empty v-if="!messages.length" description="向知识库提问，获取带引用来源的答案" />
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="bubble">
          <div class="content">{{ m.content }}</div>
          <div v-if="m.sources && m.sources.length" class="sources">
            <el-divider content-position="left">引用来源 ({{ m.sources.length }})</el-divider>
            <el-collapse>
              <el-collapse-item
                v-for="(s, si) in m.sources"
                :key="si"
                :title="`#${si + 1} ${s.doc_id || ''}  相关度 ${(s.score ?? 0).toFixed(3)}`"
              >
                <div class="src-text">{{ s.text }}</div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <div v-if="m.role === 'assistant' && m.queryId" class="feedback">
            <el-divider content-position="left">完善内容</el-divider>
            <div class="fb-row">
              <span class="fb-label">答案评分</span>
              <el-rate v-model="m.rating" :max="5" />
            </div>
            <el-input
              v-model="m.comment"
              type="textarea"
              :rows="2"
              resize="none"
              maxlength="500"
              placeholder="补充反馈（可选）"
              class="fb-comment"
            />
            <el-button
              size="small"
              type="primary"
              :loading="m.fbLoading"
              :disabled="!m.rating || m.fbDone"
              @click="submitFeedback(m)"
            >
              {{ m.fbDone ? '已提交' : '提交反馈' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="composer">
      <div class="opts">
        <span>召回数</span>
        <el-input-number v-model="topK" :min="1" :max="20" size="small" />
        <el-checkbox v-model="useRerank">重排序</el-checkbox>
      </div>
      <div class="input-row">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入你的问题，Enter 发送 / Shift+Enter 换行"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :loading="loading" @click="send">发送</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { qaApi } from '@/api'

const messages = ref([])
const input = ref('')
const topK = ref(5)
const useRerank = ref(true)
const loading = ref(false)
const chatRef = ref(null)

async function scrollBottom() {
  await nextTick()
  if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight
}

async function send() {
  const q = input.value.trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', content: q })
  input.value = ''
  loading.value = true
  await scrollBottom()
  try {
    const history = messages.value
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }))
    const res = await qaApi.chat({ query: q, history, top_k: topK.value, use_rerank: useRerank.value })
    messages.value.push({
      role: 'assistant',
      content: res.answer || '（无回答）',
      sources: res.sources || [],
      // 反馈需要 query_id；后端未返回时用本地标识兜底
      queryId: res.metadata?.query_id || res.query_id || `q_${Date.now()}`,
      rating: 0,
      comment: '',
      fbLoading: false,
      fbDone: false,
    })
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '请求失败，请稍后重试。' })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}

async function submitFeedback(m) {
  if (!m.rating) return ElMessage.warning('请先评分')
  m.fbLoading = true
  try {
    await qaApi.feedback(m.queryId, { rating: m.rating, comment: m.comment || undefined })
    m.fbDone = true
    ElMessage.success('感谢您的反馈')
  } catch (e) {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    m.fbLoading = false
  }
}
</script>

<style scoped>
.qa-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.chat {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.msg {
  display: flex;
  margin-bottom: 16px;
}
.msg.user {
  justify-content: flex-end;
}
.bubble {
  max-width: 76%;
  padding: 12px 16px;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.msg.user .bubble {
  background: #1677ff;
  color: #fff;
}
.content {
  white-space: pre-wrap;
  line-height: 1.7;
}
.sources {
  margin-top: 8px;
}
.src-text {
  color: #555;
  font-size: 13px;
  line-height: 1.6;
}
.feedback {
  margin-top: 8px;
}
.fb-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.fb-label {
  font-size: 13px;
  color: #666;
}
.fb-comment {
  margin-bottom: 8px;
}
.composer {
  border-top: 1px solid #eef0f3;
  background: #fff;
  padding: 12px 20px;
}
.opts {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}
.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
</style>
