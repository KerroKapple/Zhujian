import axios from 'axios'
import { ElMessage } from 'element-plus'

// 统一 axios 实例：基址来自环境变量，按统一错误体提示
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 120000,
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 后端统一错误体：{success:false, error:{code,message,detail}}
    const body = error?.response?.data
    const message = body?.error?.message || body?.detail || body?.message || error.message || '请求失败'
    const status = error?.response?.status
    if (status === 503) {
      ElMessage.warning(`服务未就绪：${message}`)
    } else {
      ElMessage.error(typeof message === 'string' ? message : '请求失败')
    }
    // 透传结构化信息给调用方（views 可据此渲染降级态）
    error.apiError = body?.error || null
    error.httpStatus = status
    return Promise.reject(error)
  },
)

export default request
