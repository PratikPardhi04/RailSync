import type { User, LoginResponse, MaintenanceRequest, MaintenanceRequestCreate, BlockPlan, Report, EngineerDashboard, OfficerDashboard, RejectRequest, AgentResult, HistoryEntry, AuditEntry, LiveState, WeatherInfo, ExecutionInfo } from '../types'

const BASE = `${import.meta.env.VITE_API_URL || ''}/api`

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('railsync_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${url}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const auth = {
  login: (email: string, password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
}

export const requests = {
  list: () => request<MaintenanceRequest[]>('/requests'),
  get: (id: number) => request<MaintenanceRequest & { plans: BlockPlan[] }>(`/requests/${id}`),
  create: (data: MaintenanceRequestCreate) =>
    request<{ id: number; request_id?: number; status: string; message?: string }>('/requests', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  analyze: (id: number) =>
    request<{ message: string }>(`/requests/${id}/analyze`, { method: 'POST' }),
  getAgents: (id: number, version?: number) =>
    request<AgentResult[]>(`/requests/${id}/agents${version ? `?plan_version=${version}` : ''}`),
  getReport: (id: number, version?: number) =>
    request<Report>(`/requests/${id}/report${version ? `?plan_version=${version}` : ''}`),
  getHistory: (id: number) =>
    request<{ plans: HistoryEntry[]; audit_trail: AuditEntry[] }>(`/requests/${id}/history`),
}

export const plans = {
  approve: (planId: number) =>
    request<{ block_id: string }>(`/plans/${planId}/approve`, { method: 'POST' }),
  reject: (planId: number, data: RejectRequest) =>
    request<{ message: string }>(`/plans/${planId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  replan: (planId: number) =>
    request<{ new_version: number }>(`/plans/${planId}/replan`, { method: 'POST' }),
}

export const dashboard = {
  engineer: () => request<EngineerDashboard>('/dashboard/engineer'),
  officer: () => request<OfficerDashboard>('/dashboard/officer'),
}

export const officer = {
  pending: () => request<{ pending: (MaintenanceRequest & { latest_plan?: BlockPlan })[]; stats: any }>('/officer/pending'),
}

export const live = {
  state: () => request<LiveState>('/live/state'),
  speed: (speed: number) => request<{ speed: number }>('/live/speed', { method: 'POST', body: JSON.stringify({ speed }) }),
  running: (running: boolean) => request<{ running: boolean }>('/live/running', { method: 'POST', body: JSON.stringify({ running }) }),
  jump: (minutes: number) => request<{ sim_time: string; sim_minutes: number }>('/live/jump', { method: 'POST', body: JSON.stringify({ minutes }) }),
  weather: () => request<WeatherInfo>('/live/weather'),
  dynamicReplan: (planId: number) => request<{ message: string; new_version: number; avoid_window: string }>(`/live/dynamic-replan/${planId}`, { method: 'POST' }),
}

export const execution = {
  get: (planId: number) => request<ExecutionInfo>(`/execution/plans/${planId}`),
  sanction: (planId: number) => request<ExecutionInfo>(`/execution/plans/${planId}/sanction`, { method: 'POST' }),
  checkin: (planId: number) => request<ExecutionInfo>(`/execution/plans/${planId}/checkin`, { method: 'POST' }),
  activate: (planId: number) => request<ExecutionInfo>(`/execution/plans/${planId}/activate`, { method: 'POST' }),
  release: (planId: number) => request<ExecutionInfo>(`/execution/plans/${planId}/release`, { method: 'POST' }),
  complete: (planId: number) => request<ExecutionInfo>(`/execution/plans/${planId}/complete`, { method: 'POST' }),
}
