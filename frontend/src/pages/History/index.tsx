import { useNavigate } from 'react-router-dom';

import { useWorkspaceContext } from '../../components/Layout/AppLayout';
import { useTaskStore } from '../../stores/useTaskStore';

function formatDate(value?: string | null) {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function HistoryPage() {
  const navigate = useNavigate();
  const { taskHistory, historyLoading, historyError, refreshTaskHistory } = useWorkspaceContext();
  const { taskId, setTaskId } = useTaskStore();

  return (
    <div className="flow-page">
      <section className="panel section-panel">
        <div className="field-inline">
          <div>
            <h2>任务记录</h2>
            <p className="muted-text" style={{ margin: '6px 0 0' }}>
              最近 20 条根任务会保留在工作区中，重新打开页面后会自动恢复到最近一次有效任务。
            </p>
          </div>
          <button className="button secondary" type="button" onClick={() => void refreshTaskHistory()} disabled={historyLoading}>
            {historyLoading ? '刷新中…' : '刷新列表'}
          </button>
        </div>
      </section>

      {historyError ? (
        <section className="panel" style={{ borderColor: '#fecaca', background: '#fef2f2' }}>
          <strong>任务记录加载失败</strong>
          <p className="muted-text" style={{ marginBottom: 0 }}>{historyError}</p>
        </section>
      ) : null}

      <section className="panel">
        <div className="table-wrap">
          <table className="lead-table result-table">
            <thead>
              <tr>
                <th>#</th>
                <th>任务</th>
                <th>状态</th>
                <th>已确认线索</th>
                <th>关键人完成</th>
                <th>联系方式完成</th>
                <th>最近更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {taskHistory.length > 0 ? taskHistory.map((item, index) => (
                <tr key={item.id}>
                  <td>{index + 1}</td>
                  <td>
                    <div className="company-cell">
                      <strong>{item.params?.product_name || '未命名搜索任务'}</strong>
                      <small>{(item.params?.countries || []).join('、') || '未指定国家'} · {(item.params?.mode || 'live').toUpperCase()}</small>
                    </div>
                  </td>
                  <td>{item.status}</td>
                  <td>{item.confirmed_leads}</td>
                  <td>{item.decision_maker_done_count}</td>
                  <td>{item.general_contact_done_count}</td>
                  <td>{formatDate(item.updated_at)}</td>
                  <td>
                    <button
                      className="button secondary"
                      type="button"
                      onClick={() => {
                        setTaskId(item.id);
                        void refreshTaskHistory(item.id);
                        navigate('/');
                      }}
                      disabled={taskId === item.id}
                    >
                      {taskId === item.id ? '当前任务' : '打开'}
                    </button>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '28px 16px' }}>
                    <span className="muted-text">暂无历史任务。先在潜在客户发现页运行一次搜索。</span>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
