import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { useTaskStore } from '../../stores/useTaskStore';
import { AuthUser } from '../../stores/useAuthStore';
import { formatTaskKeywordTitle } from '../../components/Layout/taskSummary';

type TaskItem = {
  id: string;
  owner_username?: string | null;
  status: string;
  confirmed_leads: number;
  decision_maker_done_count: number;
  general_contact_done_count: number;
  updated_at?: string | null;
  params?: {
    countries?: string[];
    mode?: string;
    product_name?: string;
    keywords?: string[];
  } | null;
};

type TaskHistoryResponse = {
  items: TaskItem[];
  total: number;
};

type UserListResponse = {
  items: AuthUser[];
  total: number;
};

function formatDate(value?: string | null) {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function AdminTasksPage() {
  const navigate = useNavigate();
  const setTaskId = useTaskStore((state) => state.setTaskId);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [createdFrom, setCreatedFrom] = useState('');
  const [createdTo, setCreatedTo] = useState('');

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [taskResponse, userResponse] = await Promise.all([
        apiClient.get<TaskHistoryResponse>('/tasks', {
          params: {
            type: 'lead_search',
            limit: 100,
            offset: 0,
            all_users: true,
            status: statusFilter || undefined,
            user_id: userFilter || undefined,
            owner_role: roleFilter || undefined,
            created_from: createdFrom || undefined,
            created_to: createdTo || undefined,
          },
        }),
        apiClient.get<UserListResponse>('/users'),
      ]);
      setTasks(taskResponse.data.items);
      setUsers(userResponse.data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '任务列表读取失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [statusFilter, userFilter, roleFilter, createdFrom, createdTo]);

  const deleteTask = async (taskId: string) => {
    await apiClient.delete(`/tasks/${taskId}`);
    await load();
  };

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="page-heading">
          <div className="title-stack">
            <h2>任务管理</h2>
            <p className="muted-text">管理员可查看全部根任务，按用户和状态筛选，并删除无效任务。</p>
          </div>
          <button className="button secondary" type="button" onClick={() => void load()} disabled={loading}>
            {loading ? '刷新中…' : '刷新列表'}
          </button>
        </div>
        <div className="admin-filter-row">
          <label className="field-group">
            <span>用户</span>
            <select value={userFilter} onChange={(event) => setUserFilter(event.target.value)}>
              <option value="">全部</option>
              {users.map((user) => <option key={user.id} value={user.id}>{user.username}</option>)}
            </select>
          </label>
          <label className="field-group">
            <span>状态</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">全部</option>
              {['pending', 'running', 'completed', 'failed', 'stopped_early'].map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
          <label className="field-group">
            <span>角色</span>
            <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
              <option value="">全部</option>
              <option value="admin">管理员</option>
              <option value="user">普通用户</option>
            </select>
          </label>
          <label className="field-group">
            <span>开始时间</span>
            <input type="datetime-local" value={createdFrom} onChange={(event) => setCreatedFrom(event.target.value)} />
          </label>
          <label className="field-group">
            <span>结束时间</span>
            <input type="datetime-local" value={createdTo} onChange={(event) => setCreatedTo(event.target.value)} />
          </label>
        </div>
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
                <th>任务</th>
                <th>所属用户</th>
                <th>状态</th>
                <th>线索</th>
                <th>关键人</th>
                <th>联系方式</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <div className="company-cell">
                      <strong>{formatTaskKeywordTitle(task.params, '未命名搜索任务')}</strong>
                      <small>{(task.params?.countries || []).join('、') || '未指定国家'} · {(task.params?.mode || 'live').toUpperCase()}</small>
                    </div>
                  </td>
                  <td>{task.owner_username || '-'}</td>
                  <td>{task.status}</td>
                  <td>{task.confirmed_leads}</td>
                  <td>{task.decision_maker_done_count}</td>
                  <td>{task.general_contact_done_count}</td>
                  <td>{formatDate(task.updated_at)}</td>
                  <td>
                    <div className="inline-actions">
                      <button
                        className="button secondary"
                        type="button"
                        onClick={() => {
                          setTaskId(task.id);
                          navigate('/');
                        }}
                      >
                        打开
                      </button>
                      <button className="button secondary danger" type="button" onClick={() => void deleteTask(task.id)}>
                        删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && tasks.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-state"><span className="muted-text">暂无任务。</span></td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
