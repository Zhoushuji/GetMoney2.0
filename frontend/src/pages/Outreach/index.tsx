import axios from 'axios';
import { useEffect, useRef, useState } from 'react';

import { apiClient } from '../../api/client';
import { useTaskStore } from '../../stores/useTaskStore';

type ChannelRecommendation = {
  channel: 'email' | 'linkedin' | 'whatsapp' | 'phone' | string;
  count: number;
  priority: number;
  reason: string;
};

type MessageRecommendation = {
  channel: string;
  subject: string;
  body: string;
};

type SampleTarget = {
  lead_id: string;
  company_name?: string | null;
  contact_name?: string | null;
  contact_title?: string | null;
  country?: string | null;
  channels: string[];
};

type OutreachPreview = {
  status: 'ready' | 'draft' | 'empty' | string;
  task_id?: string | null;
  task_status?: string | null;
  task_progress?: number | null;
  summary: {
    lead_count: number;
    contact_count: number;
    channel_counts: Record<'email' | 'linkedin' | 'whatsapp' | 'phone', number>;
  };
  contactable_lead_count?: number;
  recommended_channels: ChannelRecommendation[];
  message_recommendations: MessageRecommendation[];
  sample_targets: SampleTarget[];
  next_actions: string[];
  generated_at?: string;
  contacts_indexed?: number;
};

const emptyPreview: OutreachPreview = {
  status: 'empty',
  task_status: null,
  task_progress: null,
  summary: {
    lead_count: 0,
    contact_count: 0,
    channel_counts: { email: 0, linkedin: 0, whatsapp: 0, phone: 0 },
  },
  contactable_lead_count: 0,
  recommended_channels: [],
  message_recommendations: [],
  sample_targets: [],
  next_actions: [],
};

function renderChannelLabel(channel: string) {
  return {
    email: 'Email',
    linkedin: 'LinkedIn',
    whatsapp: 'WhatsApp',
    phone: 'Phone',
  }[channel] ?? channel;
}

function normalizePreview(data?: Partial<OutreachPreview> | null): OutreachPreview {
  return {
    ...emptyPreview,
    ...data,
    summary: {
      ...emptyPreview.summary,
      ...(data?.summary ?? {}),
      channel_counts: {
        ...emptyPreview.summary.channel_counts,
        ...(data?.summary?.channel_counts ?? {}),
      },
    },
    contactable_lead_count: data?.contactable_lead_count ?? 0,
    recommended_channels: data?.recommended_channels ?? [],
    message_recommendations: data?.message_recommendations ?? [],
    sample_targets: data?.sample_targets ?? [],
    next_actions: data?.next_actions ?? [],
  };
}

