type Props = {
  status: string;
  progress: number;
  total: number;
  completed: number;
  confirmedLeads: number;
  targetCount: number | null;
  phase?: string | null;
  estimatedTotalSeconds?: number | null;
  estimatedRemainingSeconds?: number | null;
  stoppedEarly: boolean;
};

function formatEta(seconds?: number | null) {
  if (seconds == null) return '—';
  if (seconds < 60) return `约 ${Math.max(0, Math.round(seconds))} 秒`;
  return `约 ${Math.max(1, Math.round(seconds / 60))} 分钟`;
}

export function TaskProgressCard({
  status,
  progress,
  total,
  completed,
  confirmedLeads,
  targetCount,
  phase,
  estimatedTotalSeconds,
  estimatedRemainingSeconds,
  stoppedEarly,
}: Props) {
  const targetReached = targetCount !== null && confirmedLeads >= targetCount;
  const progressClassName = targetReached || stoppedEarly ? 'progress-bar progress-bar-success' : 'progress-bar';

  return (
    <section className="panel section-panel panel-soft">
      <div className="page-heading">
        <div className="title-stack">
          <h2>任务进度</h2>
          <p>任务运行中会持续刷新阶段、预计剩余时间和已确认结果。</p>
        </div>
      </div>
      <div className="kpi-grid">
        <div className="stat-card"><strong>状态</strong><p>{status}</p></div>
        <div className="stat-card"><strong>已派发 / 总数</strong><p>{completed} / {total}</p></div>
        <div className="stat-card"><strong>已确认客户</strong><p>{targetCount ? `${confirmedLeads} / ${targetCount}` : `${confirmedLeads} / 不限`}</p></div>
      </div>
      <div className={progressClassName} style={{ marginTop: 16 }}>
        <span style={{ width: `${progress}%` }} />
      </div>
      <div className="progress-meta">
        <span>进度：{progress}%</span>
        <span>阶段：{phase || '—'}</span>
        <span>预计剩余：{formatEta(estimatedRemainingSeconds)}</span>
      </div>
      {estimatedTotalSeconds != null ? <p className="muted-text">预计总耗时：{formatEta(estimatedTotalSeconds)}</p> : null}
      {targetReached || stoppedEarly ? <p className="success-text">已达到目标数量，搜索已停止。</p> : null}
    </section>
  );
}
