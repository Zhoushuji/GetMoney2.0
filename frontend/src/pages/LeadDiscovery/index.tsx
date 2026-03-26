import { useEffect, useMemo, useRef, useState } from 'react';
import { AxiosError } from 'axios';
import { Link } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { useWorkspaceContext } from '../../components/Layout/AppLayout';
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
  estimated_total_seconds?: number | null;
  estimated_remaining_seconds?: number | null;
  phase?: string | null;
};

type LeadListResponse = { items: LeadRow[]; total: number; page: number; page_size: number };

type ContactResponse = {
  contacts: Array<{
    person_name?: string;
    title?: string;
    linkedin_personal_url?: string;
    personal_email?: string;
    work_email?: string;
    phone?: string;
    whatsapp?: string;
    potential_contacts?: { items?: string[] };
  }>;
};

type ContactStatusResponse = {
  lead_id: string;
  decision_maker_status: 'pending' | 'running' | 'done' | 'no_data' | 'timeout' | 'failed' | string;
  general_contact_status: 'pending' | 'running' | 'done' | 'no_data' | 'timeout' | 'failed' | string;
  contacts: ContactResponse['contacts'];
  potential_contacts?: { items?: string[]; phone?: string; whatsapp?: string; general_emails?: string[] };
  error?: string | null;
  error_details?: Record<string, unknown> | null;
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

function normalizeSearchMode(value?: string | null): 'live' | 'demo' | undefined {
  if (value === 'live' || value === 'demo') return value;
  return undefined;
}

export function LeadDiscoveryPage() {
  const { taskId, setTaskId } = useTaskStore();
  const { taskHistory, historyLoading, historyError, refreshTaskHistory } = useWorkspaceContext();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [totalRows, setTotalRows] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const eventSourceRef = useRef<EventSource | null>(null);
  const pollerRef = useRef<number | null>(null);
  const activeTaskIdRef = useRef<string | null>(taskId ?? null);

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

  const formatError = (error: unknown, fallback: string) => {
    if (error instanceof AxiosError) {
      const detail = error.response?.data?.detail;
      if (typeof detail === 'string' && detail.trim()) return detail;
      if (Array.isArray(detail) && detail.length > 0) {
        return detail.map((item) => (typeof item === 'string' ? item : item?.msg)).filter(Boolean).join('；') || fallback;
      }
      return error.message || fallback;
    }
    if (error instanceof Error) return error.message || fallback;
    return fallback;
  };

  const loadResults = async (nextTaskId: string, nextPage = page, nextPageSize = pageSize) => {
    const response = await apiClient.get<LeadListResponse>('/leads', {
      params: { task_id: nextTaskId, page: nextPage, page_size: nextPageSize },
    });
    if (activeTaskIdRef.current !== nextTaskId) return;
    setRows(response.data.items);
    setTotalRows(response.data.total);
    setPage(response.data.page);
    setPageSize(response.data.page_size);
  };

  const handleTaskUpdate = async (status: TaskStatus, expectedTaskId = activeTaskIdRef.current) => {
    if (!expectedTaskId || activeTaskIdRef.current !== expectedTaskId) return;
    setTaskStatus(status);
    setTaskError(null);
    if (status.status === 'failed') {
      stopPolling();
      closeStream();
      setIsSubmitting(false);
      setTaskError('搜索任务失败，请稍后重试，或切换到演示模式验证流程。');
      void refreshTaskHistory(expectedTaskId);
      return;
    }
    if (status.status === 'completed' || status.status === 'stopped_early') {
      stopPolling();
      closeStream();
      setIsSubmitting(false);
      void refreshTaskHistory(expectedTaskId);
    }
  };

  useEffect(() => {
    activeTaskIdRef.current = taskId ?? null;
    closeStream();
    stopPolling();
    setTaskError(null);
    setTaskStatus(null);
    setRows([]);
    setTotalRows(0);
    setSelectedIds([]);
    setPage(1);
    if (!taskId) return undefined;
    let fallbackStarted = false;
    const startPolling = () => {
      if (fallbackStarted) return;
      fallbackStarted = true;
      stopPolling();
      pollerRef.current = window.setInterval(async () => {
        try {
          const response = await apiClient.get<TaskStatus>(`/tasks/${taskId}/status`);
          await handleTaskUpdate(response.data, taskId);
        } catch (error) {
          if (activeTaskIdRef.current === taskId) {
            setTaskError(formatError(error, '任务状态读取失败，请手动刷新页面重试。'));
          }
        }
      }, 3000);
    };
    try {
      const source = new EventSource(`/api/v1/tasks/${taskId}/stream`);
      eventSourceRef.current = source;
      source.onmessage = async (event) => {
        try {
          await handleTaskUpdate(JSON.parse(event.data), taskId);
        } catch (error) {
          if (activeTaskIdRef.current === taskId) {
            setTaskError(formatError(error, '任务状态解析失败，请刷新后重试。'));
          }
        }
      };
      source.onerror = () => {
        closeStream();
        startPolling();
      };
    } catch {
      startPolling();
    }
    void (async () => {
      try {
        const response = await apiClient.get<TaskStatus>(`/tasks/${taskId}/status`);
        await handleTaskUpdate(response.data, taskId);
      } catch (error) {
        if (activeTaskIdRef.current === taskId) {
          setTaskError(formatError(error, '任务状态读取失败，请稍后重试。'));
        }
      }
    })();
    return () => {
      closeStream();
      stopPolling();
    };
  }, [taskId]);

  useEffect(() => {
    if (!taskId || !taskStatus || !['completed', 'stopped_early'].includes(taskStatus.status)) return;
    void loadResults(taskId, page, pageSize);
  }, [taskId, taskStatus, page, pageSize]);

  const mergeContact = (leadId: string, contact?: ContactResponse['contacts'][number]) => {
    setRows((current) => current.map((row) => row.id !== leadId ? row : {
      ...row,
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

  const triggerContactEnrich = async (leadId: string, mode: 'decision_maker' | 'general_contact' | 'all') => {
    setRows((current) => current.map((row) => row.id === leadId ? {
      ...row,
      decision_maker_status: mode === 'general_contact' ? row.decision_maker_status : 'running',
      general_contact_status: mode === 'decision_maker' ? row.general_contact_status : 'running',
    } : row));
    try {
      await apiClient.post('/contacts/enrich', { lead_ids: [leadId], mode });

      const startedAt = Date.now();
      while (Date.now() - startedAt < 150_000) {
        await new Promise((resolve) => setTimeout(resolve, 3000));
        const statusResponse = await apiClient.get<ContactStatusResponse>(`/contacts/status/${leadId}`);
        const decisionStatus = statusResponse.data.decision_maker_status;
        const generalStatus = statusResponse.data.general_contact_status;
        setRows((current) => current.map((row) => row.id === leadId ? {
          ...row,
          decision_maker_status: decisionStatus,
          general_contact_status: generalStatus,
          contact_status: decisionStatus === 'done' || generalStatus === 'done' ? 'done' : row.contact_status,
          contact_name: statusResponse.data.contacts?.[0]?.person_name,
          contact_title: statusResponse.data.contacts?.[0]?.title,
          linkedin_personal_url: statusResponse.data.contacts?.[0]?.linkedin_personal_url,
          personal_email: statusResponse.data.contacts?.[0]?.personal_email,
          work_email: statusResponse.data.contacts?.[0]?.work_email,
          phone: statusResponse.data.potential_contacts?.phone,
          whatsapp: statusResponse.data.potential_contacts?.whatsapp,
          general_emails: statusResponse.data.potential_contacts?.general_emails,
          potential_contacts: statusResponse.data.potential_contacts?.items ? { items: statusResponse.data.potential_contacts.items } : row.potential_contacts,
        } : row));
        const decisionDone = ['done', 'no_data', 'timeout', 'failed'].includes(decisionStatus);
        const generalDone = ['done', 'no_data', 'timeout', 'failed'].includes(generalStatus);
        const completed = mode === 'decision_maker' ? decisionDone : mode === 'general_contact' ? generalDone : (decisionDone && generalDone);
        if (completed) return;
      }
      setRows((current) => current.map((row) => row.id === leadId ? { ...row, decision_maker_status: 'timeout', general_contact_status: 'timeout' } : row));
      setTaskError('联系人挖掘超时，请稍后重试。');
    } catch (error) {
      setRows((current) => current.map((row) => row.id === leadId ? {
        ...row,
        decision_maker_status: 'failed',
        general_contact_status: 'failed',
      } : row));
      setTaskError(formatError(error, '联系人挖掘失败，请稍后重试。'));
    }
  };

  const runContactQueue = async (leadIds: string[], mode: 'decision_maker' | 'general_contact' | 'all') => {
    const queue = [...leadIds];
    while (queue.length > 0) {
      const batch = queue.splice(0, CONTACT_CONCURRENCY);
      await Promise.all(batch.map((leadId) => triggerContactEnrich(leadId, mode)));
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
  const step2Status = !step2Unlocked ? 'pending' : rows.some((row) => row.decision_maker_status === 'running' || row.general_contact_status === 'running') ? 'active' : rows.some((row) => row.decision_maker_status === 'done' || row.general_contact_status === 'done') ? 'done' : 'pending';
  const activeTaskSummary = useMemo(() => taskHistory.find((item) => item.id === taskId) ?? null, [taskHistory, taskId]);
  const formInitialValues = useMemo(() => {
    if (!activeTaskSummary?.params) return null;
    const { mode: rawMode, ...taskParams } = activeTaskSummary.params;
    const mode = normalizeSearchMode(rawMode);
    return {
      ...taskParams,
      target_count: activeTaskSummary.target_count ?? null,
      ...(mode ? { mode } : {}),
    } satisfies Partial<LeadSearchPayload>;
  }, [activeTaskSummary]);
  const strictCountryShortfall = useMemo(() => {
    const targetCountries = (activeTaskSummary?.params?.countries as string[] | undefined) ?? [];
    if (!taskStatus || targetCountries.length === 0) return null;
    if (!['completed', 'stopped_early'].includes(taskStatus.status)) return null;
    if (taskStatus.target_count == null || taskStatus.confirmed_leads >= taskStatus.target_count) return null;
    return `严格国家过滤后仅确认 ${taskStatus.confirmed_leads} 家企业；无法证明属于 ${targetCountries.join('、')} 的候选已被自动剔除。`;
  }, [activeTaskSummary, taskStatus]);

  const progressCard = useMemo(() => {
    if (!taskStatus || taskStatus.status !== 'running') return null;
    return <TaskProgressCard status={taskStatus.status} progress={taskStatus.progress} total={taskStatus.total} completed={taskStatus.completed} confirmedLeads={taskStatus.confirmed_leads} targetCount={taskStatus.target_count} phase={taskStatus.phase} estimatedTotalSeconds={taskStatus.estimated_total_seconds} estimatedRemainingSeconds={taskStatus.estimated_remaining_seconds} stoppedEarly={taskStatus.stopped_early} />;
  }, [taskStatus]);

  return (
    <div className="flow-page">
      {taskError ? (
        <section className="panel section-panel" style={{ borderColor: '#f59e0b', background: '#fffbeb' }}>
          <strong>任务提示</strong>
          <p className="muted-text" style={{ margin: '8px 0 0' }}>{taskError}</p>
        </section>
      ) : null}
      {strictCountryShortfall ? (
        <section className="panel section-panel" style={{ borderColor: '#93c5fd', background: '#eff6ff' }}>
          <strong>国家过滤提示</strong>
          <p className="muted-text" style={{ margin: '8px 0 0' }}>{strictCountryShortfall}</p>
        </section>
      ) : null}
      <section className="step-indicator panel">
        <StepCard step="1" title="潜在客户发现" status={step1Status as any} />
        <div className="step-line" />
        <StepCard step="2" title="核心联系人挖掘" status={step2Status as any} />
        <div className="step-line" />
        <StepCard step="3" title="触达拓展" status="locked" />
      </section>

      <section className="panel section-panel">
        <div className="field-inline">
          <div>
            <h2>最近任务</h2>
            <p className="muted-text" style={{ margin: '6px 0 0' }}>
              页面刷新后会自动恢复最近一次有效任务，你也可以从这里快速切换到最近 20 条搜索记录。
            </p>
          </div>
          <div className="toolbar-actions">
            <button className="button secondary" type="button" onClick={() => void refreshTaskHistory(taskId)} disabled={historyLoading}>
              {historyLoading ? '刷新中…' : '刷新任务记录'}
            </button>
            <Link className="button secondary" to="/history">查看全部记录</Link>
          </div>
        </div>
        {historyError ? <p className="field-error" style={{ marginBottom: 16 }}>{historyError}</p> : null}
        <div className="history-task-list">
          {taskHistory.length > 0 ? taskHistory.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`history-task-card${item.id === taskId ? ' is-active' : ''}`}
              onClick={() => setTaskId(item.id)}
            >
              <strong>{item.params?.product_name || '未命名任务'}</strong>
              <span>{(item.params?.countries || []).join('、') || '未指定国家'}</span>
              <small>{item.status} · 线索 {item.lead_count} · 关键人 {item.decision_maker_done_count}</small>
            </button>
          )) : (
            <div className="muted-text">暂无历史任务。先运行一次搜索，结果会自动保留。</div>
          )}
        </div>
      </section>

      <section className="section-panel">
        <h2>▼ STEP 1 — 潜在客户发现</h2>
        <LeadSearchForm
          isSubmitting={isSubmitting}
          initialValues={formInitialValues}
          initialTaskId={activeTaskSummary?.id ?? null}
          onSubmit={async (payload: LeadSearchPayload) => {
            try {
              setIsSubmitting(true);
              setTaskError(null);
              setTaskStatus(null);
              const response = await apiClient.post<{ task_id: string }>('/leads/search', payload);
              setRows([]);
              setTotalRows(0);
              setSelectedIds([]);
              setPage(1);
              setTaskId(response.data.task_id);
              await refreshTaskHistory(response.data.task_id);
            } catch (error) {
              setIsSubmitting(false);
              setTaskError(formatError(error, '搜索任务创建失败，请稍后重试。'));
            }
          }}
        />
        {progressCard}
      </section>

      <section className={`panel section-panel ${step2Unlocked ? '' : 'panel-disabled'}`}>
        <h2>▼ STEP 2 — 核心联系人挖掘</h2>
        <p className="muted-text">联系人批量操作与导出已整合到下方统一结果表格工具栏右侧。</p>
      </section>

      <section className="section-panel">
        <h2>▼ 统一结果表格（STEP 1 + STEP 2 共用）</h2>
        <div className="result-toolbar panel">
          <div className="toolbar-actions">
            <button className="button secondary" type="button" disabled={!step2Unlocked} onClick={() => setSelectedIds(rows.map((row) => row.id))}>☑ 全选</button>
            <button className="button" type="button" disabled={!step2Unlocked} onClick={() => runContactQueue(rows.map((row) => row.id), 'decision_maker')}>查找关键人</button>
            <button className="button" type="button" disabled={!step2Unlocked} onClick={() => runContactQueue(rows.map((row) => row.id), 'general_contact')}>抓取潜在联系方式</button>
            <button className="button" type="button" disabled={!step2Unlocked} onClick={() => runContactQueue(rows.map((row) => row.id), 'all')}>全部查找联系人</button>
            <button className="button" type="button" disabled={!step2Unlocked || selectedIds.length === 0} onClick={() => runContactQueue(selectedIds, 'all')}>批量查找（{selectedIds.length}家）</button>
          </div>
          <div className="toolbar-actions">
            <button className="export-btn export-btn-excel" type="button" disabled={!step2Unlocked} onClick={() => exportResults('xlsx')}>↓ Excel</button>
            <button className="export-btn export-btn-csv" type="button" disabled={!step2Unlocked} onClick={() => exportResults('csv')}>↓ CSV</button>
          </div>
        </div>
        <LeadTable
          rows={rows}
          selectedIds={selectedIds}
          step2Unlocked={step2Unlocked}
          page={page}
          pageSize={pageSize}
          total={totalRows}
          onToggleRow={(leadId) => setSelectedIds((current) => current.includes(leadId) ? current.filter((id) => id !== leadId) : [...current, leadId])}
          onToggleAll={() => setSelectedIds((current) => current.length === rows.length ? [] : rows.map((row) => row.id))}
          onEnrichDecisionMakers={(leadId) => runContactQueue([leadId], 'decision_maker')}
          onEnrichGeneralContacts={(leadId) => runContactQueue([leadId], 'general_contact')}
          onEnrichAllContacts={(leadId) => runContactQueue([leadId], 'all')}
          onPageChange={(nextPage) => setPage(nextPage)}
          onPageSizeChange={(nextPageSize) => {
            setPage(1);
            setPageSize(nextPageSize);
          }}
        />
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
