import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/qa',
    children: [
      { path: 'qa', name: 'qa', component: () => import('@/views/QaView.vue'), meta: { title: '智能问答' } },
      { path: 'documents', name: 'documents', component: () => import('@/views/DocumentsView.vue'), meta: { title: '文档管理' } },
      { path: 'drawings', name: 'drawings', component: () => import('@/views/DrawingsView.vue'), meta: { title: '施工图处理' } },
      { path: 'graph', name: 'graph', component: () => import('@/views/GraphView.vue'), meta: { title: '知识图谱' } },
      { path: 'projects', name: 'projects', component: () => import('@/views/ProjectsView.vue'), meta: { title: '项目管理' } },
      { path: 'agents', name: 'agents', component: () => import('@/views/AgentsView.vue'), meta: { title: '智能分析' } },
      { path: 'admin', name: 'admin', component: () => import('@/views/AdminView.vue'), meta: { title: '系统管理' } },
    ],
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
