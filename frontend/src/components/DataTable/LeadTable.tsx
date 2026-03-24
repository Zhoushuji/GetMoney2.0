export type LeadRow = {
  id: string;
  company_name?: string;
  website?: string;
  facebook_url?: string;
  linkedin_url?: string;
  country?: string;
  contact_status: 'pending' | 'running' | 'done' | 'failed' | 'no_data' | 'timeout' | string;
  contact_name?: string;
  contact_title?: string;
  linkedin_personal_url?: string;
  personal_email?: string;
  work_email?: string;
  phone?: string;
  whatsapp?: string;
  potential_contacts?: { items?: string[] } | null;
};

type Props = {
  rows: LeadRow[];
  selectedIds: string[];
  step2Unlocked: boolean;
  page: number;
  pageSize: number;
  total: number;
  onToggleRow: (leadId: string) => void;
  onToggleAll: () => void;
  onEnrichOne: (leadId: string) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

function renderDomain(url?: string) {
  if (!url) return '-';
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export function LeadTable({ rows, selectedIds, step2Unlocked, page, pageSize, total, onToggleRow, onToggleAll, onEnrichOne, onPageChange, onPageSizeChange }: Props) {
  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.includes(row.id));
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const renderContactAction = (row: LeadRow) => {
    if (!step2Unlocked) return <span className="muted-text">待解锁</span>;
    if (row.contact_status === 'running') return <span className="status-inline"><span className="spinner-inline" /> 挖掘中...</span>;
    if (row.contact_status === 'done') return <span className="done-text">✓ 已完成</span>;
    if (row.contact_status === 'no_data') return <span className="no-data-text">— 暂无数据</span>;
    if (row.contact_status === 'timeout') return <button className="button secondary timeout-btn" type="button" onClick={() => onEnrichOne(row.id)}>⏱ 超时 重试</button>;
    if (row.contact_status === 'failed') return <button className="button secondary timeout-btn" type="button" onClick={() => onEnrichOne(row.id)}>⚠ 重试</button>;
    return <button className="button secondary" type="button" onClick={() => onEnrichOne(row.id)}>查找联系人</button>;
  };

  const renderCellValue = (row: LeadRow, key: keyof LeadRow) => {
    if ((row.contact_status === 'no_data' || row.contact_status === 'timeout') && ['contact_name', 'contact_title', 'linkedin_personal_url', 'personal_email', 'work_email', 'phone', 'whatsapp'].includes(key as string)) {
      return '—';
    }
    return row[key] as string | undefined;
  };

  return (
    <section className="panel">
      <div className="table-wrap unified-table-wrap">
        <table className="lead-table result-table">
          <thead>
            <tr>
              <th className="sticky-col sticky-check"><input type="checkbox" checked={allSelected} onChange={onToggleAll} /></th>
              <th className="sticky-col sticky-index">#</th>
              <th className="sticky-col sticky-company col-company">公司名称</th>
              <th className="col-website">官网</th>
              <th>Facebook</th>
              <th>LinkedIn</th>
              <th>国家</th>
              <th className="sticky-col sticky-action">联系人操作</th>
              <th className="col-contact-name">联系人姓名</th>
              <th className="col-title">职位</th>
              <th>个人LinkedIn</th>
              <th className="col-email">个人邮箱</th>
              <th className="col-email">工作邮箱</th>
              <th>电话</th>
              <th>WhatsApp</th>
              <th>潜在联系方式</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id}>
                <td className="sticky-col sticky-check"><input type="checkbox" checked={selectedIds.includes(row.id)} onChange={() => onToggleRow(row.id)} /></td>
                <td className="sticky-col sticky-index">{(page - 1) * pageSize + index + 1}</td>
                <td className="sticky-col sticky-company col-company">{row.company_name ?? '-'}</td>
                <td className="col-website">{row.website ? <a href={row.website} target="_blank" rel="noreferrer" title={row.website}>{renderDomain(row.website)}</a> : '-'}</td>
                <td>{row.facebook_url ? <a href={row.facebook_url} target="_blank" rel="noreferrer" title={row.facebook_url}>{row.facebook_url}</a> : '-'}</td>
                <td>{row.linkedin_url ? <a href={row.linkedin_url} target="_blank" rel="noreferrer" title={row.linkedin_url}>{row.linkedin_url}</a> : '-'}</td>
                <td>{row.country ?? '-'}</td>
                <td className="sticky-col sticky-action">{renderContactAction(row)}</td>
                <td className="col-contact-name">{renderCellValue(row, 'contact_name') || '-'}</td>
                <td className="col-title">{renderCellValue(row, 'contact_title') || '-'}</td>
                <td>{renderCellValue(row, 'linkedin_personal_url') ? <a href={renderCellValue(row, 'linkedin_personal_url')} target="_blank" rel="noreferrer" title={renderCellValue(row, 'linkedin_personal_url')}>{renderCellValue(row, 'linkedin_personal_url')}</a> : '-'}</td>
                <td className="col-email">{renderCellValue(row, 'personal_email') || '-'}</td>
                <td className="col-email">{renderCellValue(row, 'work_email') || '-'}</td>
                <td>{renderCellValue(row, 'phone') || '-'}</td>
                <td>{renderCellValue(row, 'whatsapp') || '-'}</td>
                <td title={(row.potential_contacts?.items || []).join('\n')}>{row.potential_contacts?.items?.length ? row.potential_contacts.items.join(' / ') : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination-bar">
        <div>第 {page} 页 / 共 {totalPages} 页，总计 {total} 家企业</div>
        <div className="pagination-actions">
          <label>
            每页
            <select className="select pagination-select" value={pageSize} onChange={(e) => onPageSizeChange(Number(e.target.value))}>
              {[20, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
          <button className="button secondary" type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
          <button className="button secondary" type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>下一页</button>
        </div>
      </div>
    </section>
  );
}
