// .env.production sets NEXT_PUBLIC_API_URL to the custom domain
// (api.apexsdr.com) - this was previously ignored in favor of the hardcoded
// Render URL below, which still serves as the fallback for environments
// that don't set it (e.g. local dev without a .env.local).
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "https://apex-sdr-api.onrender.com/api/v1";

const CREDENTIAL_STORAGE_KEY = "apex_sdr_credential";

/**
 * The caller's bearer credential - a signed JWT or a provisioned API key,
 * both verified the same way by the backend's TenantAuthenticator. There is
 * no tenant-ID header: tenant identity is derived entirely from this
 * credential server-side.
 *
 * Resolution order: a build-time credential (NEXT_PUBLIC_API_CREDENTIAL, for
 * deployments that pin a single service credential) takes precedence, then a
 * credential stored in localStorage (set via setAuthCredential, e.g. by an
 * ops/admin flow that pastes a freshly issued token).
 */
export function getAuthCredential(): string | null {
  const buildTimeCredential = process.env.NEXT_PUBLIC_API_CREDENTIAL;
  if (buildTimeCredential) {
    return buildTimeCredential;
  }
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(CREDENTIAL_STORAGE_KEY);
}

export function setAuthCredential(credential: string) {
  window.localStorage.setItem(CREDENTIAL_STORAGE_KEY, credential);
}

export function clearAuthCredential() {
  window.localStorage.removeItem(CREDENTIAL_STORAGE_KEY);
}

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const credential = getAuthCredential();
  if (credential) {
    headers.set("Authorization", `Bearer ${credential}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const detail = errorData.detail;
    // FastAPI's own 422 validation responses shape `detail` as an array of
    // {loc, msg, type} objects rather than a string (unlike handler-raised
    // HTTPException(detail="...")). Left as-is, `new Error(anArray)` coerces
    // via Array.prototype.toString(), which stringifies each object to
    // "[object Object]" instead of a readable message.
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: { msg?: string }) => d?.msg).filter(Boolean).join(", ")
        : "";
    throw new Error(message || `API error: ${response.status}`);
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
