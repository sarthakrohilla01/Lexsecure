import axios from 'axios';

const envApiUrl = (import.meta as any).env?.VITE_API_URL as string | undefined;

export const API_URL: string = envApiUrl || '/api';

const absolute = (path: string): string => {
  if (/^https?:\/\//i.test(path)) return path;
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  return `${origin}${path.startsWith('/') ? '' : '/'}${path}`;
};

export const WS_URL: string = absolute(API_URL.replace(/^http/i, 'ws') + '/ws');

export const HEALTH_URL: string = API_URL.replace(/\/api\/?$/, '') + '/health';

export const getAuthToken = (): string | null =>
  localStorage.getItem('lexsecure_token');

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  if (!config.headers?.Authorization) {
    const token = localStorage.getItem('lexsecure_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.includes('/login')) {
      localStorage.removeItem('lexsecure_token');
      localStorage.removeItem('lexsecure_user');
      localStorage.removeItem('lexsecure_mfa');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const errorDetail = (err: any, fallback = 'Request failed'): string => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const text = detail
      .map((item: any) => item?.msg)
      .filter(Boolean)
      .join(', ');
    if (text) return text;
  }
  if (err?.response?.data?.message) return String(err.response.data.message);
  if (err?.message) return err.message;
  return fallback;
};
