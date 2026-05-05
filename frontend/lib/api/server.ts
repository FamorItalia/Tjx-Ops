import { cookies } from "next/headers";

const DEFAULT_BACKEND = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export function getBackendBaseUrl() {
  return DEFAULT_BACKEND.replace(/\/$/, "");
}

export async function backendRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getBackendBaseUrl()}/api/v1${path.startsWith("/") ? path : `/${path}`}`;
  const token = cookies().get("ops_session_token")?.value;
  const response = await fetch(url, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });

  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText}`;
    try {
      const err = await response.json();
      throw new Error(err.detail || fallback);
    } catch {
      throw new Error(fallback);
    }
  }

  return response.json() as Promise<T>;
}
