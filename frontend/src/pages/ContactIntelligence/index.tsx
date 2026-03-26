import { useEffect, useMemo, useRef, useState } from 'react';

import { apiClient } from '../../api/client';
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

type LeadItem = {
  id: string;
  company_name?: string;
  website?: string;
  country?: string;
  contact_status: string;
  decision_maker_status?: string;
  general_contact_status?: string;
  contact_name?: string;
  contact_title?: string;
  linkedin_personal_url?: string;
  personal_email?: string;
  work_email?: string;
  phone?: string;
  whatsapp?: string;
  general_emails?: string[] | null;
  potential_contacts?: { items?: string[] } | null;
};

type LeadListResponse = {
  items: LeadItem[];
  total: number;
  page: number;
  page_size: number;
};

const STATUS_ORDER = ['pending', 'running', 'no_data', 'failed', 'timeout', 'done', 'completed'];
function leadStatusTone(status?: string) {
  switch (status) {
    case 'running':
      return { background: '#dbeafe', color: '#1d4ed8', label: '进行中' };
    case 'done':
      return { background: '#dcfce7', color: '#15803d', label: '已完成' };
    case 'completed':
      return { background: '#dcfce7', color: '#15803d', label: '已完成' };
    case 'no_data':
      return { background: '#f3f4f6', color: '#4b5563', label: '无数据' };
    case 'timeout':
      return { background: '#ffedd5', color: '#c2410c', label: '超时' };
    case 'failed':
      return { background: '#fee2e2', color: '#b91c1c', label: '失败' };
    default:
      return { background: '#f3f4f6', color: '#4b5563', label: '待执行' };
  }
}

function taskStatusTone(status?: string) {
  switch (status) {
    case 'running':
      return { background: '#dbeafe', color: '#1d4ed8', label: '进行中' };
    case 'pending':
      return { background: '#f3f4f6', color: '#4b5563', label: '排队中' };
    case 'completed':
    case 'done':
      return { background: '#dcfce7', color: '#15803d', label: '已完成' };
    case 'stopped_early':
      return { background: '#ffedd5', color: '#c2410c', label: '提前结束' };
    case 'failed':
      return { background: '#fee2e2', color: '#b91c1c', label: '失败' };
    default:
      return { background: '#f3f4f6', color: '#4b5563', label: status ?? '未知' };
  }
}

