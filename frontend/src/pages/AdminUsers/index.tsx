import { FormEvent, useEffect, useState } from 'react';

import { apiClient } from '../../api/client';
import { AuthUser } from '../../stores/useAuthStore';

type UserListResponse = {
  items: AuthUser[];
  total: number;
};

type EditableUser = AuthUser & {
  nextRole: string;
  nextLimit: number;
  nextActive: boolean;
  password: string;
};

export function AdminUsersPage() {
  const [users, setUsers] = useState<EditableUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({
    username: '',
    password: '',
    role: 'user',
    daily_task_limit: 3,
  });

  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<UserListResponse>('/users');
      setUsers(
        response.data.items.map((item) => ({
          ...item,
          nextRole: item.role,
          nextLimit: item.daily_task_limit,
          nextActive: item.is_active,
          password: '',
        })),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '用户列表读取失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await apiClient.post('/users', createForm);
      setCreateForm({ username: '', password: '', role: 'user', daily_task_limit: 3 });
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建用户失败');
    } finally {
      setCreating(false);
    }
  };

  const saveUser = async (user: EditableUser) => {
    await apiClient.patch(`/users/${user.id}`, {
      role: user.nextRole,
      is_active: user.nextActive,
      daily_task_limit: user.nextLimit,
    });
    await loadUsers();
  };

  const resetPassword = async (user: EditableUser) => {
    if (!user.password.trim()) return;
    await apiClient.patch(`/users/${user.id}/password`, { password: user.password });
    await loadUsers();
  };

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="page-heading">
          <div className="title-stack">
            <h2>用户管理</h2>
            <p className="muted-text">创建账号，调整角色、启停状态和每日根任务额度。</p>
          </div>
          <button className="button secondary" type="button" onClick={() => void loadUsers()} disabled={loading}>
            {loading ? '刷新中…' : '刷新列表'}
          </button>
        </div>
      </section>

      <section className="panel">
        <form className="admin-form-grid" onSubmit={handleCreate}>
          <label className="field-group">
            <span>用户名</span>
            <input value={createForm.username} onChange={(event) => setCreateForm((prev) => ({ ...prev, username: event.target.value }))} />
          </label>
          <label className="field-group">
            <span>密码</span>
            <input type="password" value={createForm.password} onChange={(event) => setCreateForm((prev) => ({ ...prev, password: event.target.value }))} />
          </label>
          <label className="field-group">
            <span>角色</span>
            <select value={createForm.role} onChange={(event) => setCreateForm((prev) => ({ ...prev, role: event.target.value }))}>
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </label>
          <label className="field-group">
            <span>每日根任务额度</span>
            <input
              type="number"
              min={1}
              value={createForm.daily_task_limit}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, daily_task_limit: Number(event.target.value || 1) }))}
            />
          </label>
          <button className="button primary" type="submit" disabled={creating}>
            {creating ? '创建中…' : '创建用户'}
          </button>
        </form>
      </section>

      {error ? (
        <section className="panel notice-panel notice-danger">
          <p className="muted-text">{error}</p>
        </section>
      ) : null}

      <section className="panel">
        <div className="table-wrap">
          <table className="lead-table result-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>角色</th>
                <th>状态</th>
                <th>每日额度</th>
                <th>重置密码</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>
                    <select value={user.nextRole} onChange={(event) => setUsers((current) => current.map((item) => item.id === user.id ? { ...item, nextRole: event.target.value } : item))}>
                      <option value="user">普通用户</option>
                      <option value="admin">管理员</option>
                    </select>
                  </td>
                  <td>
                    <label className="inline-check">
                      <input type="checkbox" checked={user.nextActive} onChange={(event) => setUsers((current) => current.map((item) => item.id === user.id ? { ...item, nextActive: event.target.checked } : item))} />
                      <span>{user.nextActive ? '启用' : '停用'}</span>
                    </label>
                  </td>
                  <td>
                    <input
                      type="number"
                      min={1}
                      value={user.nextLimit}
                      onChange={(event) => setUsers((current) => current.map((item) => item.id === user.id ? { ...item, nextLimit: Number(event.target.value || 1) } : item))}
                    />
                  </td>
                  <td>
                    <div className="inline-actions">
                      <input
                        type="password"
                        value={user.password}
                        placeholder="新密码"
                        onChange={(event) => setUsers((current) => current.map((item) => item.id === user.id ? { ...item, password: event.target.value } : item))}
                      />
                      <button className="button secondary" type="button" onClick={() => void resetPassword(user)} disabled={!user.password.trim()}>
                        重置
                      </button>
                    </div>
                  </td>
                  <td>
                    <button className="button secondary" type="button" onClick={() => void saveUser(user)}>
                      保存
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty-state"><span className="muted-text">暂无用户。</span></td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
