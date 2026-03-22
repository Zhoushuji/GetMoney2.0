import { useMutation, useQuery } from '@tanstack/react-query';

import { apiClient } from '../../api/client';
import { LeadTable, LeadRow } from '../../components/DataTable/LeadTable';
import { LeadSearchForm } from '../../components/SearchForm/LeadSearchForm';
import { TaskProgressCard } from '../../components/TaskProgress/TaskProgressCard';
import { useTaskStore } from '../../stores/useTaskStore';

export function LeadDiscoveryPage() {
  const { taskId, setTaskId } = useTaskStore();

  const searchMutation = useMutation({
    mutationFn: async (payload: { product_name: string; continents: string[]; countries: string[]; languages: string[]; channels: string[] }) => {
      const response = await apiClient.post('/leads/search', payload);
      return response.data as { task_id: string };
    },
    onSuccess: (data) => setTaskId(data.task_id),
  });

  const statusQuery = useQuery({
    queryKey: ['task-status', taskId],
    queryFn: async () => (await apiClient.get(`/tasks/${taskId}/status`)).data,
    enabled: Boolean(taskId),
    refetchInterval: 3000,
  });

  const leadsQuery = useQuery({
    queryKey: ['leads', taskId],
    queryFn: async () => (await apiClient.get(`/leads?task_id=${taskId}`)).data,
    enabled: Boolean(taskId),
  });

  const rows: LeadRow[] = (leadsQuery.data?.items ?? []).map((item: any) => ({ ...item }));

  return (
    <>
      <section className="panel hero">
        <div>
          <h2>潜在客户发现引擎</h2>
          <p>围绕产品、国家、语言与渠道组合生成异步搜索任务，统一汇总官网、Facebook、LinkedIn 与黄页信息。</p>
          <div className="tag-list">
            <span className="tag">FastAPI</span>
            <span className="tag">Celery + Redis</span>
            <span className="tag">PostgreSQL</span>
            <span className="tag">React Query</span>
          </div>
        </div>
        <div className="kpi-grid">
          <div className="kpi-card"><strong>5+</strong><p>搜索渠道</p></div>
          <div className="kpi-card"><strong>50+</strong><p>黄页国家可扩展</p></div>
          <div className="kpi-card"><strong>3s</strong><p>任务轮询周期</p></div>
        </div>
      </section>
      <LeadSearchForm onSubmit={async (payload) => searchMutation.mutateAsync(payload)} />
      <TaskProgressCard status={statusQuery.data?.status ?? 'idle'} progress={statusQuery.data?.progress ?? 0} total={statusQuery.data?.total ?? 0} completed={statusQuery.data?.completed ?? 0} />
      <LeadTable rows={rows} />
    </>
  );
}
