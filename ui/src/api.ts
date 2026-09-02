import type { RunResult, PolicyComparisonResult, InteractionDetail, Interaction, Finding, Metrics, DemoScenario, Detector, ModelInfo, PolicyInfo, AuditRecord } from './types';

const API_BASE = '/api';

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => fetchJSON<{ status: string }>('/health'),

  check: (payload: {
    request_text: string;
    response_text: string;
    context: Record<string, unknown>;
    policy: Record<string, unknown>;
    model?: string;
    provider?: string;
  }) => fetchJSON<any>('/check', { method: 'POST', body: JSON.stringify(payload) }),

  checkText: (payload: {
    request_text: string;
    response_text: string;
    model?: string;
    provider?: string;
  }) => fetchJSON<any>('/check/text', { method: 'POST', body: JSON.stringify(payload) }),

  listInteractions: (params?: {
    limit?: number;
    offset?: number;
    dimension?: string;
    decision?: string;
    model?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    if (params?.dimension) qs.set('dimension', params.dimension);
    if (params?.decision) qs.set('decision', params.decision);
    if (params?.model) qs.set('model', params.model);
    return fetchJSON<Interaction[]>(`/interactions?${qs}`);
  },

  getInteraction: (id: string) => fetchJSON<InteractionDetail>(`/interactions/${id}`),

  listFindings: (params?: {
    limit?: number;
    offset?: number;
    dimension?: string;
    state?: string;
    detector_id?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    if (params?.dimension) qs.set('dimension', params.dimension);
    if (params?.state) qs.set('state', params.state);
    if (params?.detector_id) qs.set('detector_id', params.detector_id);
    return fetchJSON<Finding[]>(`/findings?${qs}`);
  },

  listPolicies: () => fetchJSON<PolicyInfo[]>('/policies'),

  evaluatePolicy: (payload: { finding: any; policy: any }) =>
    fetchJSON<any>('/policies/evaluate', { method: 'POST', body: JSON.stringify(payload) }),

  listModels: () => fetchJSON<ModelInfo[]>('/models'),

  listDetectors: () => fetchJSON<Detector[]>('/detectors'),

  getMetrics: () => fetchJSON<Metrics>('/metrics'),

  listAudit: (params?: { limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    return fetchJSON<AuditRecord[]>(`/audit?${qs}`);
  },

  listDemoScenarios: () => fetchJSON<DemoScenario[]>('/demo/scenarios'),

  runDemo: (payload: { scenario: string; policy?: string; consequence?: string }) =>
    fetchJSON<RunResult>('/demo/run', { method: 'POST', body: JSON.stringify(payload) }),

  comparePolicy: (payload: { scenario: string; policies: string[]; consequence?: string }) =>
    fetchJSON<PolicyComparisonResult>('/demo/compare-policy', { method: 'POST', body: JSON.stringify(payload) }),

  liveStatus: () => fetchJSON<{ available: boolean; model: string; provider: string }>('/live/status'),

  liveRun: (payload: { prompt: string; model?: string }) =>
    fetchJSON<any>('/live/run', { method: 'POST', body: JSON.stringify(payload) }),

  resetSession: () => fetchJSON<{ status: string; message: string }>('/session/reset', { method: 'POST' }),
};
