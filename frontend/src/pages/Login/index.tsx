import { FormEvent, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { useTaskStore } from '../../stores/useTaskStore';
import { AuthUser, useAuthStore } from '../../stores/useAuthStore';

type LoginResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export function LoginPage() {
  const navigate = useNavigate();
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const setSession = useAuthStore((state) => state.setSession);
  const setTaskId = useTaskStore((state) => state.setTaskId);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (token && user) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.post<LoginResponse>('/auth/login', { username, password });
      setSession(response.data.access_token, response.data.user);
      setTaskId(undefined);
      navigate('/', { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : '登录失败';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <section className="auth-card">
        <div className="title-stack">
          <h2>账号登录</h2>
          <p className="muted-text">使用管理员创建的用户名和密码登录系统。</p>
        </div>
        <form className="page-stack" onSubmit={handleSubmit}>
          <label className="field-group">
            <span>用户名</span>
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label className="field-group">
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error ? <p className="muted-text" style={{ color: '#b91c1c' }}>{error}</p> : null}
          <button className="button primary" type="submit" disabled={loading}>
            {loading ? '登录中…' : '登录'}
          </button>
        </form>
      </section>
    </div>
  );
}