export function OutreachPage() {
  const { taskId } = useTaskStore();
  const [preview, setPreview] = useState<OutreachPreview>(emptyPreview);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  const loadPreview = async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
      const response = await apiClient.get<OutreachPreview>(`/outreach/preview${query}`);
      if (requestId !== requestIdRef.current) return;
      setPreview(normalizePreview(response.data));
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      const detail = axios.isAxiosError(err)
        ? (typeof err.response?.data === 'string'
          ? err.response.data
          : err.response?.data?.detail || err.message)
        : err instanceof Error
          ? err.message
          : '';
      setError(detail ? `无法加载触达预览：${detail}` : '无法加载触达预览，请确认后端服务已启动。');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadPreview();
  }, [taskId]);

  const summaryCards = [
    { label: 'Leads', value: preview.summary.lead_count },
    { label: 'Lead records with contact data', value: preview.summary.contact_count },
    { label: 'Leads with indexed contacts', value: preview.contactable_lead_count ?? 0 },
    { label: 'Contacts indexed', value: preview.contacts_indexed ?? 0 },
    { label: 'Email-ready', value: preview.summary.channel_counts.email },
    { label: 'LinkedIn-ready', value: preview.summary.channel_counts.linkedin },
    { label: 'WhatsApp-ready', value: preview.summary.channel_counts.whatsapp },
    { label: 'Phone-ready', value: preview.summary.channel_counts.phone },
  ];

  const isRunning = preview.task_status === 'running';
  const resolvedTaskTag = preview.task_id ? `Task ${preview.task_id.slice(0, 8)}` : 'Latest task';
  const statusTag = preview.task_status ?? preview.status;
  const nextActions = preview.next_actions.length > 0
    ? preview.next_actions
    : ['No next actions are available yet.'];

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="page-heading">
          <div className="title-stack">
            <h2>客户触达与商业拓展</h2>
            <p>
              基于当前 lead/contact 数据生成确定性预览，不依赖外部 LLM。任务切换后会自动刷新。
            </p>
          </div>
          <button className="button secondary" type="button" onClick={() => void loadPreview()} disabled={loading}>
            {loading ? '加载中…' : '刷新预览'}
          </button>
        </div>
        <div className="tag-list">
          <span className="tag">{resolvedTaskTag}</span>
          <span className="tag">{statusTag}</span>
          {preview.task_progress != null ? <span className="tag">Progress {preview.task_progress}%</span> : null}
          <span className="tag">Deterministic</span>
          <span className="tag">No external LLM</span>
        </div>
      </section>

      <section className="panel">
        <div className="stats-grid">
          {summaryCards.map((card) => (
            <div key={card.label} className="kpi-card">
              <strong style={{ fontSize: 28, display: 'block' }}>{card.value}</strong>
              <p>{card.label}</p>
            </div>
          ))}
        </div>
        <div className="kpi-grid">
          <div className="kpi-card"><strong>{preview.task_status ?? 'n/a'}</strong><p>Task status</p></div>
          <div className="kpi-card"><strong>{preview.contactable_lead_count ?? 0}</strong><p>Leads with indexed contacts</p></div>
          <div className="kpi-card"><strong>{preview.status}</strong><p>Preview state</p></div>
        </div>
      </section>

      {loading ? (
        <section className="panel">
          <h3>正在生成预览</h3>
          <p>正在读取当前任务的 lead 和 contact 数据，稍后会显示推荐渠道与首封消息草案。</p>
        </section>
      ) : error ? (
        <section className="panel">
          <h3>加载失败</h3>
          <p>{error}</p>
          <button className="button secondary" type="button" onClick={() => void loadPreview()}>
            重试
          </button>
        </section>
      ) : preview.status === 'empty' ? (
        <section className="panel">
          <h3>{isRunning ? '任务仍在生成预览' : '暂无可执行触达数据'}</h3>
          <p>
            {isRunning
              ? '当前 discovery 任务还在运行，预览会在任务完成后生成。你可以稍后刷新查看最新结果。'
              : '当前没有可用的 lead/contact 预览，先跑潜在客户发现和联系人挖掘，再回到这里查看建议。'}
          </p>
          <ul>
            {nextActions.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </section>
      ) : (
        <>
          <section className="panel">
            <h3>推荐渠道</h3>
            <div className="page-stack">
              {preview.recommended_channels.length > 0 ? preview.recommended_channels.map((item) => (
                <div key={item.channel} className="surface-card surface-card-soft">
                  <div className="page-heading">
                    <strong>{renderChannelLabel(item.channel)}</strong>
                    <span className="tag">覆盖 {item.count}</span>
                  </div>
                  <p className="muted-text">{item.reason}</p>
                </div>
              )) : (
                <p>
                  当前没有足够的渠道信号。先补充联系人数据，或者刷新查看最新的 discovery 结果。
                </p>
              )}
            </div>
          </section>

          <section className="panel">
            <h3>消息草案</h3>
            <div className="page-stack">
              {preview.message_recommendations.length > 0 ? preview.message_recommendations.map((item) => (
                <div key={item.channel} className="surface-card surface-card-soft">
                  <div className="page-heading">
                    <strong>{renderChannelLabel(item.channel)}</strong>
                    <span className="tag">{item.subject}</span>
                  </div>
                  <pre className="message-body">{item.body}</pre>
                </div>
              )) : (
                <p>当前没有可生成的消息草案，先确认有没有可用的联系方式。</p>
              )}
            </div>
          </section>

          <section className="panel">
            <h3>示例触达对象</h3>
            <div className="page-stack">
              {preview.sample_targets.length > 0 ? preview.sample_targets.slice(0, 5).map((item) => (
                <div key={item.lead_id} className="surface-card surface-card-soft">
                  <strong>{item.company_name ?? 'Unknown company'}</strong>
                  <p className="muted-text">
                    {item.contact_name ? `${item.contact_name}${item.contact_title ? ` · ${item.contact_title}` : ''}` : '未挖掘到明确联系人'}
                  </p>
                  <div className="tag-list">
                    {item.country ? <span className="tag">{item.country}</span> : null}
                    {item.channels.map((channel) => <span key={channel} className="tag">{renderChannelLabel(channel)}</span>)}
                  </div>
                </div>
              )) : (
                <p style={{ marginBottom: 0 }}>当前没有可展示的示例触达对象。</p>
              )}
            </div>
          </section>

          <section className="panel">
            <h3>下一步</h3>
            <ul>
              {nextActions.map((item) => <li key={item}>{item}</li>)}
            </ul>
            {preview.generated_at ? <p className="muted-text">Generated at {preview.generated_at}</p> : null}
          </section>
        </>
      )}
    </div>
  );
}
