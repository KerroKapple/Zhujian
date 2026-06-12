<template>
  <div class="layout">
    <!-- 深色侧栏 -->
    <aside class="aside" :class="{ collapsed }">
      <div class="brand">
        <svg class="brand-logo" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="#1f6feb" />
          <path d="M16 6l8 4v5c0 5-3.4 8.3-8 11-4.6-2.7-8-6-8-11V10l8-4z" fill="#dbe8ff" />
          <path d="M16 11l4 2v2.4c0 2.6-1.7 4.3-4 5.6-2.3-1.3-4-3-4-5.6V13l4-2z" fill="#16335c" />
        </svg>
        <span v-show="!collapsed" class="brand-name">筑见 <em>BuildView</em></span>
      </div>

      <el-scrollbar class="nav-scroll">
        <el-menu
          :default-active="route.path"
          :collapse="collapsed"
          :collapse-transition="false"
          router
          background-color="transparent"
          class="nav"
        >
          <template v-for="g in menuGroups" :key="g.name">
            <div v-show="!collapsed" class="nav-group-label">{{ g.name }}</div>
            <el-menu-item v-for="m in g.items" :key="m.path" :index="m.path">
              <el-icon><component :is="m.icon" /></el-icon>
              <template #title>{{ m.title }}</template>
            </el-menu-item>
          </template>
        </el-menu>
      </el-scrollbar>

      <!-- 底部：角色切换 + 收起 -->
      <div class="aside-foot">
        <el-select
          v-if="!collapsed"
          v-model="role"
          size="small"
          class="role-select"
          placeholder="角色"
        >
          <el-option v-for="r in ROLES" :key="r" :label="`角色 · ${r}`" :value="r" />
        </el-select>
        <button class="collapse-btn" :title="collapsed ? '展开' : '收起'" @click="toggle">
          <el-icon><Expand v-if="collapsed" /><Fold v-else /></el-icon>
        </button>
      </div>
    </aside>

    <!-- 右侧主体 -->
    <div class="body">
      <header class="topbar">
        <div class="topbar-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ currentGroup }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-right">
          <el-input
            v-model="search"
            class="global-search"
            placeholder="全局搜索"
            :prefix-icon="Search"
            clearable
          />
          <el-tag class="role-tag" effect="plain" round>{{ role }}</el-tag>
          <el-badge :is-dot="true" class="bell">
            <el-icon class="icon-btn"><Bell /></el-icon>
          </el-badge>
          <el-dropdown trigger="click">
            <span class="user">
              <el-avatar :size="28" class="user-avatar">筑</el-avatar>
              <span class="user-name">工程账户</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="User">个人中心</el-dropdown-item>
                <el-dropdown-item :icon="Setting">偏好设置</el-dropdown-item>
                <el-dropdown-item divided :icon="SwitchButton">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <keep-alive>
              <component :is="Component" />
            </keep-alive>
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  Search,
  Bell,
  ArrowDown,
  User,
  Setting,
  SwitchButton,
  Fold,
  Expand,
} from '@element-plus/icons-vue'
import { useUserStore, ROLES } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { role } = storeToRefs(userStore)
watch(role, (v) => userStore.setRole(v))

const search = ref('')
const collapsed = ref(false)
function toggle() {
  collapsed.value = !collapsed.value
}

// 窄屏自动收起
if (typeof window !== 'undefined') {
  const mq = window.matchMedia('(max-width: 992px)')
  collapsed.value = mq.matches
  mq.addEventListener('change', (e) => (collapsed.value = e.matches))
}

// 由路由 meta 的 group/icon 动态生成分组菜单
const GROUP_ORDER = ['知识', '项目', '系统']
const menuGroups = computed(() => {
  const children = router.options.routes[0].children || []
  const map = new Map()
  for (const r of children) {
    const g = r.meta?.group || '其他'
    if (!map.has(g)) map.set(g, [])
    map.get(g).push({
      path: '/' + r.path,
      title: r.meta?.title || r.name,
      icon: r.meta?.icon || 'Menu',
    })
  }
  return GROUP_ORDER.filter((g) => map.has(g)).map((g) => ({ name: g, items: map.get(g) }))
})

const currentTitle = computed(() => route.meta?.title || '筑见 BuildView')
const currentGroup = computed(() => route.meta?.group || '工作台')
</script>

<style scoped>
.layout {
  display: flex;
  height: 100%;
  background: var(--c-bg);
}

/* 深色侧栏 */
.aside {
  width: var(--aside-w);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--c-ink);
  background: linear-gradient(180deg, var(--c-ink) 0%, var(--c-ink-2) 100%);
  transition: width 0.2s ease;
  overflow: hidden;
}
.aside.collapsed {
  width: var(--aside-w-collapsed);
}
.brand {
  height: var(--header-h);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  flex-shrink: 0;
}
.brand-logo {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
}
.brand-name {
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  white-space: nowrap;
}
.brand-name em {
  font-style: normal;
  font-weight: 500;
  color: #9db8e6;
  font-size: 12px;
  margin-left: 2px;
}

.nav-scroll {
  flex: 1;
  min-height: 0;
}
.nav {
  border-right: none;
  padding: 6px 10px;
}
.nav-group-label {
  color: #6f86ad;
  font-size: 11px;
  letter-spacing: 1px;
  padding: 14px 12px 6px;
}
.nav :deep(.el-menu-item) {
  height: 42px;
  line-height: 42px;
  color: #c2d0e6;
  border-radius: var(--r-sm);
  margin: 2px 0;
}
.nav :deep(.el-menu-item:hover) {
  color: #fff;
  background: rgba(255, 255, 255, 0.06);
}
.nav :deep(.el-menu-item.is-active) {
  color: #fff;
  background: var(--c-primary);
  font-weight: 600;
}

.aside-foot {
  flex-shrink: 0;
  padding: 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  gap: 8px;
}
.role-select {
  flex: 1;
}
.role-select :deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.08);
  box-shadow: none;
}
.role-select :deep(.el-select__placeholder),
.role-select :deep(.el-select__selected-item) {
  color: #dbe6f7;
}
.collapse-btn {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border: none;
  border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.08);
  color: #c2d0e6;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.collapse-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
}

/* 主体 */
.body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: var(--header-h);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--c-surface);
  border-bottom: 1px solid var(--c-border);
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.global-search {
  width: 220px;
}
.role-tag {
  border-color: var(--c-border);
  color: var(--c-primary);
}
.bell {
  display: flex;
  align-items: center;
}
.icon-btn {
  font-size: 18px;
  color: var(--c-text-2);
  cursor: pointer;
}
.icon-btn:hover {
  color: var(--c-primary);
}
.user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}
.user-avatar {
  background: var(--c-primary);
  color: #fff;
  font-weight: 600;
}
.user-name {
  font-size: 14px;
  color: var(--c-text);
}

.content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 20px;
  background: var(--c-bg);
}

@media (max-width: 768px) {
  .global-search {
    display: none;
  }
  .user-name {
    display: none;
  }
}
</style>
