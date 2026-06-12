import request from './request'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

// ===== 智能问答 =====
export const qaApi = {
  chat: (data) => request.post('/qa/chat', data),
  ask: (data) => request.post('/qa/ask', data),
  // 反馈契约：POST /qa/feedback/{queryId}，rating/comment 为 query 参数
  feedback: (queryId, params) => request.post(`/qa/feedback/${queryId}`, null, { params }),
  // SSE 流式问答：返回 fetch Response，调用方读 body 流
  askStream: (data, signal) =>
    fetch(`${API_BASE}/qa/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      signal,
    }),
}

// ===== 文档管理（列表返回 Page: {items,total,page,page_size}） =====
export const documentApi = {
  list: (params) => request.get('/document/list', { params }),
  detail: (docId) => request.get(`/document/${docId}`),
  status: (docId) => request.get(`/document/${docId}/status`),
  remove: (docId) => request.delete(`/document/${docId}`),
  batchRemove: (docIds) => request.post('/document/delete/batch', { doc_ids: docIds }),
  upload: (formData, params) =>
    request.post('/document/upload', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

// ===== 施工图（列表返回 Page） =====
export const drawingApi = {
  list: (params) => request.get('/drawing/list', { params }),
  upload: (formData, params) =>
    request.post('/drawing/upload', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  status: (docId) => request.get(`/drawing/${docId}/status`),
  result: (docId) => request.get(`/drawing/${docId}/result`),
  entities: (docId, params) => request.get(`/drawing/${docId}/entities`, { params }),
  reprocess: (docId) => request.post(`/drawing/${docId}/reprocess`),
  remove: (docId) => request.delete(`/drawing/${docId}`),
}

// ===== 知识图谱 =====
export const graphApi = {
  statistics: () => request.get('/graph/statistics'),
  documentGraph: (docId) => request.get(`/graph/document/${docId}`),
  documentStatistics: (docId) => request.get(`/graph/document/${docId}/statistics`),
  visualization: (docId, params) => request.get(`/graph/visualization/${docId}`, { params }),
  components: (params) => request.get('/graph/components', { params }),
  materials: (params) => request.get('/graph/materials', { params }),
  specifications: (params) => request.get('/graph/specifications', { params }),
  relations: (params) => request.get('/graph/relations', { params }),
  connected: (nodeId, params) => request.get(`/graph/connected/${nodeId}`, { params }),
  search: (data) => request.post('/graph/search', data),
  health: () => request.get('/graph/health'),
  removeDocument: (docId) => request.delete(`/graph/document/${docId}`),
}

// ===== 项目管理（列表返回 Page） =====
export const projectApi = {
  list: (params) => request.get('/projects/', { params }),
  create: (data) => request.post('/projects/', data),
  detail: (id) => request.get(`/projects/${id}`),
  update: (id, data) => request.put(`/projects/${id}`, data),
  remove: (id) => request.delete(`/projects/${id}`),
  statistics: (id) => request.get(`/projects/${id}/statistics`),
  tasks: (id, params) => request.get(`/projects/${id}/tasks`, { params }),
  delayedTasks: (id) => request.get(`/projects/${id}/tasks/delayed`),
  criticalTasks: (id) => request.get(`/projects/${id}/tasks/critical`),
  costs: (id, params) => request.get(`/projects/${id}/costs`, { params }),
  costSummary: (id) => request.get(`/projects/${id}/costs/summary`),
  safety: (id, params) => request.get(`/projects/${id}/safety`, { params }),
  openDefects: (id) => request.get(`/projects/${id}/safety/open-defects`),
  safetyStatistics: (id) => request.get(`/projects/${id}/safety/statistics`),
}

// ===== 智能体分析 =====
export const agentApi = {
  weeklyReport: (data) => request.post('/agents/weekly-report', data),
  riskAnalysis: (data) => request.post('/agents/risk-analysis', data),
  costAnalysis: (data) => request.post('/agents/cost-analysis', data),
  progressAnalysis: (data) => request.post('/agents/progress-analysis', data),
  safetyAnalysis: (data) => request.post('/agents/safety-analysis', data),
  quickCost: (projectId) => request.get(`/agents/cost-analysis/${projectId}/quick-check`),
  quickProgress: (projectId) => request.get(`/agents/progress-analysis/${projectId}/quick-check`),
  quickSafety: (projectId) => request.get(`/agents/safety-analysis/${projectId}/quick-check`),
  quickRisk: (projectId) => request.get(`/agents/risk-analysis/${projectId}/quick-scan`),
  dashboard: (projectId) => request.get(`/agents/dashboard/${projectId}`),
  workflows: (params) => request.get('/agents/workflows', { params }),
}

// ===== 系统管理 =====
export const adminApi = {
  status: () => request.get('/admin/status'),
  health: () => request.get('/admin/health'),
  config: () => request.get('/admin/config'),
  indexStats: () => request.get('/admin/index/stats'),
  rebuildIndex: () => request.post('/admin/index/rebuild'),
  cacheStats: () => request.get('/admin/cache/stats'),
  clearCache: (params) => request.post('/admin/cache/clear', null, { params }),
  statistics: (params) => request.get('/admin/statistics', { params }),
}
