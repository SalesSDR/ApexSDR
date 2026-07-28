export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
export const TENANT_ID = "tenant_1";

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Tenant-ID", TENANT_ID);

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${response.status}`);
  }

  return response.json();
}

export async function bulkAction(prospectIds: string[], action: string) {
  return fetchApi("/prospects/bulk-action", {
    method: "POST",
    body: JSON.stringify({ prospect_ids: prospectIds, action }),
  });
}

export async function advanceProspect(prospectId: string, targetState?: string) {
  return fetchApi(`/prospects/${prospectId}/advance`, {
    method: "POST",
    body: JSON.stringify({ target_state: targetState }),
  });
}
