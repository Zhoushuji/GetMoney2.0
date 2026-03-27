import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { apiClient } from '../../api/client';
import { useWorkspaceContext } from '../../components/Layout/AppLayout';
import { formatTaskKeywordTitle } from '../../components/Layout/taskSummary';
import { useTaskStore } from '../../stores/useTaskStore';

type ReviewRecord = {
  lead_id: string;
  field_key: string;
  company_name?: string | null;
  current_value?: string | null;
  verdict: 'correct' | 'incorrect';
  source_path: string;
  note?: string | null;
  reviewed_at?: string | null;
};

type ReviewListResponse = {
  items: ReviewRecord[];
  total: number;
};

function formatDate(value?: string | null) {
  if (!value) return '-';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export function ReviewsPage() {
  const { taskId } = useTaskStore();
  const { taskHistory } = useWorkspaceContext();
  const [items, setItems] = useState<ReviewRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeTask = useMemo(() => taskHistory.find((item) => item.id === taskId) ?? null, [taskHistory, taskId]);

  useEffect(() => {
    if (!taskId) {
      setItems([]);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.get<ReviewListResponse>('/reviews', { params: { task_id: taskId } });
        if (!cancelled) {
          setItems(response.data.items ?? []);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : '审核记录读取失败');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const exportReviews = async (format: 'xlsx' | 'csv') => {
    if (!taskId) return;
    const response = await apiClient.get(`/reviews/export?task_id=${taskId}&format=${format}`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.download = `lead-reviews.${format}`;
    link.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="flow-page page-stack">
      <section className="panel section-panel">
        <div className="page-heading">
          <div className="title-stack">
            <h2>字段审核记录</h2>
            <p className="muted-text">
              这里只汇总当前任务中已经手工标记过的字段，可直接导出成 CSV 或 XLSX。
            </p>
          </div>
          <div className="toolbar-actions">
            <button className="export-btn export-btn-excel" type="button" disabled={!taskId || items.length === 0} onClick={() => void exportReviews('xlsx')}>↓ Excel</button>
            <button className="export-btn export-btn-csv" type="button" disabled={!taskId || items.length === 0} onClick={() => void exportReviews('csv')}>↓ CSV</button>
            <Link className="button secondary" to="/">返回结果表</Link>
          </div>
        </div>
        <div className="task-summary-strip">
          <strong>{activeTask ? formatTaskKeywordTitle(activeTask.params, '未命名任务') : '未选择任务'}</strong>
          <span>{(activeTask?.params?.countries || []).join('、') || '未指定国家'} · {(activeTask?.params?.mode || 'live').toUpperCase()}</span>
        </div>
      </section>

      {error ? (
        <section className="panel notice-panel notice-danger">
          <strong>审核记录加载失败</strong>
          <p className="muted-text">{error}</p>
        </section>
      ) : null}

      <section className="panel">
        <div className="table-wrap">
          <table className="lead-table result-table">
            <thead>
              <tr>
                <th>#</th>
                <th>公司</th>
                <th>字段</th>
                <th>当前值</th>
                <th>判定</th>
                <th>获取路径</th>
                <th>备注</th>
                <th>标记时间</th>
              </tr>
            </thead>
            <tbody>
              {items.length > 0 ? items.map((item, index) => (
                <tr key={`${item.lead_id}:${item.field_key}`}>
                  <td>{index + 1}</td>
                  <td>{item.company_name || '-'}</td>
                  <td>{item.field_key}</td>
                  <td className="review-value-cell">{item.current_value || '-'}</td>
                  <td>{item.verdict === 'correct' ? '正确' : '错误'}</td>
                  <td className="review-value-cell">{item.source_path}</td>
                  <td className="review-value-cell">{item.note || '-'}</td>
                  <td>{formatDate(item.reviewed_at)}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={8} className="empty-state">
                    <span className="muted-text">{loading ? '加载中…' : '当前任务还没有任何已审核字段。回到结果表后点击字段后的标记开始审核。'}</span>
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
