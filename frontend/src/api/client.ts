import axios from "axios";
import { getStoredAuth, clearAuth } from "@/store/auth";
import { API_BASE_URL } from "@/lib/apiBase";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const auth = getStoredAuth();
  if (auth?.token) {
    config.headers.Authorization = `Bearer ${auth.token}`;
  }
  return config;
});

const PUBLIC_PATHS = ["/login", "/setup", "/invite"];

apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    const url: string = error.config?.url ?? "";
    const onPublicPage = PUBLIC_PATHS.includes(window.location.pathname);
    if (
      error.response?.status === 401 &&
      !onPublicPage &&
      !url.includes("/auth/login") &&
      !url.includes("/auth/magic-link") &&
      !url.includes("/auth/set-password")
    ) {
      clearAuth();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
