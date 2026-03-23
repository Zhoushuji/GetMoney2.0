type Props = {
  status: string;
  progress: number;
  total: number;
  completed: number;
  confirmedLeads: number;
  targetCount: number | null;
  estimatedRemainingSeconds?: number | null;
  stoppedEarly: boolean;
};

export function TaskProgressCard({
  status,
  progress,
  total,
  completed,
  confirmedLeads,
  targetCount,
  estimatedRemainingSeconds,
  stoppedEarly,
}: Props) {
  const targetReached = targetCount !== null && confirmedLeads >= targetCount;
  const progressClassName = targetReached || stoppedEarly ? 'progress-bar progress-bar-success' : 'progress-bar';

  return (
    <section className="panel">
      <h2>任务进度</h2>
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
        <span>预计剩余：{estimatedRemainingSeconds ? `${estimatedRemainingSeconds}s` : '—'}</span>
      </div>
      {targetReached || stoppedEarly ? <p className="success-text">已达到目标数量，搜索已停止。</p> : null}
    </section>
  );
}
