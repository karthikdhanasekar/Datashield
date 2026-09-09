/**
 * DataShield OSINT - API Client
 * Centralized Axios instance with auth, error handling, and refresh
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Request interceptor: attach token ────────────────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// ── Response interceptor: handle 401 / token refresh ────────────────────────
let isRefreshing = false
let failedQueue: Array<{ resolve: Function; reject: Function }> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error)
    else prom.resolve(token)
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) throw new Error('No refresh token')

        const { data } = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        })

        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)

        processQueue(null, data.access_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        if (typeof window !== 'undefined') {
          localStorage.clear()
          window.location.href = '/auth/login'
        }
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// ── API Functions ─────────────────────────────────────────────────────────────

// Auth
export const authApi = {
  register: (data: any) => api.post('/auth/register', data),
  login: (data: any) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  refreshToken: (token: string) => api.post('/auth/refresh', { refresh_token: token }),
  getMe: () => api.get('/auth/me'),
  setupMFA: () => api.post('/auth/mfa/setup'),
  verifyMFA: (code: string) => api.post('/auth/mfa/verify', { code }),
  disableMFA: (code: string) => api.post('/auth/mfa/disable', { code }),
  requestPasswordReset: (email: string) => api.post('/auth/password-reset/request', { email }),
  confirmPasswordReset: (data: any) => api.post('/auth/password-reset/confirm', data),
  verifyEmail: (token: string) => api.get(`/auth/verify-email?token=${token}`),
}

// Scans
export const scanApi = {
  create: (data: any) => api.post('/scans/', data),
  list: (params?: any) => api.get('/scans/', { params }),
  get: (id: string) => api.get(`/scans/${id}`),
  delete: (id: string) => api.delete(`/scans/${id}`),
  updateFinding: (id: string, data: any) => api.patch(`/scans/findings/${id}`, data),
  getExposureScore: () => api.get('/scans/dashboard/exposure-score'),
  search: (params: { q: string; severity?: string; finding_type?: string; page?: number; page_size?: number }) =>
    api.get('/scans/search', { params }),
  exportFindings: (params?: { fmt?: 'csv' | 'json'; severity?: string; include_false_positives?: boolean }) =>
    api.get('/scans/findings/export', { params, responseType: 'blob' }),
  // Fetch last N scans with finding counts for the analytics trend chart
  getHistory: (limit = 30) => api.get('/scans/', { params: { page_size: limit, page: 1 } }),
}

// Takedowns
export const takedownApi = {
  preview: (data: any) => api.post('/takedowns/preview', data),
  create: (data: any) => api.post('/takedowns/', data),
  list: (params?: any) => api.get('/takedowns/', { params }),
  updateStatus: (id: string, data: any) => api.patch(`/takedowns/${id}/status`, data),
}

// Monitors
export const monitorApi = {
  create: (data: any) => api.post('/monitors/', data),
  list: () => api.get('/monitors/'),
  delete: (id: string) => api.delete(`/monitors/${id}`),
}

// Complaints
export const complaintApi = {
  create: (data: any) => api.post('/complaints/', data),
}

// Notifications
export const notificationApi = {
  list: (params?: any) => api.get('/notifications/', { params }),
  markRead: (id: string) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
}

// AI
export const aiApi = {
  chat: (message: string, includeContext = true) =>
    api.post('/ai/chat', { message, include_context: includeContext }),
  analyze: (scanId?: string) =>
    api.post('/ai/analyze', { scan_id: scanId }),
}

// Admin
export const adminApi = {
  getUsers: (params?: any) => api.get('/admin/users', { params }),
  updateUserStatus: (id: string, status: string) =>
    api.patch(`/admin/users/${id}/status`, null, { params: { new_status: status } }),
  updateUserRole: (id: string, role: string) =>
    api.patch(`/admin/users/${id}/role`, null, { params: { new_role: role } }),
  getAnalytics: () => api.get('/admin/analytics/overview'),
  getExposureTrends: (days = 30) => api.get('/admin/analytics/exposure-trends', { params: { days } }),
  getAuditLogs: (params?: any) => api.get('/admin/audit-logs', { params }),
}

export default api
