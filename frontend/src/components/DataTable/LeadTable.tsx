export type LeadRow = {
  id: string;
  company_name?: string;
  website?: string;
  facebook_url?: string;
  linkedin_url?: string;
  country?: string;
  continent?: string;
  source?: string;
  contact_status: 'pending' | 'running' | 'done' | 'failed' | 'no_data' | 'timeout' | string;
  decision_maker_status?: 'pending' | 'running' | 'done' | 'failed' | 'no_data' | 'timeout' | string;
  general_contact_status?: 'pending' | 'running' | 'done' | 'failed' | 'no_data' | 'timeout' | string;
  contact_name?: string;
  contact_title?: string;
  linkedin_personal_url?: string;
  personal_email?: string;
  work_email?: string;
  phone?: string;
  whatsapp?: string;
  potential_contacts?: { items?: string[] } | null;
  general_emails?: string[] | null;
  raw_data?: {
    target_country?: string | null;
    target_country_code?: string | null;
    country_detection?: {
      status?: string;
      detected_country_name?: string | null;
      target_country_name?: string | null;
      confidence?: number | null;
      mismatch_reason?: string | null;
      evidence?: Array<{ signal?: string; value?: string; weight?: number }>;
    } | null;
  } | null;
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
  onEnrichDecisionMakers: (leadId: string) => void;
  onEnrichGeneralContacts: (leadId: string) => void;
  onEnrichAllContacts: (leadId: string) => void;
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

function renderLinkLabel(url?: string) {
  if (!url) return '-';
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^www\./, '');
    const path = parsed.pathname.replace(/\/+$/, '');
    if (!path || path === '/') return host;
    return `${host}${path.length > 28 ? `${path.slice(0, 28)}...` : path}`;
  } catch {
    return url;
  }
}

function renderCountryTooltip(row: LeadRow) {
  const detection = row.raw_data?.country_detection;
  if (!detection) return undefined;
  const lines = [
    row.raw_data?.target_country ? `目标市场：${row.raw_data.target_country}` : null,
    detection.detected_country_name ? `识别国家：${detection.detected_country_name}` : null,
    detection.confidence != null ? `可信度：${Math.round(detection.confidence * 100)}%` : null,
    ...(detection.evidence ?? []).slice(0, 4).map((item) => `${item.signal || 'evidence'}: ${item.value || '-'}`),
    detection.mismatch_reason ? `说明：${detection.mismatch_reason}` : null,
  ].filter(Boolean);
  return lines.length > 0 ? lines.join('\n') : undefined;
}

export function LeadTable({ rows, selectedIds, step2Unlocked, page, pageSize, total, onToggleRow, onToggleAll, onEnrichDecisionMakers, onEnrichGeneralContacts, onEnrichAllContacts, onPageChange, onPageSizeChange }: Props) {
  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.includes(row.id));
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasRows = rows.length > 0;

  const renderStatusTag = (status?: string) => {
    if (status === 'running') return <span className="status-inline"><span className="spinner-inline" /> 进行中</span>;
    if (status === 'done') return <span className="done-text">✓ 完成</span>;
    if (status === 'no_data') return <span className="no-data-text">— 无数据</span>;
    if (status === 'timeout') return <span className="no-data-text">⏱ 超时</span>;
    if (status === 'failed') return <span className="no-data-text">⚠ 失败</span>;
    return <span className="muted-text">待执行</span>;
  };

  const renderContactAction = (row: LeadRow) => {
    if (!step2Unlocked) return <span className="muted-text">待解锁</span>;
    return (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button className="button secondary" type="button" onClick={() => onEnrichDecisionMakers(row.id)}>查找关键人</button>
        <button className="button secondary" type="button" onClick={() => onEnrichGeneralContacts(row.id)}>抓取潜在联系方式</button>
        <button className="button secondary" type="button" onClick={() => onEnrichAllContacts(row.id)}>全部查找</button>
      </div>
    );
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
              <th>识别国家 / 区域</th>
              <th className="sticky-col sticky-action">联系人操作</th>
              <th>关键人状态</th>
              <th>潜在联系方式状态</th>
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
            {hasRows ? rows.map((row, index) => (
              <tr key={row.id}>
                <td className="sticky-col sticky-check"><input type="checkbox" checked={selectedIds.includes(row.id)} onChange={() => onToggleRow(row.id)} /></td>
                <td className="sticky-col sticky-index">{(page - 1) * pageSize + index + 1}</td>
                <td className="sticky-col sticky-company col-company">
                  <div className="company-cell">
                    <strong>{row.company_name ?? '-'}</strong>
                    <small>{renderDomain(row.website)}</small>
                  </div>
                </td>
                <td className="col-website">
                  {row.website ? (
                    <a className="link-pill" href={row.website} target="_blank" rel="noreferrer" title={row.website}>
                      {renderDomain(row.website)}
                    </a>
                  ) : '-'}
                </td>
                <td>
                  {row.facebook_url ? (
                    <a className="link-pill link-pill-facebook" href={row.facebook_url} target="_blank" rel="noreferrer" title={row.facebook_url}>
                      {renderLinkLabel(row.facebook_url)}
                    </a>
                  ) : '-'}
                </td>
                <td>
                  {row.linkedin_url ? (
                    <a className="link-pill link-pill-linkedin" href={row.linkedin_url} target="_blank" rel="noreferrer" title={row.linkedin_url}>
                      {renderLinkLabel(row.linkedin_url)}
                    </a>
                  ) : '-'}
                </td>
                <td title={renderCountryTooltip(row)}>
                  <div className="location-cell">
                    <strong>{row.country ?? '-'}</strong>
                    <small>{row.continent || '未标注区域'}</small>
                  </div>
                </td>
                <td className="sticky-col sticky-action">{renderContactAction(row)}</td>
                <td>{renderStatusTag(row.decision_maker_status)}</td>
                <td>{renderStatusTag(row.general_contact_status)}</td>
                <td className="col-contact-name">{row.contact_name || '-'}</td>
                <td className="col-title">{row.contact_title || '-'}</td>
                <td>
                  {row.linkedin_personal_url ? (
                    <a className="link-pill link-pill-linkedin" href={row.linkedin_personal_url} target="_blank" rel="noreferrer" title={row.linkedin_personal_url}>
                      {renderLinkLabel(row.linkedin_personal_url)}
                    </a>
                  ) : '-'}
                </td>
                <td className="col-email">{row.personal_email || '-'}</td>
                <td className="col-email">{row.work_email || '-'}</td>
                <td>{row.phone || '-'}</td>
                <td>{row.whatsapp || '-'}</td>
                <td title={(row.potential_contacts?.items || []).join('\n')}>
                  {row.potential_contacts?.items?.length ? (
                    <div className="contact-chip-list">
                      {row.potential_contacts.items.slice(0, 4).map((item) => <span key={item} className="contact-chip">{item}</span>)}
                      {row.potential_contacts.items.length > 4 ? <span className="contact-chip">+{row.potential_contacts.items.length - 4}</span> : null}
                    </div>
                  ) : row.general_emails?.length ? (
                    <div className="contact-chip-list">
                      {row.general_emails.slice(0, 4).map((item) => <span key={item} className="contact-chip">{item}</span>)}
                      {row.general_emails.length > 4 ? <span className="contact-chip">+{row.general_emails.length - 4}</span> : null}
                    </div>
                  ) : '-'}
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan={18} style={{ padding: '28px 16px', textAlign: 'center' }}>
                  <div className="muted-text">暂无结果。先完成搜索，或者切换到演示模式生成一批可操作的示例企业。</div>
                </td>
              </tr>
            )}
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
