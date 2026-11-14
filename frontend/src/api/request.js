import axios from "axios";

const request = axios.create({
  baseURL: "/api",
  timeout: 300000, // 增加到 5 分钟，防止生图超时
});

// 请求拦截器：注入 Token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// 响应拦截器：处理鉴权失败
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      const isGuest = localStorage.getItem("isGuest") === "true";
      if (!isGuest && window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export const logout = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("isGuest");
  localStorage.removeItem("visionary_active_jobs");
  window.location.href = "/login";
};

export default request;
