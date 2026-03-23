import { useEffect, useMemo, useRef, useState } from 'react';

import { apiClient } from '../../api/client';
import { LeadTable, LeadRow } from '../../components/DataTable/LeadTable';
import { LeadSearchForm, LeadSearchPayload } from '../../components/SearchForm/LeadSearchForm';
import { TaskProgressCard } from '../../components/TaskProgress/TaskProgressCard';
import { useTaskStore } from '../../stores/useTaskStore';

type TaskStatus = {
  id: string;
  status: string;
  progress: number;
  total: number;
  completed: number;
  confirmed_leads: number;
  target_count: number | null;
  stopped_early: boolean;
  estimated_remaining_seconds?: number | null;
};

type LeadListResponse = {
  items: LeadRow[];
  total: number;
};

export function LeadDiscoveryPage() {
  const { taskId, setTaskId } = useTaskStore();
  const [view, setView] = useState<'form' | 'progress' | 'results'>('form');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollerRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollerRef.current !== null) {
      window.clearInterval(pollerRef.current);
      pollerRef.current = null;
    }
  };

  const closeStream = () => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
  };

  const loadResults = async (nextTaskId: string) => {
    const response = await apiClient.get<LeadListResponse>(`/leads?task_id=${nextTaskId}&page=1&page_size=50`);
    setRows(response.data.items);
    setTotalRows(response.data.total);
    setView('results');
  };

  const handleTaskUpdate = async (status: TaskStatus) => {
    setTaskStatus(status);
    if (status.status === 'failed') {
      stopPolling();
      closeStream();
      setIsSubmitting(false);
      window.alert('搜索任务失败，请稍后重试。');
      return;
    }
    if (status.status === 'completed' || status.status === 'stopped_early') {
      stopPolling();
      closeStream();
      setIsSubmitting(false);
      await loadResults(status.id);
    }
  };

  useEffect(() => {
    if (!taskId) {
      return undefined;
    }

    setView('progress');
    let fallbackStarted = false;

    const startPolling = () => {
      if (fallbackStarted) {
        return;
      }
      fallbackStarted = true;
      stopPolling();
      pollerRef.current = window.setInterval(async () => {
        const response = await apiClient.get<TaskStatus>(`/tasks/${taskId}/status`);
        await handleTaskUpdate(response.data);
      }, 3000);
    };

    try {
      const source = new EventSource(`/api/v1/tasks/${taskId}/stream`);
      eventSourceRef.current = source;
      source.onmessage = async (event) => {
        const status = JSON.parse(event.data) as TaskStatus;
        await handleTaskUpdate(status);
      };
      source.onerror = () => {
        closeStream();
        startPolling();
      };
    } catch {
      startPolling();
    }

    return () => {
      closeStream();
      stopPolling();
    };
  }, [taskId]);

  const exportResults = async () => {
    if (!taskId) {
      return;
    }
    const response = await apiClient.get(`/leads/export?task_id=${taskId}&format=xlsx&include_contacts=true`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'lead-results.xlsx';
    link.click();
    window.URL.revokeObjectURL(url);
  };

  const progressCard = useMemo(() => {
    if (!taskStatus || (view === 'results' && taskStatus.status !== 'running')) {
      return null;
    }
    return (
      <TaskProgressCard
        status={taskStatus.status}
        progress={taskStatus.progress}
        total={taskStatus.total}
        completed={taskStatus.completed}
        confirmedLeads={taskStatus.confirmed_leads}
        targetCount={taskStatus.target_count}
        estimatedRemainingSeconds={taskStatus.estimated_remaining_seconds}
        stoppedEarly={taskStatus.stopped_early}
      />
    );
  }, [taskStatus, view]);

  return (
    <>
      <section className="panel hero">
        <div>
          <h2>潜在客户发现引擎</h2>
          <p>围绕产品、国家与语言组合生成异步搜索任务，系统会在达到目标客户数量后自动停止继续过搜索。</p>
          <div className="tag-list">
            <span className="tag">FastAPI</span>
            <span className="tag">SSE + Polling Fallback</span>
            <span className="tag">PostgreSQL</span>
            <span className="tag">React</span>
          </div>
        </div>
        <div className="kpi-grid">
          <div className="kpi-card"><strong>全球</strong><p>大洲 / 国家 / 语言</p></div>
          <div className="kpi-card"><strong>1.5x</strong><p>过搜索系数</p></div>
          <div className="kpi-card"><strong>3s</strong><p>轮询降级周期</p></div>
        </div>
      </section>

      <LeadSearchForm
        isSubmitting={isSubmitting}
        onSubmit={async (payload: LeadSearchPayload) => {
          try {
            setIsSubmitting(true);
            setRows([]);
            setTotalRows(0);
            setTaskStatus(null);
            const response = await apiClient.post<{ task_id: string }>('/leads/search', payload);
            setTaskId(response.data.task_id);
          } catch (error) {
            setIsSubmitting(false);
            window.alert('搜索任务创建失败，请检查网络或稍后重试。');
          }
        }}
      />

      {progressCard}

      {view === 'results' ? (
        <>
          <section className="panel compact-panel result-toolbar">
            <strong>共找到 {totalRows} 家客户</strong>
            <button className="button secondary" type="button" onClick={exportResults}>导出 Excel</button>
          </section>
          <LeadTable rows={rows} />
        </>
      ) : null}
    </>
  );
}
