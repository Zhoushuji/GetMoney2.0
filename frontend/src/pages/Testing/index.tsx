import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';

import { apiClient } from '../../api/client';
import { useTaskStore } from '../../stores/useTaskStore';

type CheckState = {
  status: 'idle' | 'loading' | 'ok' | 'error';
  message: string;
  checkedAt?: string;
  durationMs?: number;
};

type TaskStatus = {
  id: string;
  status: string;
  progress: number;
  total: number;
  completed: number;
  confirmed_leads?: number;
  target_count?: number | null;
  stopped_early?: boolean;
  updated_at?: string;
};

type LeadSummary = {
  total: number;
  page: number;
  page_size: number;
};

function formatTime(value?: string) {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function formatDuration(durationMs?: number) {
  if (durationMs === undefined) return '-';
  if (durationMs < 1000) return `${durationMs}ms`;
  return `${(durationMs / 1000).toFixed(1)}s`;
}

function formatError(error: unknown) {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return '未知错误';
}

function StatusBadge({ tone, children }: { tone: 'neutral' | 'good' | 'warn' | 'bad'; children: string }) {
  return (
    <span className={`status-badge status-badge-${tone}`}>
      {children}
    </span>
  );
}

function CheckCard({
  title,
  endpoint,
  state,
  children,
}: {
  title: string;
  endpoint: string;
  state: CheckState;
  children: ReactNode;
}) {
  const tone = state.status === 'ok' ? 'good' : state.status === 'error' ? 'bad' : state.status === 'loading' ? 'warn' : 'neutral';

  return (
    <div className="surface-card surface-card-soft" style={{ display: 'grid', gap: 12 }}>
      <div className="page-heading">
        <strong>{title}</strong>
        <StatusBadge tone={tone}>{state.status.toUpperCase()}</StatusBadge>
      </div>
      <p className="muted-text" style={{ fontSize: 14 }}>{state.message}</p>
      <p className="muted-text" style={{ fontSize: 13 }}>Endpoint：{endpoint}</p>
      <div style={{ display: 'grid', gap: 6, color: '#6b7280', fontSize: 13 }}>
        <div>检查时间：{state.checkedAt ?? '-'}</div>
        <div>耗时：{formatDuration(state.durationMs)}</div>
      </div>
      {children}
    </div>
  );
}

export function TestingPage() {
  const taskId = useTaskStore((state) => state.taskId);
  const [healthCheck, setHealthCheck] = useState<CheckState>({ status: 'idle', message: '未检查' });
  const [taskCheck, setTaskCheck] = useState<CheckState>({ status: 'idle', message: '未检查' });
  const [leadCheck, setLeadCheck] = useState<CheckState>({ status: 'idle', message: '未检查' });
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [leadSummary, setLeadSummary] = useState<LeadSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastRunAt, setLastRunAt] = useState<string | null>(null);

  const checkHealth = async (): Promise<CheckState> => {
    const startedAt = Date.now();
    try {
      const response = await fetch('/health', { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json() as { status?: string; service?: string };
      return {
        status: 'ok',
        message: payload.service ? `${payload.service} 已响应` : '后端已响应',
        checkedAt: new Date().toLocaleString(),
        durationMs: Date.now() - startedAt,
      };
    } catch (error) {
      return {
        status: 'error',
        message: `健康检查失败：${formatError(error)}`,
        checkedAt: new Date().toLocaleString(),
        durationMs: Date.now() - startedAt,
      };
    }
  };

  const checkTask = async (nextTaskId: string): Promise<{ state: CheckState; data: TaskStatus | null }> => {
    const startedAt = Date.now();
    try {
      const response = await apiClient.get<TaskStatus>(`/tasks/${nextTaskId}/status`);
      return {
        state: {
          status: 'ok',
          message: `任务状态读取成功：${response.data.status}`,
          checkedAt: new Date().toLocaleString(),
          durationMs: Date.now() - startedAt,
        },
        data: response.data,
      };
    } catch (error) {
      return {
        state: {
          status: 'error',
          message: `任务状态读取失败：${formatError(error)}`,
          checkedAt: new Date().toLocaleString(),
          durationMs: Date.now() - startedAt,
        },
        data: null,
      };
    }
  };

  const checkLeads = async (nextTaskId: string): Promise<{ state: CheckState; data: LeadSummary | null }> => {
    const startedAt = Date.now();
    try {
      const response = await apiClient.get<LeadSummary>(`/leads?task_id=${nextTaskId}&page=1&page_size=1`);
      return {
        state: {
          status: 'ok',
          message: `线索摘要读取成功：${response.data.total} 条`,
          checkedAt: new Date().toLocaleString(),
          durationMs: Date.now() - startedAt,
        },
        data: response.data,
      };
    } catch (error) {
      return {
        state: {
          status: 'error',
          message: `线索摘要读取失败：${formatError(error)}`,
          checkedAt: new Date().toLocaleString(),
          durationMs: Date.now() - startedAt,
        },
        data: null,
      };
    }
  };

  const runChecks = async () => {
    setLoading(true);
    try {
      const healthPromise = checkHealth();
      const taskPromise = taskId ? checkTask(taskId) : Promise.resolve({
        state: { status: 'idle', message: '未绑定 taskId，跳过任务状态检查' } satisfies CheckState,
        data: null,
      });
      const leadPromise = taskId ? checkLeads(taskId) : Promise.resolve({
        state: { status: 'idle', message: '未绑定 taskId，跳过线索摘要检查' } satisfies CheckState,
        data: null,
      });

      const [nextHealth, nextTask, nextLeads] = await Promise.all([healthPromise, taskPromise, leadPromise]);

      setHealthCheck(nextHealth);
      setTaskCheck(nextTask.state);
      setLeadCheck(nextLeads.state);
      setTaskStatus(nextTask.data);
      setLeadSummary(nextLeads.data);
      setLastRunAt(new Date().toLocaleString());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void runChecks();
  }, [taskId]);

  const activeTask = taskStatus && ['pending', 'running'].includes(taskStatus.status);
  const hasTaskContext = Boolean(taskId);
  const smokeOk = healthCheck.status === 'ok' && (!hasTaskContext || (taskCheck.status === 'ok' && leadCheck.status === 'ok'));

  return (
    <div className="page-stack">
      <section className="panel panel-soft">
        <div className="page-heading">
          <div className="title-stack">
            <h2>Testing / Smoke Check</h2>
            <p>
                检查后端可达性，并拆分展示当前 task、线索摘要和健康探测结果。
            </p>
          </div>
          <button className="button" type="button" onClick={() => void runChecks()} disabled={loading}>
            {loading ? '检查中…' : '重新检查'}
          </button>
        </div>
        <div className="tag-list">
          <StatusBadge tone={hasTaskContext ? 'good' : 'neutral'}>
            {hasTaskContext ? '已绑定 task' : '未绑定 task'}
          </StatusBadge>
          <StatusBadge tone={smokeOk ? 'good' : 'warn'}>
            {smokeOk ? 'SMOKE PASS' : 'SMOKE CHECK'}
          </StatusBadge>
          <StatusBadge tone={lastRunAt ? 'neutral' : 'neutral'}>
            {lastRunAt ? `最后运行：${lastRunAt}` : '尚未运行'}
          </StatusBadge>
        </div>
      </section>

      <section className="stats-grid">
        <CheckCard title="后端健康" endpoint="/health" state={healthCheck}>
          <div style={{ display: 'grid', gap: 4, color: '#4b5563', fontSize: 14 }}>
            <div>检查结论：{healthCheck.status === 'ok' ? '通过' : healthCheck.status === 'error' ? '失败' : '待检查'}</div>
          </div>
        </CheckCard>

        <CheckCard title="当前任务" endpoint={taskId ? `/tasks/${taskId}/status` : '/tasks/{taskId}/status'} state={taskCheck}>
          <div style={{ display: 'grid', gap: 4, color: '#4b5563', fontSize: 14 }}>
            <div>任务 ID：{taskId ?? '未绑定'}</div>
            <div>任务状态：{taskStatus ? `${taskStatus.status} / ${taskStatus.progress}%` : '无可读状态'}</div>
            <div>更新时间：{formatTime(taskStatus?.updated_at)}</div>
          </div>
        </CheckCard>

        <CheckCard title="线索摘要" endpoint={taskId ? `/leads?task_id=${taskId}&page=1&page_size=1` : '/leads?task_id={taskId}&page=1&page_size=1'} state={leadCheck}>
          <div style={{ display: 'grid', gap: 4, color: '#4b5563', fontSize: 14 }}>
            <div>总数：{leadSummary ? leadSummary.total : '-'}</div>
            <div>分页：{leadSummary ? `page ${leadSummary.page} / size ${leadSummary.page_size}` : '-'}</div>
            <div>结果摘要：{leadSummary ? '已读取' : '无可读摘要'}</div>
          </div>
        </CheckCard>
      </section>

      <section className="panel panel-soft">
        <h3>Smoke Check Summary</h3>
        <div style={{ display: 'grid', gap: 10, color: '#374151' }}>
          <div>健康检查：{healthCheck.status === 'ok' ? '通过' : healthCheck.status === 'error' ? '失败' : '未完成'}</div>
          <div>任务绑定：{taskId ? '已连接到当前 task' : '未检测到当前 task'}</div>
          <div>任务状态：{taskCheck.status === 'ok' ? '通过' : taskCheck.status === 'error' ? '失败' : '跳过或未完成'}</div>
          <div>线索摘要：{leadCheck.status === 'ok' ? '通过' : leadCheck.status === 'error' ? '失败' : '跳过或未完成'}</div>
          <div>最后状态更新时间：{formatTime(taskStatus?.updated_at)}</div>
        </div>

        {taskStatus ? (
          <div style={{ marginTop: 16, display: 'grid', gap: 8, color: '#4b5563', fontSize: 14 }}>
            <div>任务状态：{taskStatus.status}</div>
            <div>进度：{taskStatus.progress}%</div>
            <div>已完成：{taskStatus.completed}</div>
            <div>确认线索：{taskStatus.confirmed_leads ?? 0}</div>
            <div>目标数量：{taskStatus.target_count ?? '-'}</div>
            <div>提前停止：{taskStatus.stopped_early ? '是' : '否'}</div>
          </div>
        ) : null}

        {leadSummary ? (
          <div style={{ marginTop: 16, display: 'grid', gap: 4, color: '#4b5563', fontSize: 14 }}>
            <div>线索总数：{leadSummary.total}</div>
            <div>分页信息：第 {leadSummary.page} 页 / 每页 {leadSummary.page_size} 条</div>
          </div>
        ) : null}

        <p className="muted-text" style={{ marginTop: 16, fontSize: 13 }}>
          这页只负责 smoke check 和诊断可视化；如果后端路由或代理层没接好，会在对应卡片里显示具体失败点。
        </p>
      </section>
    </div>
  );
}
