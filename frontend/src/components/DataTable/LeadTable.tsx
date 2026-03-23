export type LeadRow = {
  id: string;
  company_name?: string;
  website?: string;
  facebook_url?: string;
  linkedin_url?: string;
  country?: string;
  source?: string;
  contact_status: string;
  contact_name?: string;
  contact_title?: string;
  personal_email?: string;
  work_email?: string;
  phone?: string;
  whatsapp?: string;
  contact_confidence?: number;
};

export function LeadTable({ rows }: { rows: LeadRow[] }) {
  return (
    <section className="panel">
      <h2>结果表格</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th>公司名称</th><th>官网</th><th>Facebook</th><th>LinkedIn</th><th>国家</th><th>来源</th><th>状态</th><th>联系人</th><th>职位</th><th>个人邮箱</th><th>工作邮箱</th><th>电话</th><th>WhatsApp</th><th>置信度</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id}>
                <td>{index + 1}</td>
                <td>{row.company_name}</td>
                <td>{row.website ? <a href={row.website}>{row.website}</a> : '-'}</td>
                <td>{row.facebook_url ? <a href={row.facebook_url}>Link</a> : '-'}</td>
                <td>{row.linkedin_url ? <a href={row.linkedin_url}>Link</a> : '-'}</td>
                <td>{row.country}</td>
                <td>{row.source}</td>
                <td>{row.contact_status}</td>
                <td>{row.contact_name || '-'}</td>
                <td>{row.contact_title || '-'}</td>
                <td>{row.personal_email || '-'}</td>
                <td>{row.work_email || '-'}</td>
                <td>{row.phone || '-'}</td>
                <td>{row.whatsapp || '-'}</td>
                <td>{row.contact_confidence ? `${Math.round(row.contact_confidence * 100)}%` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
