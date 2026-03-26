/**
 * hamr-browser API 封装
 * baseURL: http://localhost:8000
 * 开发时通过 Vite proxy 转发，生产时直接请求
 */

const BASE_URL = import.meta.env.PROD ? 'http://localhost:8000' : ''

// ── 类型定义 ──────────────────────────────────────────────

export interface FlowSummary {
  id: string
  name: string
  description: string | null
  parameter_count: number
  has_auth: boolean
}

export interface FlowParameter {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean'
  required: boolean
  description: string | null
  example: unknown | null
  enum: string[] | null
  default: unknown | null
}

export interface FlowDetail {
  id: string
  name: string
  description: string | null
  parameters: FlowParameter[]
  has_auth: boolean
  auth?: unknown
  steps: unknown[]
  capture: unknown
}

export interface FlowSchema {
  flow_id: string
  name: string
  description: string | null
  has_auth: boolean
  parameters: FlowParameter[]
  example_request: Record<string, unknown>
}

export interface FlowRunResult {
  flow_id: string
  run_id: string | null
  status: 'success' | 'error'
  duration_ms: number
  data: unknown | null
  error_code: string | null
  error_message: string | null
}

export interface HistoryRecord {
  run_id: string
  flow_id: string
  params: Record<string, unknown>
  status: 'success' | 'error'
  duration_ms: number
  data: unknown | null
  error_code: string | null
  error_message: string | null
  created_at: string
}

export interface LogsResponse {
  total: number
  records: HistoryRecord[]
}

export interface BrowserStatus {
  ready: boolean
  headless: boolean
}

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}

// ── 通用请求工具 ──────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const err: ApiError = await res.json()
      if (typeof err.detail === 'string') {
        detail = err.detail
      } else if (Array.isArray(err.detail)) {
        detail = err.detail.map((d) => d.msg).join('; ')
      }
    } catch {
      // ignore parse error
    }
    throw new Error(detail)
  }
  // 204 No Content
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Flows API ────────────────────────────────────────────

/** 获取所有已注册流程列表 */
export function getFlows(): Promise<FlowSummary[]> {
  return request<FlowSummary[]>('/flows')
}

/** 获取流程详细信息（含 steps、capture 等完整配置） */
export function getFlow(flowId: string): Promise<FlowDetail> {
  return request<FlowDetail>(`/flows/${flowId}`)
}

/** 获取流程参数 Schema（含示例请求） */
export function getFlowSchema(flowId: string): Promise<FlowSchema> {
  return request<FlowSchema>(`/flows/${flowId}/schema`)
}

/** 执行流程 */
export function runFlow(flowId: string, params: Record<string, unknown>): Promise<FlowRunResult> {
  return request<FlowRunResult>(`/flows/${flowId}/run`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

/** 删除流程 */
export function deleteFlow(flowId: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/flows/${flowId}`, { method: 'DELETE' })
}

/** 上传 YAML 文件注册流程（multipart） */
export function uploadFlow(file: File): Promise<{ message: string; flow: FlowDetail }> {
  const form = new FormData()
  form.append('file', file)
  return request<{ message: string; flow: FlowDetail }>('/flows', {
    method: 'POST',
    headers: {},   // 让浏览器自动设置 multipart Content-Type
    body: form,
  })
}

// ── Browser API ──────────────────────────────────────────

/** 获取浏览器状态 */
export function getBrowserStatus(): Promise<BrowserStatus> {
  return request<BrowserStatus>('/browser/status')
}

/** 重启浏览器 */
export function restartBrowser(): Promise<{ message: string }> {
  return request<{ message: string }>('/browser/restart', { method: 'POST' })
}

/** 触发指定流程登录 */
export function triggerLogin(flowId: string): Promise<{ message: string; flow_id: string; final_url: string }> {
  return request(`/browser/${flowId}/login`, { method: 'POST' })
}

/** 检查流程登录状态 */
export function checkLoginStatus(flowId: string): Promise<{ flow_id: string; has_auth: boolean; logged_in: boolean }> {
  return request(`/browser/${flowId}/login/status`)
}

// ── Logs API ─────────────────────────────────────────────

/** 获取执行日志列表 */
export function getLogs(options?: {
  flow_id?: string
  status?: 'success' | 'error'
  limit?: number
}): Promise<LogsResponse> {
  const params = new URLSearchParams()
  if (options?.flow_id) params.set('flow_id', options.flow_id)
  if (options?.status) params.set('status', options.status)
  if (options?.limit != null) params.set('limit', String(options.limit))
  const qs = params.toString()
  return request<LogsResponse>(`/logs${qs ? `?${qs}` : ''}`)
}

/** 获取单条执行记录 */
export function getLog(runId: string): Promise<HistoryRecord> {
  return request<HistoryRecord>(`/logs/${runId}`)
}

// ── Health ───────────────────────────────────────────────

export function getHealth(): Promise<{ status: string; version: string; browser_ready: boolean }> {
  return request('/health')
}
