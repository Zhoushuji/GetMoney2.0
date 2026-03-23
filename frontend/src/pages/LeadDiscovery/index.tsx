import { useEffect, useMemo, useRef, useState } from 'react';

import { apiClient } from '../../api/client';
import { LeadSearchForm, LeadSearchPayload } from '../../components/SearchForm/LeadSearchForm';
import { LeadTable, LeadRow } from '../../components/DataTable/LeadTable';
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

type LeadListResponse = { items: LeadRow[]; total: number };

type ContactResponse = {
  contacts: Array<{
    person_name?: string;
    title?: string;
    linkedin_personal_url?: string;
    personal_email?: string;
    work_email?: string;
    phone?: string;
    whatsapp?: string;
    potential_contacts?: Record<string, string>;
  }>;
};

const CONTACT_CONCURRENCY = 5;

function StepCard({ step, title, status }: { step: string; title: string; status: 'pending' | 'active' | 'done' | 'locked' }) {
  const content = {
    pending: { icon: step, text: '待开始' },
    active: { icon: step, text: '进行中…' },
    done: { icon: '✓', text: '已完成' },
    locked: { icon: '🔒', text: '待开放' },
  }[status];

  return (
    <div className={`step-card step-${status}`}>
      <div className="step-circle">{content.icon}</div>
      <div>
        <strong>{title}</strong>
        <p>{content.text}</p>
      </div>
    </div>
  );
}

export function LeadDiscoveryPage() {
  const { taskId, setTaskId } = useTaskStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
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
    if (!taskId) return undefined;
    let fallbackStarted = false;

    const startPolling = () => {
      if (fallbackStarted) return;
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
      source.onmessage = async (event) => await handleTaskUpdate(JSON.parse(event.data));
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

  const mergeContact = (leadId: string, contact?: ContactResponse['contacts'][number]) => {
    setRows((current) => current.map((row) => row.id !== leadId ? row : {
      ...row,
      contact_status: contact ? 'done' : 'failed',
      contact_name: contact?.person_name,
      contact_title: contact?.title,
      linkedin_personal_url: contact?.linkedin_personal_url,
      personal_email: contact?.personal_email,
      work_email: contact?.work_email,
      phone: contact?.phone,
      whatsapp: contact?.whatsapp,
      potential_contacts: contact?.potential_contacts,
    }));
  };

  const runContactQueue = async (leadIds: string[]) => {
    const queue = [...leadIds];
    while (queue.length > 0) {
      const batch = queue.splice(0, CONTACT_CONCURRENCY);
      setRows((current) => current.map((row) => batch.includes(row.id) ? { ...row, contact_status: 'running' } : row));
      await apiClient.post('/contacts/enrich', { lead_ids: batch });
      await Promise.all(batch.map(async (leadId) => {
        const response = await apiClient.get<ContactResponse>(`/contacts?lead_id=${leadId}`);
        mergeContact(leadId, response.data.contacts[0]);
      }));
    }
  };

  const exportResults = async (format: 'xlsx' | 'csv') => {
    if (!taskId) return;
    const response = await apiClient.get(`/leads/export?task_id=${taskId}&format=${format}&include_contacts=true`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.download = `lead-results.${format}`;
    link.click();
    window.URL.revokeObjectURL(url);
  };

  const step1Status = isSubmitting ? 'active' : rows.length > 0 ? 'done' : 'pending';
  const step2Unlocked = rows.length > 0;
  const step2Status = !step2Unlocked ? 'pending' : rows.some((row) => row.contact_status === 'running') ? 'active' : rows.some((row) => row.contact_status === 'done') ? 'done' : 'pending';

  const progressCard = useMemo(() => {
    if (!taskStatus || taskStatus.status !== 'running') return null;
    return <TaskProgressCard status={taskStatus.status} progress={taskStatus.progress} total={taskStatus.total} completed={taskStatus.completed} confirmedLeads={taskStatus.confirmed_leads} targetCount={taskStatus.target_count} estimatedRemainingSeconds={taskStatus.estimated_remaining_seconds} stoppedEarly={taskStatus.stopped_early} />;
  }, [taskStatus]);

  return (
    <div className="flow-page">
      <section className="step-indicator panel">
        <StepCard step="1" title="潜在客户发现" status={step1Status as any} />
        <div className="step-line" />
        <StepCard step="2" title="核心联系人挖掘" status={step2Status as any} />
        <div className="step-line" />
        <StepCard step="3" title="触达拓展" status="locked" />
      </section>

      <section className="panel section-panel">
        <h2>▼ STEP 1 — 潜在客户发现</h2>
        <LeadSearchForm
          isSubmitting={isSubmitting}
          onSubmit={async (payload: LeadSearchPayload) => {
            try {
              setIsSubmitting(true);
              setRows([]);
              setTotalRows(0);
              setSelectedIds([]);
              setTaskStatus(null);
              const response = await apiClient.post<{ task_id: string }>('/leads/search', payload);
              setTaskId(response.data.task_id);
            } catch {
              setIsSubmitting(false);
              window.alert('搜索任务创建失败，请稍后重试。');
            }
          }}
        />
        {progressCard}
      </section>

      <section className={`panel section-panel ${step2Unlocked ? '' : 'panel-disabled'}`}>
        <h2>▼ STEP 2 — 核心联系人挖掘</h2>
        <div className="result-toolbar">
          <div className="toolbar-actions">
            <button className="button secondary" type="button" disabled={!step2Unlocked} onClick={() => setSelectedIds(rows.map((row) => row.id))}>☑ 全选</button>
            <button className="button" type="button" disabled={!step2Unlocked} onClick={() => runContactQueue(rows.filter((row) => row.contact_status === 'pending').map((row) => row.id))}>全部查找联系人</button>
            <button className="button" type="button" disabled={!step2Unlocked || selectedIds.length === 0} onClick={() => runContactQueue(selectedIds)}>批量查找联系人（已选 {selectedIds.length} 家）</button>
          </div>
          <div className="toolbar-actions">
            <button className="button secondary" type="button" disabled={!step2Unlocked} onClick={() => exportResults('xlsx')}>导出 Excel</button>
            <button className="button secondary" type="button" disabled={!step2Unlocked} onClick={() => exportResults('csv')}>导出 CSV</button>
          </div>
        </div>
      </section>

      <section className="panel section-panel">
        <h2>▼ 统一结果表格（STEP 1 + STEP 2 共用）</h2>
        <LeadTable
          rows={rows}
          selectedIds={selectedIds}
          step2Unlocked={step2Unlocked}
          onToggleRow={(leadId) => setSelectedIds((current) => current.includes(leadId) ? current.filter((id) => id !== leadId) : [...current, leadId])}
          onToggleAll={() => setSelectedIds((current) => current.length === rows.length ? [] : rows.map((row) => row.id))}
          onEnrichOne={(leadId) => runContactQueue([leadId])}
        />
        {rows.length > 0 ? <div className="results-summary">共找到 {totalRows} 家客户。</div> : null}
      </section>

      <section className="panel section-panel step3-card">
        <h2>▼ STEP 3 — 客户触达与商业拓展</h2>
        <div className="locked-card">
          <div className="locked-icon">🔒</div>
          <div>
            <h3>客户触达与商业拓展</h3>
            <p>即将开放，功能规划中</p>
            <div className="tag-list">
              <span className="tag">邮件序列</span>
              <span className="tag">LinkedIn InMail</span>
              <span className="tag">WhatsApp 触达</span>
              <span className="tag">触达追踪</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
