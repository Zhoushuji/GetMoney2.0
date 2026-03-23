export type LeadRow = {
  id: string;
  company_name?: string;
  website?: string;
  facebook_url?: string;
  linkedin_url?: string;
  country?: string;
  contact_status: string;
  contact_name?: string;
  contact_title?: string;
  personal_email?: string;
  work_email?: string;
  phone?: string;
  whatsapp?: string;
};

export function LeadTable({ rows }: { rows: LeadRow[] }) {
  return (
    <section className="panel">
      <h2>结果表格</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th>公司名称</th><th>官网</th><th>Facebook</th><th>LinkedIn</th><th>国家</th><th>状态</th><th>联系人</th><th>职位</th><th>个人邮箱</th><th>工作邮箱</th><th>电话</th><th>WhatsApp</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id}>
                <td>{index + 1}</td>
                <td>{row.company_name ?? '-'}</td>
                <td>{row.website ? <a href={row.website} target="_blank" rel="noreferrer">{row.website}</a> : '-'}</td>
                <td>{row.facebook_url ? <a href={row.facebook_url} target="_blank" rel="noreferrer">Link</a> : '-'}</td>
                <td>{row.linkedin_url ? <a href={row.linkedin_url} target="_blank" rel="noreferrer">Link</a> : '-'}</td>
                <td>{row.country ?? '-'}</td>
                <td>{row.contact_status}</td>
                <td>{row.contact_name || '-'}</td>
                <td>{row.contact_title || '-'}</td>
                <td>{row.personal_email || '-'}</td>
                <td>{row.work_email || '-'}</td>
                <td>{row.phone || '-'}</td>
                <td>{row.whatsapp || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
