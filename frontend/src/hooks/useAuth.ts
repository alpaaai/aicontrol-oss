import { useState, useCallback } from "react";
import { getStoredAuth, storeAuth, clearAuth } from "@/store/auth";
import type { AuthUser } from "@/store/auth";

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(getStoredAuth);

  const login = useCallback((userData: AuthUser) => {
    storeAuth(userData);
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    setUser(null);
    window.location.href = "/login";
  }, []);

  return { user, login, logout, isAuthenticated: !!user };
}
