import { ReactNode, useState } from 'react';

import { apiClient } from '../../api/client';

export type LeadReviewAnnotation = {
  verdict: 'correct' | 'incorrect';
  source_path: string;
  note?: string | null;
  updated_at?: string | null;
};

export type FieldProvenance = {
  source_type?: string | null;
  source_url?: string | null;
  extractor?: string | null;
  source_hint?: string | null;
};

export type LeadRow = {
  id: string;
  company_name?: string;
  website?: string;
  facebook_url?: string;
  linkedin_url?: string;
  matched_keywords?: string[] | null;
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
  field_provenance?: Record<string, FieldProvenance> | null;
  review_annotations?: Record<string, LeadReviewAnnotation> | null;
  raw_data?: {
    matched_keywords?: string[] | null;
    target_country?: string | null;
    target_country_code?: string | null;
    company_fit?: {
      category?: string | null;
      evidence?: string[] | null;
      positive_hits?: string[] | null;
      negative_hits?: string[] | null;
    } | null;
    field_provenance?: Record<string, FieldProvenance> | null;
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
  onReviewAnnotationChange: (leadId: string, fieldKey: string, annotation: LeadReviewAnnotation | null) => void;
};

type EditorState = {
  leadId: string;
  fieldKey: string;
  label: string;
  currentValue: string;
  verdict: 'correct' | 'incorrect';
  sourcePath: string;
  note: string;
};

const REVIEWABLE_FIELD_LABELS: Record<string, string> = {
  company_fit: '行业匹配',
  company_name: '公司名称',
  website: '官网',
  facebook_url: 'Facebook',
  linkedin_url: 'LinkedIn',
  country: '识别国家',
  contact_name: '联系人姓名',
  contact_title: '联系人职位',
  linkedin_personal_url: '个人 LinkedIn',
  personal_email: '个人邮箱',
  work_email: '工作邮箱',
  phone: '电话',
  whatsapp: 'WhatsApp',
  potential_contacts: '潜在联系方式',
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

function renderMatchedKeywords(row: LeadRow) {
  const keywords = row.matched_keywords ?? row.raw_data?.matched_keywords ?? [];
  if (keywords.length === 0) return '-';
  return (
    <div className="contact-chip-list" title={keywords.join('\n')}>
      {keywords.slice(0, 4).map((keyword) => <span key={keyword} className="contact-chip">{keyword}</span>)}
      {keywords.length > 4 ? <span className="contact-chip">+{keywords.length - 4}</span> : null}
    </div>
  );
}

function getAnnotation(row: LeadRow, fieldKey: string): LeadReviewAnnotation | undefined {
  return row.review_annotations?.[fieldKey];
}

function getProvenance(row: LeadRow, fieldKey: string): FieldProvenance | undefined {
  return row.field_provenance?.[fieldKey] ?? row.raw_data?.field_provenance?.[fieldKey];
}

function formatCompanyFit(row: LeadRow): string {
  const category = row.raw_data?.company_fit?.category;
  if (!category) return '未判定';
  const labels: Record<string, string> = {
    relevant: '相关',
    marketplace: '电商平台',
    retailer: '零售商',
    classifieds: '分类信息',
    media: '媒体/内容站',
    unrelated: '不相关',
  };
  return labels[category] ?? category;
}

function formatPotentialContacts(row: LeadRow): string {
  const items = row.potential_contacts?.items;
  if (items?.length) return items.join('\n');
  if (row.general_emails?.length) return row.general_emails.join('\n');
  return '';
}

export function LeadTable({
  rows,
  selectedIds,
  step2Unlocked,
  page,
  pageSize,
  total,
  onToggleRow,
  onToggleAll,
  onEnrichDecisionMakers,
  onEnrichGeneralContacts,
  onEnrichAllContacts,
  onPageChange,
  onPageSizeChange,
  onReviewAnnotationChange,
}: Props) {
  const [editorState, setEditorState] = useState<EditorState | null>(null);
  const [editorBusy, setEditorBusy] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
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
      <div className="result-action-stack">
        <button className="mini-action-button" type="button" onClick={() => onEnrichDecisionMakers(row.id)}>关键人</button>
        <button className="mini-action-button" type="button" onClick={() => onEnrichGeneralContacts(row.id)}>联系方式</button>
        <button className="mini-action-button" type="button" onClick={() => onEnrichAllContacts(row.id)}>全部</button>
      </div>
    );
  };

  const openEditor = (row: LeadRow, fieldKey: string, currentValue: string) => {
    const existing = getAnnotation(row, fieldKey);
    const provenance = getProvenance(row, fieldKey);
    setEditorError(null);
    setEditorState({
      leadId: row.id,
      fieldKey,
      label: REVIEWABLE_FIELD_LABELS[fieldKey] ?? fieldKey,
      currentValue,
      verdict: existing?.verdict ?? 'correct',
      sourcePath: existing?.source_path ?? provenance?.source_url ?? '',
      note: existing?.note ?? provenance?.source_hint ?? '',
    });
  };

  const saveReview = async () => {
    if (!editorState) return;
    try {
      setEditorBusy(true);
      setEditorError(null);
      const response = await apiClient.put<LeadReviewAnnotation>(
        `/leads/${editorState.leadId}/reviews/${editorState.fieldKey}`,
        {
          verdict: editorState.verdict,
          source_path: editorState.sourcePath,
          note: editorState.note || null,
        },
      );
      onReviewAnnotationChange(editorState.leadId, editorState.fieldKey, response.data);
      setEditorState(null);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : '审核保存失败');
    } finally {
      setEditorBusy(false);
    }
  };

  const deleteReview = async () => {
    if (!editorState) return;
    try {
      setEditorBusy(true);
      setEditorError(null);
      await apiClient.delete(`/leads/${editorState.leadId}/reviews/${editorState.fieldKey}`);
      onReviewAnnotationChange(editorState.leadId, editorState.fieldKey, null);
      setEditorState(null);
    } catch (error) {
      setEditorError(error instanceof Error ? error.message : '审核删除失败');
    } finally {
      setEditorBusy(false);
    }
  };

  const renderReviewable = (row: LeadRow, fieldKey: string, content: ReactNode, currentValue: string, title?: string) => {
    const annotation = getAnnotation(row, fieldKey);
    const provenance = getProvenance(row, fieldKey);
    const badgeLabel = annotation?.verdict === 'correct' ? '正确' : annotation?.verdict === 'incorrect' ? '错误' : '未审';
    const badgeClass = annotation?.verdict === 'correct'
      ? 'review-badge review-badge-correct'
      : annotation?.verdict === 'incorrect'
        ? 'review-badge review-badge-incorrect'
        : 'review-badge review-badge-pending';
    const autoHint = [provenance?.source_type, provenance?.extractor, provenance?.source_url, provenance?.source_hint]
      .filter(Boolean)
      .join('\n');
    return (
      <div className="reviewable-cell">
        <div className="reviewable-main" title={title}>
          <div className="reviewable-content">{content}</div>
          <button
            type="button"
            className={badgeClass}
            title={autoHint || '点击标记字段是否正确'}
            onClick={() => openEditor(row, fieldKey, currentValue)}
          >
            {badgeLabel}
          </button>
        </div>
        {annotation?.source_path ? <div className="review-source-line">获取路径：{annotation.source_path}</div> : null}
      </div>
    );
  };

  return (
    <>
      <section className="panel">
        <div className="table-wrap unified-table-wrap">
          <table className="lead-table result-table">
            <thead>
              <tr>
                <th className="sticky-col sticky-check"><input type="checkbox" checked={allSelected} onChange={onToggleAll} /></th>
                <th className="sticky-col sticky-index">#</th>
                <th className="sticky-col sticky-company col-company">公司名称</th>
                <th>匹配关键词</th>
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
                      {renderReviewable(
                        row,
                        'company_name',
                        <strong>{row.company_name ?? '-'}</strong>,
                        row.company_name ?? '',
                        row.company_name ?? '-',
                      )}
                      <small>{renderDomain(row.website)}</small>
                      {renderReviewable(
                        row,
                        'company_fit',
                        <small className="muted-text">行业匹配：{formatCompanyFit(row)}</small>,
                        formatCompanyFit(row),
                        row.raw_data?.company_fit?.evidence?.join('\n'),
                      )}
                    </div>
                  </td>
                  <td>{renderMatchedKeywords(row)}</td>
                  <td className="col-website">
                    {renderReviewable(
                      row,
                      'website',
                      row.website ? (
                        <a className="link-pill" href={row.website} target="_blank" rel="noreferrer" title={row.website}>
                          {renderDomain(row.website)}
                        </a>
                      ) : '-',
                      row.website ?? '',
                      row.website,
                    )}
                  </td>
                  <td>
                    {renderReviewable(
                      row,
                      'facebook_url',
                      row.facebook_url ? (
                        <a className="link-pill link-pill-facebook" href={row.facebook_url} target="_blank" rel="noreferrer" title={row.facebook_url}>
                          {renderLinkLabel(row.facebook_url)}
                        </a>
                      ) : '-',
                      row.facebook_url ?? '',
                      row.facebook_url,
                    )}
                  </td>
                  <td>
                    {renderReviewable(
                      row,
                      'linkedin_url',
                      row.linkedin_url ? (
                        <a className="link-pill link-pill-linkedin" href={row.linkedin_url} target="_blank" rel="noreferrer" title={row.linkedin_url}>
                          {renderLinkLabel(row.linkedin_url)}
                        </a>
                      ) : '-',
                      row.linkedin_url ?? '',
                      row.linkedin_url,
                    )}
                  </td>
                  <td title={renderCountryTooltip(row)}>
                    {renderReviewable(
                      row,
                      'country',
                      <div className="location-cell">
                        <strong>{row.country ?? '-'}</strong>
                        <small>{row.continent || '未标注区域'}</small>
                      </div>,
                      row.country ?? '',
                      renderCountryTooltip(row),
                    )}
                  </td>
                  <td className="sticky-col sticky-action">{renderContactAction(row)}</td>
                  <td>{renderStatusTag(row.decision_maker_status)}</td>
                  <td>{renderStatusTag(row.general_contact_status)}</td>
                  <td className="col-contact-name">
                    {renderReviewable(row, 'contact_name', row.contact_name || '-', row.contact_name ?? '', row.contact_name)}
                  </td>
                  <td className="col-title">
                    {renderReviewable(row, 'contact_title', row.contact_title || '-', row.contact_title ?? '', row.contact_title)}
                  </td>
                  <td>
                    {renderReviewable(
                      row,
                      'linkedin_personal_url',
                      row.linkedin_personal_url ? (
                        <a className="link-pill link-pill-linkedin" href={row.linkedin_personal_url} target="_blank" rel="noreferrer" title={row.linkedin_personal_url}>
                          {renderLinkLabel(row.linkedin_personal_url)}
                        </a>
                      ) : '-',
                      row.linkedin_personal_url ?? '',
                      row.linkedin_personal_url,
                    )}
                  </td>
                  <td className="col-email">
                    {renderReviewable(row, 'personal_email', row.personal_email || '-', row.personal_email ?? '', row.personal_email)}
                  </td>
                  <td className="col-email">
                    {renderReviewable(row, 'work_email', row.work_email || '-', row.work_email ?? '', row.work_email)}
                  </td>
                  <td>{renderReviewable(row, 'phone', row.phone || '-', row.phone ?? '', row.phone)}</td>
                  <td>{renderReviewable(row, 'whatsapp', row.whatsapp || '-', row.whatsapp ?? '', row.whatsapp)}</td>
                  <td title={formatPotentialContacts(row)}>
                    {renderReviewable(
                      row,
                      'potential_contacts',
                      row.potential_contacts?.items?.length ? (
                        <div className="contact-chip-list">
                          {row.potential_contacts.items.slice(0, 4).map((item) => <span key={item} className="contact-chip">{item}</span>)}
                          {row.potential_contacts.items.length > 4 ? <span className="contact-chip">+{row.potential_contacts.items.length - 4}</span> : null}
                        </div>
                      ) : row.general_emails?.length ? (
                        <div className="contact-chip-list">
                          {row.general_emails.slice(0, 4).map((item) => <span key={item} className="contact-chip">{item}</span>)}
                          {row.general_emails.length > 4 ? <span className="contact-chip">+{row.general_emails.length - 4}</span> : null}
                        </div>
                      ) : '-',
                      formatPotentialContacts(row),
                      formatPotentialContacts(row),
                    )}
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={19} className="empty-state">
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

      {editorState ? (
        <div className="review-modal-backdrop" role="presentation" onClick={() => !editorBusy && setEditorState(null)}>
          <div className="review-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="review-modal-header">
              <div>
                <h3>字段审核</h3>
                <p className="muted-text">{editorState.label}</p>
              </div>
              <button className="button secondary" type="button" onClick={() => setEditorState(null)} disabled={editorBusy}>关闭</button>
            </div>
            <div className="review-modal-body">
              <label className="field">
                <span>当前值</span>
                <textarea className="input input-textarea" value={editorState.currentValue || '-'} readOnly rows={3} />
              </label>
              <div className="field">
                <span>判定</span>
                <div className="review-verdict-group">
                  <button
                    type="button"
                    className={`button secondary${editorState.verdict === 'correct' ? ' is-selected' : ''}`}
                    onClick={() => setEditorState({ ...editorState, verdict: 'correct' })}
                    disabled={editorBusy}
                  >
                    正确
                  </button>
                  <button
                    type="button"
                    className={`button secondary${editorState.verdict === 'incorrect' ? ' is-selected' : ''}`}
                    onClick={() => setEditorState({ ...editorState, verdict: 'incorrect' })}
                    disabled={editorBusy}
                  >
                    错误
                  </button>
                </div>
              </div>
              <label className="field">
                <span>获取路径</span>
                <input
                  className="input"
                  value={editorState.sourcePath}
                  onChange={(event) => setEditorState({ ...editorState, sourcePath: event.target.value })}
                  placeholder="填写正确来源页面或路径"
                  disabled={editorBusy}
                />
              </label>
              <label className="field">
                <span>备注</span>
                <textarea
                  className="input input-textarea"
                  value={editorState.note}
                  onChange={(event) => setEditorState({ ...editorState, note: event.target.value })}
                  rows={3}
                  placeholder="可补充说明"
                  disabled={editorBusy}
                />
              </label>
              {editorError ? <p className="field-error">{editorError}</p> : null}
            </div>
            <div className="review-modal-footer">
              <button className="button secondary" type="button" onClick={deleteReview} disabled={editorBusy}>清除标记</button>
              <button className="button" type="button" onClick={saveReview} disabled={editorBusy || !editorState.sourcePath.trim()}>
                {editorBusy ? '保存中…' : '保存标记'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
