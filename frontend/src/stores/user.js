/* 角色状态：全部/项目/造价/安全/技术，持久化到 localStorage */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const ROLES = ['全部', '项目', '造价', '安全', '技术']

const STORAGE_KEY = 'zhujian.role'

export const useUserStore = defineStore('user', () => {
  const role = ref(localStorage.getItem(STORAGE_KEY) || '全部')

  function setRole(next) {
    if (!ROLES.includes(next)) return
    role.value = next
    localStorage.setItem(STORAGE_KEY, next)
  }

  return { role, setRole }
})
