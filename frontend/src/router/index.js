import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

// 路由路径保持不变；meta 增加分组/角色/标题供侧栏与权限使用
const routes = [
  {
    path: '/',
    component: MainLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '工作台', group: '项目', icon: 'Odometer', roles: ['全部', '项目', '造价', '安全', '技术'] },
      },
      {
        path: 'qa',
        name: 'qa',
        component: () => import('@/views/QaView.vue'),
        meta: { title: '智能问答', group: '知识', icon: 'ChatDotRound', roles: ['全部'] },
      },
      {
        path: 'documents',
        name: 'documents',
        component: () => import('@/views/DocumentsView.vue'),
        meta: { title: '文档管理', group: '知识', icon: 'Document', roles: ['全部'] },
      },
      {
        path: 'drawings',
        name: 'drawings',
        component: () => import('@/views/DrawingsView.vue'),
        meta: { title: '施工图处理', group: '知识', icon: 'Picture', roles: ['全部', '技术'] },
      },
      {
        path: 'graph',
        name: 'graph',
        component: () => import('@/views/GraphView.vue'),
        meta: { title: '知识图谱', group: '知识', icon: 'Share', roles: ['全部', '技术'] },
      },
      {
        path: 'projects',
        name: 'projects',
        component: () => import('@/views/ProjectsView.vue'),
        meta: { title: '项目管理', group: '项目', icon: 'Folder', roles: ['全部', '项目', '造价'] },
      },
      {
        path: 'agents',
        name: 'agents',
        component: () => import('@/views/AgentsView.vue'),
        meta: { title: '智能分析', group: '项目', icon: 'MagicStick', roles: ['全部', '项目', '造价', '安全'] },
      },
      {
        path: 'admin',
        name: 'admin',
        component: () => import('@/views/AdminView.vue'),
        meta: { title: '系统管理', group: '系统', icon: 'Setting', roles: ['全部'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const t = to.meta?.title
  document.title = t ? `${t} · 筑见 BuildView` : '筑见 BuildView'
})

export default router
