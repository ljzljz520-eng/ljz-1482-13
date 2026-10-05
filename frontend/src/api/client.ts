import axios, { AxiosError } from "axios";
import toast from "react-hot-toast";

const api = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("cs_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError<{ message?: string }>) => {
    if (error.response?.status === 401) {
      if (localStorage.getItem("cs_token")) {
        localStorage.removeItem("cs_token");
        localStorage.removeItem("cs_user");
        toast.error("登录已过期，请重新登录");
        if (!location.pathname.startsWith("/login")) {
          location.href = "/login";
        }
      }
    }
    const message =
      error.response?.data?.message ??
      (error.code === "ECONNABORTED" ? "请求超时，请稍后重试" : "网络异常，请稍后重试");
    return Promise.reject(Object.assign(error, { friendlyMessage: message }));
  }
);

export default api;
