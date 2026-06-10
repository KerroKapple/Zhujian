import request from './request'

// ===== 智能问答 =====
export const qaApi = {
  ask: (data) => request.post('/qa/ask', data),
  chat: (data) => request.post('/qa/chat', data),
  feedback: (queryId, params) => request.get(`/qa/feedback/${queryId}`, { params }),
}

// ===== 文档管理 =====
export const documentApi = {
  list: (params) => request.get('/document/list', { params }),
  detail: (docId) => request.get(`/document/${docId}`),
  status: (docId) => request.get(`/document/${docId}/status`),
  remove: (docId) => request.delete(`/document/${docId}`),
  upload: (formData, params) =>
    request.post('/document/upload', formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

// ===== 施工图 =====
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
  remove: (docId) => request.delete(`/drawing/${docId}`),
}

// ===== 知识图谱 =====
export const graphApi = {
  statistics: () => request.get('/graph/statistics'),
  documentGraph: (docId) => request.get(`/graph/document/${docId}`),
  visualization: (docId, params) => request.get(`/graph/visualization/${docId}`, { params }),
  components: (params) => request.get('/graph/components', { params }),
  search: (data) => request.post('/graph/search', data),
  health: () => request.get('/graph/health'),
}

// ===== 项目管理 =====
export const projectApi = {
  list: (params) => request.get('/projects/', { params }),
  create: (data) => request.post('/projects/', data),
  detail: (id) => request.get(`/projects/${id}`),
  update: (id, data) => request.put(`/projects/${id}`, data),
  remove: (id) => request.delete(`/projects/${id}`),
  statistics: (id) => request.get(`/projects/${id}/statistics`),
}

// ===== 智能体分析 =====
export const agentApi = {
  weeklyReport: (data) => request.post('/agents/weekly-report', data),
  riskAnalysis: (data) => request.post('/agents/risk-analysis', data),
  costAnalysis: (data) => request.post('/agents/cost-analysis', data),
  progressAnalysis: (data) => request.post('/agents/progress-analysis', data),
  safetyAnalysis: (data) => request.post('/agents/safety-analysis', data),
  dashboard: (projectId) => request.get(`/agents/dashboard/${projectId}`),
  workflows: (params) => request.get('/agents/workflows', { params }),
}

// ===== 系统管理 =====
export const adminApi = {
  status: () => request.get('/admin/status'),
  health: () => request.get('/admin/health'),
  indexStats: () => request.get('/admin/index/stats'),
  rebuildIndex: () => request.post('/admin/index/rebuild'),
  cacheStats: () => request.get('/admin/cache/stats'),
  clearCache: (params) => request.post('/admin/cache/clear', null, { params }),
  statistics: (params) => request.get('/admin/statistics', { params }),
}
