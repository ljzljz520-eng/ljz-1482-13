import axios, { AxiosError } from "axios";
import { toast } from "react-hot-toast";

const api = axios.create({
  // @ts-ignore
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const raw = localStorage.getItem("wb_auth");
  if (raw) {
    try {
      const { token } = JSON.parse(raw);
      if (token) config.headers.Authorization = `Bearer ${token}`;
    } catch {
      /* ignore malformed storage */
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (error.response?.status === 401) {
      // Drop stale credentials and bounce to login except on the login page.
      if (!window.location.pathname.startsWith("/login")) {
        localStorage.removeItem("wb_auth");
        window.location.assign("/login");
      }
    } else {
      const message =
        error.response?.data?.detail ??
        error.message ??
        "网络请求失败，请稍后重试";
      if (!error.config?.headers?.get?.("X-Silent")) {
        toast.error(typeof message === "string" ? message : "请求失败");
      }
    }
    return Promise.reject(error);
  }
);

export default api;
