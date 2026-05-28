export interface AuthUser {
  email: string;
  role: "admin" | "analyst" | "auditor";
  token: string;
}

const SESSION_KEY = "ac_auth";

export function getStoredAuth(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function storeAuth(user: AuthUser) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
}

export function clearAuth() {
  sessionStorage.removeItem(SESSION_KEY);
}
