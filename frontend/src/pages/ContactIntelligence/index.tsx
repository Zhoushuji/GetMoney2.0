export function ContactIntelligencePage() {
  return (
    <>
      <section className="panel">
        <h2>核心联系人挖掘</h2>
        <p>基于模块一输出执行二阶段联系人 enrichment，严格按白名单 / 黑名单职位规则筛选 CEO、Managing Director、GM 与采购类岗位。</p>
        <div className="kpi-grid">
          <div className="kpi-card"><strong>P1-P4</strong><p>职位优先级</p></div>
          <div className="kpi-card"><strong>Email / Phone / WA</strong><p>联系方式提取</p></div>
          <div className="kpi-card"><strong>0-1</strong><p>置信度评分</p></div>
        </div>
      </section>
      <section className="panel">
        <h3>规则概览</h3>
        <ul>
          <li>仅对模块一已有公司执行 enrichment，不新增或删除 lead。</li>
          <li>白名单：CEO / Founder / Owner / Managing Director / General Manager / GM / Procurement / Purchasing / Sourcing。</li>
          <li>黑名单优先：Director、Sales、Marketing、Support、HR、Accountant、Intern。</li>
        </ul>
      </section>
    </>
  );
}
