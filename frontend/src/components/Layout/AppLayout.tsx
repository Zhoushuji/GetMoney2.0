import { NavLink, Outlet } from 'react-router-dom';

const navigationItems = [
  { to: '/', label: '潜在客户发现', end: true },
  { to: '/contacts', label: '核心联系人挖掘' },
  { to: '/outreach', label: '客户触达与拓展' },
  { to: '/testing', label: '功能测试' },
];

export function AppLayout() {
  return (
    <div className="single-page-shell">
      <header className="topbar topbar-simple">
        <div className="brand">
          <h1>LeadGen System</h1>
          <p>B2B 智能客户开发平台</p>
        </div>
        <nav className="topbar-nav" aria-label="Primary">
          {navigationItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="single-page-content">
        <Outlet />
      </main>
    </div>
  );
}
