import { useEffect, useState } from 'react';
import { NavLink, Outlet, useOutletContext } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { useTaskStore } from '../../stores/useTaskStore';

export type WorkspaceTaskSummary = {
  id: string;
  type?: string | null;
  status: string;
  progress: number;
  total: number;
  completed: number;
  confirmed_leads: number;
  target_count: number | null;
  stopped_early: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  params?: {
    product_name?: string;
    keywords?: string[];
    continents?: string[];
    countries?: string[];
    languages?: string[];
    mode?: 'live' | 'demo' | string;
  } | null;
  lead_count: number;
  decision_maker_done_count: number;
  general_contact_done_count: number;
  latest_contact_task?: {
    id: string;
    status: string;
    progress: number;
    mode?: string | null;
    updated_at?: string | null;
  } | null;
};

type TaskHistoryResponse = {
  items: WorkspaceTaskSummary[];
  total: number;
  limit: number;
  offset: number;
};

type WorkspaceContextValue = {
  taskHistory: WorkspaceTaskSummary[];
  historyLoading: boolean;
  historyError: string | null;
  refreshTaskHistory: (preferredTaskId?: string) => Promise<void>;
};

const navigationItems = [
  { to: '/', label: '潜在客户发现', end: true },
  { to: '/history', label: '任务记录' },
  { to: '/reviews', label: '审核记录' },
  { to: '/contacts', label: '核心联系人挖掘' },
  { to: '/outreach', label: '客户触达与拓展' },
  { to: '/testing', label: '功能测试' },
];

export function useWorkspaceContext() {
  return useOutletContext<WorkspaceContextValue>();
}

export function AppLayout() {
  const { taskId, setTaskId } = useTaskStore();
  const [taskHistory, setTaskHistory] = useState<WorkspaceTaskSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const refreshTaskHistory = async (preferredTaskId?: string) => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const response = await apiClient.get<TaskHistoryResponse>('/tasks', {
        params: { type: 'lead_search', limit: 20, offset: 0 },
      });
      const items = response.data.items ?? [];
      setTaskHistory(items);

      const nextTaskId = preferredTaskId ?? taskId;
      if (items.length === 0) {
        if (taskId) setTaskId(undefined);
        return;
      }

      if (nextTaskId && items.some((item) => item.id === nextTaskId)) {
        if (nextTaskId !== taskId) setTaskId(nextTaskId);
        return;
      }
      setTaskId(items[0].id);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : '任务记录读取失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    const persistStore = useTaskStore as typeof useTaskStore & {
      persist?: {
        hasHydrated?: () => boolean;
        onFinishHydration?: (callback: () => void) => () => void;
      };
    };

    const run = () => {
      void refreshTaskHistory();
    };

    if (persistStore.persist?.hasHydrated?.()) {
      run();
      return;
    }

    const unsubscribe = persistStore.persist?.onFinishHydration?.(run);
    return () => {
      unsubscribe?.();
    };
  }, []);

  return (
    <div className="single-page-shell">
      <header className="topbar topbar-simple">
        <div className="brand">
          <h1>LeadGen System</h1>
          <p>B2B 智能客户开发平台</p>
        </div>
        <nav className="topbar-nav" aria-label="Primary">
          {navigationItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="single-page-content">
        <Outlet context={{ taskHistory, historyLoading, historyError, refreshTaskHistory }} />
      </main>
    </div>
  );
}
