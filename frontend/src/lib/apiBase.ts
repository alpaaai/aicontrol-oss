declare global {
  interface Window {
    __AICONTROL_CONFIG__?: { apiUrl?: string };
  }
}

/**
 * Base URL the browser uses to reach the API. Resolution order:
 *   1. /config.js, written at container start from AICONTROL_API_URL
 *   2. VITE_API_URL, baked in at build time
 *   3. http://localhost:8001
 */
export const API_BASE_URL: string =
  window.__AICONTROL_CONFIG__?.apiUrl ||
  import.meta.env.VITE_API_URL ||
  "http://localhost:8001";