function formatSeconds(seconds?: number | null) {
  if (seconds == null || Number.isNaN(seconds)) return '未知';
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))} 秒`;
  const minutes = Math.round(seconds / 60);
  return `${minutes} 分钟`;
}

function compactList(values: Array<string | undefined | null>) {
  return values.filter((value): value is string => Boolean(value && value.trim())).join(' / ');
}

function isLeadFinished(status?: string) {
  return status === 'done' || status === 'completed';
}

export function ContactIntelligencePage() {
  const taskId = useTaskStore((state) => state.taskId);
  const [searchTask, setSearchTask] = useState<TaskStatus | null>(null);
  const [enrichmentTask, setEnrichmentTask] = useState<TaskStatus | null>(null);
  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [totalLeads, setTotalLeads] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLaunching, setIsLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const enrichmentTaskIdRef = useRef<string | null>(null);
  const refreshLockRef = useRef(false);
  const pendingRefreshRef = useRef(false);
  const activeTaskIdRef = useRef<string | null>(null);

  const fetchTaskStatus = async (id: string) => {
    const response = await apiClient.get<TaskStatus>(`/tasks/${id}/status`);
    return response.data;
  };

  const fetchAllLeads = async (activeTaskId: string) => {
    const pageSize = 200;
    let page = 1;
    let total = 0;
    const collected: LeadItem[] = [];

    while (true) {
      const response = await apiClient.get<LeadListResponse>('/leads', {
        params: { task_id: activeTaskId, page, page_size: pageSize },
      });
      const payload = response.data;
      total = payload.total;
      collected.push(...payload.items);
      if (collected.length >= payload.total || payload.items.length < payload.page_size) break;
      page += 1;
    }

    return { items: collected, total };
  };

  const refreshWorkspace = async () => {
    if (!taskId) return;
    if (refreshLockRef.current) {
      pendingRefreshRef.current = true;
      return;
    }
    refreshLockRef.current = true;
    setIsRefreshing(true);
    setError(null);
    const requestedTaskId = taskId;
    const requestedEnrichmentTaskId = enrichmentTaskIdRef.current;

    try {
      const [searchStatusResult, leadResultResult, enrichmentStatusResult] = await Promise.allSettled([
        fetchTaskStatus(taskId),
        fetchAllLeads(taskId),
        requestedEnrichmentTaskId ? fetchTaskStatus(requestedEnrichmentTaskId) : Promise.resolve(null),
      ]);

      if (activeTaskIdRef.current !== requestedTaskId) return;

      const nextErrors: string[] = [];

      if (searchStatusResult.status === 'fulfilled') {
        setSearchTask(searchStatusResult.value);
      } else {
        nextErrors.push('搜索任务状态');
      }

      if (leadResultResult.status === 'fulfilled') {
        setLeads(leadResultResult.value.items);
        setTotalLeads(leadResultResult.value.total);
      } else {
        nextErrors.push('企业列表');
      }

      if (enrichmentStatusResult.status === 'fulfilled') {
        setEnrichmentTask(enrichmentStatusResult.value);
      } else if (requestedEnrichmentTaskId) {
        nextErrors.push('联系人任务状态');
      }

      setLastUpdatedAt(new Date().toLocaleString());
      setError(nextErrors.length > 0 ? `刷新部分失败：${nextErrors.join('、')}` : null);
    } catch (err) {
      const message = err instanceof Error ? err.message : '联系人页面刷新失败';
      setError(message);
    } finally {
      setIsRefreshing(false);
      refreshLockRef.current = false;
      if (pendingRefreshRef.current) {
        pendingRefreshRef.current = false;
        void refreshWorkspace();
      }
    }
  };

  const launchEnrichment = async (leadIds?: string[]) => {
    if (!taskId) return;
    const targetLeadIds = (leadIds && leadIds.length > 0 ? leadIds : leads.map((lead) => lead.id)).filter(Boolean);
    if (targetLeadIds.length === 0) {
      setError('没有可启动联系人挖掘的企业。');
      return;
    }
    setIsLaunching(true);
    setError(null);

    try {
      const response = await apiClient.post<{ task_id: string }>('/contacts/enrich', {
        lead_ids: targetLeadIds,
        mode: 'all',
      });
      enrichmentTaskIdRef.current = response.data.task_id;
      await refreshWorkspace();
    } catch (err) {
      const message = err instanceof Error ? err.message : '启动联系人挖掘失败';
      setError(message);
    } finally {
      setIsLaunching(false);
    }
  };

  useEffect(() => {
    activeTaskIdRef.current = taskId ?? null;
    if (!taskId) {
      setSearchTask(null);
      setEnrichmentTask(null);
      setLeads([]);
      setTotalLeads(0);
      setLastUpdatedAt(null);
      setError(null);
      enrichmentTaskIdRef.current = null;
      refreshLockRef.current = false;
      pendingRefreshRef.current = false;
      return undefined;
    }

    setSearchTask(null);
    setEnrichmentTask(null);
    setLeads([]);
    setTotalLeads(0);
    setLastUpdatedAt(null);
    setError(null);
    enrichmentTaskIdRef.current = null;
    refreshLockRef.current = false;
    pendingRefreshRef.current = false;

    void refreshWorkspace();
    const timer = window.setInterval(() => {
      void refreshWorkspace();
    }, 12000);

    return () => window.clearInterval(timer);
  }, [taskId]);

  const statusSummary = useMemo(() => {
    const countBy = (predicate: (lead: LeadItem) => boolean) => leads.filter(predicate).length;
    const keyDone = countBy((lead) => isLeadFinished(lead.decision_maker_status));
    const keyRunning = countBy((lead) => lead.decision_maker_status === 'running');
    const keyPending = countBy((lead) => lead.decision_maker_status === 'pending');
    const keyBlocked = countBy((lead) => ['failed', 'timeout', 'no_data'].includes(lead.decision_maker_status ?? ''));
    const contactDone = countBy((lead) => isLeadFinished(lead.general_contact_status));
    const contactRunning = countBy((lead) => lead.general_contact_status === 'running');
    const contactPending = countBy((lead) => lead.general_contact_status === 'pending');
    const contactBlocked = countBy((lead) => ['failed', 'timeout', 'no_data'].includes(lead.general_contact_status ?? ''));
    const fullyContacted = countBy((lead) => Boolean(lead.contact_name || lead.contact_title || lead.personal_email || lead.work_email || lead.phone || lead.whatsapp));

    return {
      total: leads.length,
      keyDone,
      keyRunning,
      keyPending,
      keyBlocked,
      contactDone,
      contactRunning,
      contactPending,
      contactBlocked,
      fullyContacted,
    };
  }, [leads]);

  const visibleLeads = useMemo(() => {
    return [...leads].sort((a, b) => {
      const score = (lead: LeadItem) => {
        const decision = STATUS_ORDER.indexOf(lead.decision_maker_status ?? 'pending');
        const general = STATUS_ORDER.indexOf(lead.general_contact_status ?? 'pending');
        return Math.min(decision === -1 ? 0 : decision, general === -1 ? 0 : general);
      };
      const delta = score(a) - score(b);
      if (delta !== 0) return delta;
      return (a.company_name ?? '').localeCompare(b.company_name ?? '');
    }).slice(0, 15);
  }, [leads]);

  const searchTaskBadge = taskStatusTone(searchTask?.status);
  const enrichmentTaskBadge = taskStatusTone(enrichmentTask?.status);

  return (
    <div className="flow-page">
      <section className="panel">
        <div className="block-heading">
          <div>
            <h2>核心联系人挖掘</h2>
            <p className="muted-text" style={{ margin: '6px 0 0' }}>
              自动读取当前任务，展示已发现的企业列表，并把关键人和潜在联系方式的挖掘进度放在同一页管理。
            </p>
          </div>
          <div className="toolbar-actions">
            <button className="button secondary" type="button" onClick={() => void refreshWorkspace()} disabled={!taskId || isRefreshing}>
              {isRefreshing ? '刷新中…' : '刷新数据'}
            </button>
            <button className="button" type="button" onClick={() => void launchEnrichment()} disabled={!taskId || isLaunching || leads.length === 0}>
              {isLaunching ? '启动中…' : '批量启动联系人挖掘'}
            </button>
          </div>
        </div>

        <div className="kpi-grid">
          <div className="kpi-card">
            <strong>{taskId ? '已连接任务' : '未选择任务'}</strong>
            <p>{taskId ?? '先在潜在客户发现页启动一次搜索。'}</p>
          </div>
          <div className="kpi-card">
            <strong>{searchTaskBadge.label}</strong>
            <p>搜索任务：{searchTask?.status ?? '未知'}</p>
          </div>
          <div className="kpi-card">
            <strong>{enrichmentTaskBadge.label}</strong>
            <p>联系人任务：{enrichmentTask?.status ?? '未启动'}</p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="panel" style={{ borderColor: '#fecaca', background: '#fef2f2' }}>
          <strong>页面刷新失败</strong>
          <p className="muted-text" style={{ marginBottom: 0 }}>{error}</p>
        </section>
      ) : null}

      {!taskId ? (
        <section className="panel">
          <h3>如何使用</h3>
          <ul>
            <li>先到潜在客户发现模块运行一次搜索，页面会自动读取 Zustand 中的 task id。</li>
            <li>这里会拉取该任务下的企业列表，并按关键人挖掘和联系方式挖掘的状态做汇总。</li>
            <li>点击“批量启动联系人挖掘”后，页面会持续轮询进度并更新结果。</li>
          </ul>
        </section>
      ) : (
        <>
          <section className="panel">
            <div className="block-heading">
              <h3>进度概览</h3>
              <span className="muted-text">最后更新：{lastUpdatedAt ?? '尚未刷新'}</span>
            </div>
            <div className="kpi-grid">
              <div className="kpi-card">
                <strong>{statusSummary.total}</strong>
                <p>当前企业数</p>
              </div>
              <div className="kpi-card">
                <strong>{statusSummary.keyDone}</strong>
                <p>关键人已完成</p>
              </div>
              <div className="kpi-card">
                <strong>{statusSummary.contactDone}</strong>
                <p>潜在联系方式已完成</p>
              </div>
              <div className="kpi-card">
                <strong>{statusSummary.fullyContacted}</strong>
                <p>已回填联系人信息</p>
              </div>
            </div>

            <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
              <div>
                <div className="field-inline" style={{ marginBottom: 8 }}>
                  <strong>关键人挖掘</strong>
                  <span className="muted-text">
                    进行中 {statusSummary.keyRunning} / 待处理 {statusSummary.keyPending} / 受阻 {statusSummary.keyBlocked}
                  </span>
                </div>
                <div className="progress-bar">
                  <span style={{ width: `${leads.length ? Math.round((statusSummary.keyDone / leads.length) * 100) : 0}%` }} />
                </div>
              </div>
              <div>
                <div className="field-inline" style={{ marginBottom: 8 }}>
                  <strong>潜在联系方式</strong>
                  <span className="muted-text">
                    进行中 {statusSummary.contactRunning} / 待处理 {statusSummary.contactPending} / 受阻 {statusSummary.contactBlocked}
                  </span>
                </div>
                <div className="progress-bar">
                  <span style={{ width: `${leads.length ? Math.round((statusSummary.contactDone / leads.length) * 100) : 0}%` }} />
                </div>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="block-heading">
              <h3>任务详情</h3>
              <span className="muted-text">
                搜索任务：{searchTaskBadge.label} · 联系人任务：{enrichmentTaskBadge.label}
              </span>
            </div>
            <div className="kpi-grid">
              <div className="kpi-card">
                <strong>{searchTaskBadge.label}</strong>
                <p>
                  已确认 {searchTask?.confirmed_leads ?? 0} / 目标 {(searchTask?.target_count ?? totalLeads) || '全部'} · 进度 {searchTask?.progress ?? 0}%
                </p>
              </div>
              <div className="kpi-card">
                <strong>{enrichmentTaskBadge.label}</strong>
                <p>
                  已完成 {enrichmentTask?.completed ?? 0} / 总计 {enrichmentTask?.total ?? 0} · 进度 {enrichmentTask?.progress ?? 0}%
                </p>
              </div>
              <div className="kpi-card">
                <strong>{formatSeconds(searchTask?.estimated_remaining_seconds)}</strong>
                <p>搜索预计剩余</p>
              </div>
              <div className="kpi-card">
                <strong>{formatSeconds(enrichmentTask?.estimated_remaining_seconds)}</strong>
                <p>联系人预计剩余</p>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="block-heading">
              <h3>企业结果</h3>
              <span className="muted-text">
                展示优先级按待处理排序，当前仅显示前 {visibleLeads.length} 家。
              </span>
            </div>

            <div className="table-wrap">
              <table className="lead-table result-table" style={{ minWidth: 1100 }}>
                <thead>
                  <tr>
                    <th>公司</th>
                    <th>国家</th>
                    <th>关键人状态</th>
                    <th>联系方式状态</th>
                    <th>联系人</th>
                    <th>联系方式</th>
                    <th>动作</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleLeads.map((lead) => (
                    <tr key={lead.id}>
                      <td>
                        <strong>{lead.company_name ?? '-'}</strong>
                        <div className="muted-text" style={{ marginTop: 4 }}>{lead.website ?? '-'}</div>
                      </td>
                      <td>{lead.country ?? '-'}</td>
                      <td>
                        <span className="tag" style={{ background: leadStatusTone(lead.decision_maker_status).background, color: leadStatusTone(lead.decision_maker_status).color, borderColor: 'transparent' }}>
                          {leadStatusTone(lead.decision_maker_status).label}
                        </span>
                      </td>
                      <td>
                        <span className="tag" style={{ background: leadStatusTone(lead.general_contact_status).background, color: leadStatusTone(lead.general_contact_status).color, borderColor: 'transparent' }}>
                          {leadStatusTone(lead.general_contact_status).label}
                        </span>
                      </td>
                      <td>
                        <div><strong>{lead.contact_name ?? '-'}</strong></div>
                        <div className="muted-text">{lead.contact_title ?? '-'}</div>
                      </td>
                      <td>
                        <div>{compactList([lead.personal_email, lead.work_email]) || '-'}</div>
                        <div className="muted-text">{compactList([lead.phone, lead.whatsapp]) || compactList(lead.general_emails ?? []) || '-'}</div>
                      </td>
                      <td>
                        <div className="toolbar-actions">
                          <button className="button secondary" type="button" onClick={() => void launchEnrichment([lead.id])} disabled={isLaunching}>
                            重新挖掘
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {visibleLeads.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="muted-text">
                        当前任务还没有可展示的企业，或搜索结果尚未同步完成。
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <h3>规则概览</h3>
            <ul>
              <li>只对模块一已有的企业执行联系人 enrichment，不新增或删除 lead。</li>
              <li>白名单：CEO / Founder / Owner / Managing Director / General Manager / GM / Procurement / Purchasing / Sourcing。</li>
              <li>黑名单优先：Director、Sales、Marketing、Support、HR、Accountant、Intern。</li>
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
