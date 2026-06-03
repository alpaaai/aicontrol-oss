import axios from "axios";
import { getStoredAuth, clearAuth } from "@/store/auth";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8001",
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const auth = getStoredAuth();
  if (auth?.token) {
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    const url: string = error.config?.url ?? "";
    if (error.response?.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/magic-link") && !url.includes("/auth/set-password")) {
      clearAuth();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
