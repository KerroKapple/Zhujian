<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '220px'" class="aside">
      <div class="logo">
        <el-icon><Reading /></el-icon>
        <span v-show="!collapsed">企业 RAG 平台</span>
      </div>
      <el-menu :default-active="activeMenu" :collapse="collapsed" router class="menu">
        <el-menu-item index="/qa"><el-icon><ChatDotRound /></el-icon><span>智能问答</span></el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon><span>文档管理</span></el-menu-item>
        <el-menu-item index="/drawings"><el-icon><Picture /></el-icon><span>施工图处理</span></el-menu-item>
        <el-menu-item index="/graph"><el-icon><Share /></el-icon><span>知识图谱</span></el-menu-item>
        <el-menu-item index="/projects"><el-icon><Folder /></el-icon><span>项目管理</span></el-menu-item>
        <el-menu-item index="/agents"><el-icon><MagicStick /></el-icon><span>智能分析</span></el-menu-item>
        <el-menu-item index="/admin"><el-icon><Setting /></el-icon><span>系统管理</span></el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <el-icon class="collapse-btn" @click="collapsed = !collapsed">
          <Fold v-if="!collapsed" /><Expand v-else />
        </el-icon>
        <span class="title">{{ currentTitle }}</span>
      </el-header>
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const collapsed = ref(false)
const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta?.title || '企业 RAG 平台')
</script>

<style scoped>
.layout {
  height: 100%;
}
.aside {
  background: #001529;
  transition: width 0.2s;
  overflow: hidden;
}
.logo {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 18px;
  color: #fff;
  font-weight: 600;
  white-space: nowrap;
}
.menu {
  border-right: none;
  background: #001529;
}
.menu :deep(.el-menu-item) {
  color: #c0c4cc;
}
.menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #1677ff;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-bottom: 1px solid #eef0f3;
}
.collapse-btn {
  cursor: pointer;
  font-size: 18px;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.main {
  background: #f5f6f8;
  padding: 0;
}
</style>
