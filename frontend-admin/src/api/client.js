import axios from 'axios'
import { message } from 'antd'

const client = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code && data.code !== 200) {
      message.error(data.message || 'Request failed')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
      return Promise.reject(error)
    }
    if (error.response?.status === 403) {
      message.error('Permission denied: admin privileges required')
      return Promise.reject(error)
    }
    const msg = error.response?.data?.message || error.message || 'Network error'
    message.error(msg)
    return Promise.reject(error)
  }
)

export default client

export const authApi = {
  login: (data) => client.post('/auth/login', data),
  register: (data) => client.post('/auth/register', data),
  me: () => client.get('/auth/me'),
}

export const signatureApi = {
  list: (page = 1, pageSize = 20) => client.get('/signatures', { params: { page, page_size: pageSize } }),
  get: (id) => client.get(`/signatures/${id}`),
  upload: (formData) => client.post('/signatures', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  delete: (id) => client.delete(`/signatures/${id}`),
}

export const analysisApi = {
  list: (page = 1, pageSize = 20) => client.get('/analyses', { params: { page, page_size: pageSize } }),
  get: (id) => client.get(`/analyses/${id}`),
  create: (data) => client.post('/analyses', data),
  createWithFiles: (formData) => client.post('/analyses/upload', formData, { 
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000, // 5分钟超时，文件上传可能较慢
  }),
  getReport: (id) => client.get(`/analyses/${id}/report`),
  delete: (id) => client.delete(`/analyses/${id}`),
}

export const baselineApi = {
  list: (page = 1, pageSize = 20) => client.get('/baselines', { params: { page, page_size: pageSize } }),
  get: (id) => client.get(`/baselines/${id}`),
  create: (data) => client.post('/baselines', data),
  delete: (id) => client.delete(`/baselines/${id}`),
}

export const diffApi = {
  list: (page = 1, pageSize = 20) => client.get('/diffs', { params: { page, page_size: pageSize } }),
  get: (id) => client.get(`/diffs/${id}`),
  create: (data) => client.post('/diffs', data),
  delete: (id) => client.delete(`/diffs/${id}`),
}

export const dashboardApi = {
  stats: () => client.get('/dashboard/stats'),
}

export const userApi = {
  list: (page = 1, pageSize = 20) => client.get('/users', { params: { page, page_size: pageSize } }),
  create: (data) => client.post('/users', data),
  update: (id, data) => client.put(`/users/${id}`, data),
  delete: (id) => client.delete(`/users/${id}`),
}
