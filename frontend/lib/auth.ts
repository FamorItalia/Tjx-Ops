export const AUTH_COOKIE = "ops_session_token";

export function setAuthToken(token: string) {
  const maxAge = 60 * 60 * 24 * 30; // 30 days
  document.cookie = `${AUTH_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
}

export function clearAuthToken() {
  document.cookie = `${AUTH_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}
