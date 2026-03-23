import { NavLink, Outlet } from 'react-router-dom';

export function AppLayout() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <h1>LeadGen System</h1>
          <p>B2B 智能客户开发平台</p>
        </div>
        <div className="tag-list">
          <span className="tag">EN</span>
          <span className="tag">中文</span>
        </div>
      </header>
      <aside className="sidebar">
        <nav>
          <NavLink to="/" end>潜在客户发现</NavLink>
          <NavLink to="/contacts">核心联系人挖掘</NavLink>
          <NavLink to="/outreach">客户触达与 BD</NavLink>
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
