type Props = {
  status: string;
  progress: number;
  total: number;
  completed: number;
};

export function TaskProgressCard({ status, progress, total, completed }: Props) {
  return (
    <section className="panel">
      <h2>任务进度</h2>
      <div className="kpi-grid">
        <div className="stat-card"><strong>状态</strong><p>{status}</p></div>
        <div className="stat-card"><strong>已完成</strong><p>{completed} / {total}</p></div>
        <div className="stat-card"><strong>进度</strong><p>{progress}%</p></div>
      </div>
      <div className="progress-bar" style={{ marginTop: 16 }}>
        <span style={{ width: `${progress}%` }} />
      </div>
    </section>
  );
}
