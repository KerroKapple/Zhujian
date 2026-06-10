import axios from 'axios'
import { ElMessage } from 'element-plus'

// 统一 axios 实例：基址来自环境变量，统一错误提示
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 120000,
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error?.response?.data?.detail || error?.response?.data?.message || error.message
    ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    return Promise.reject(error)
  },
)

export default request
