export type LeadRow = {
  id: string;
  company_name?: string;
  website?: string;
  facebook_url?: string;
  linkedin_url?: string;
  country?: string;
  contact_status: 'pending' | 'running' | 'done' | 'failed' | string;
  contact_name?: string;
  contact_title?: string;
  linkedin_personal_url?: string;
  personal_email?: string;
  work_email?: string;
  phone?: string;
  whatsapp?: string;
  potential_contacts?: Record<string, string> | null;
};

type Props = {
  rows: LeadRow[];
  selectedIds: string[];
  step2Unlocked: boolean;
  onToggleRow: (leadId: string) => void;
  onToggleAll: () => void;
  onEnrichOne: (leadId: string) => void;
};

export function LeadTable({ rows, selectedIds, step2Unlocked, onToggleRow, onToggleAll, onEnrichOne }: Props) {
  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.includes(row.id));

  const renderContactAction = (row: LeadRow) => {
    if (!step2Unlocked) {
      return <span className="muted-text">待解锁</span>;
    }
    if (row.contact_status === 'running') {
      return <span className="status-inline"><span className="spinner-inline" /> 挖掘中...</span>;
    }
    if (row.contact_status === 'done') {
      return <span className="done-text">✓ 已完成</span>;
    }
    if (row.contact_status === 'failed') {
      return <button className="button secondary" type="button" onClick={() => onEnrichOne(row.id)}>⚠ 重试</button>;
    }
    return <button className="button secondary" type="button" onClick={() => onEnrichOne(row.id)}>查找联系人</button>;
  };

  return (
    <section className="panel">
      <div className="table-wrap unified-table-wrap">
        <table className="lead-table">
          <thead>
            <tr>
              <th className="sticky-col sticky-check"><input type="checkbox" checked={allSelected} onChange={onToggleAll} /></th>
              <th className="sticky-col sticky-index">#</th>
              <th className="sticky-col sticky-company">公司名称</th>
              <th>官网</th>
              <th>Facebook</th>
              <th>LinkedIn</th>
              <th>国家</th>
              <th className="sticky-col sticky-action">联系人操作</th>
              <th>联系人姓名</th>
              <th>职位</th>
              <th>个人LinkedIn</th>
              <th>个人邮箱</th>
              <th>工作邮箱</th>
              <th>电话</th>
              <th>WhatsApp</th>
              <th>潜在联系方式</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id}>
                <td className="sticky-col sticky-check"><input type="checkbox" checked={selectedIds.includes(row.id)} onChange={() => onToggleRow(row.id)} /></td>
                <td className="sticky-col sticky-index">{index + 1}</td>
                <td className="sticky-col sticky-company">{row.company_name ?? '-'}</td>
                <td>{row.website ? <a href={row.website} target="_blank" rel="noreferrer">{row.website}</a> : '-'}</td>
                <td>{row.facebook_url ? <a href={row.facebook_url} target="_blank" rel="noreferrer">{row.facebook_url}</a> : '-'}</td>
                <td>{row.linkedin_url ? <a href={row.linkedin_url} target="_blank" rel="noreferrer">{row.linkedin_url}</a> : '-'}</td>
                <td>{row.country ?? '-'}</td>
                <td className="sticky-col sticky-action">{renderContactAction(row)}</td>
                <td>{row.contact_name || '-'}</td>
                <td>{row.contact_title || '-'}</td>
                <td>{row.linkedin_personal_url ? <a href={row.linkedin_personal_url} target="_blank" rel="noreferrer">{row.linkedin_personal_url}</a> : '-'}</td>
                <td>{row.personal_email || '-'}</td>
                <td>{row.work_email || '-'}</td>
                <td>{row.phone || '-'}</td>
                <td>{row.whatsapp || '-'}</td>
                <td>{row.potential_contacts ? Object.entries(row.potential_contacts).map(([k, v]) => `${k}: ${v}`).join(' / ') : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
