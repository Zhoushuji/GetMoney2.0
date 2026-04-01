import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api/v1',
});

apiClient.interceptors.request.use((config) => {
  if (typeof window === 'undefined') return config;
  const raw = window.localStorage.getItem('leadgen-auth');
  if (!raw) return config;
  try {
    const parsed = JSON.parse(raw) as { state?: { token?: string } };
    const token = parsed.state?.token;
    if (token) {
      config.headers = config.headers ?? {};
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    return config;
  }
  return config;
});
