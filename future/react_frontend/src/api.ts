export const API_BASE = import.meta.env.VITE_API_BASE || "";

export interface ApiHeaders {
  [key: string]: string;
}

export function buildHeaders(demoMode: boolean, token?: string): ApiHeaders {
  const headers: ApiHeaders = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else if (demoMode) {
    headers["X-Demo-Mode"] = "true";
  }
  return headers;
}

export async function loadDemoDataset(sampleKey: string, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/demo/load/${sampleKey}`, {
    method: "POST",
    headers: buildHeaders(demoMode),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function uploadDatasetFile(file: File, demoMode = true) {
  const form = new FormData();
  form.append("file", file);
  const headers: ApiHeaders = demoMode ? { "X-Demo-Mode": "true" } : {};
  const res = await fetch(`${API_BASE}/api/v1/datasets/upload`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchProfile(datasetId: string, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/profile`, {
    headers: buildHeaders(demoMode),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchQuality(datasetId: string, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/quality`, {
    headers: buildHeaders(demoMode),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function confirmMappings(
  datasetId: string,
  grain: string,
  mappings: Array<{ source_column: string; canonical_concept: string }>,
  demoMode = true
) {
  const res = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/mappings/confirm`, {
    method: "POST",
    headers: buildHeaders(demoMode),
    body: JSON.stringify({ grain, mappings }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function queryDashboard(datasetId: string, filters: Record<string, any>, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/dashboards/${datasetId}/query`, {
    method: "POST",
    headers: buildHeaders(demoMode),
    body: JSON.stringify({ filters }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchInsights(datasetId: string, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/datasets/${datasetId}/insights`, {
    headers: buildHeaders(demoMode),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function askAI(datasetId: string, question: string, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/ai/conversations/${datasetId}/ask`, {
    method: "POST",
    headers: buildHeaders(demoMode),
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function runWhatIf(payload: Record<string, number>, demoMode = true) {
  const res = await fetch(`${API_BASE}/api/v1/scenarios/simulate`, {
    method: "POST",
    headers: buildHeaders(demoMode),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
