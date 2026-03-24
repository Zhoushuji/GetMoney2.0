import { Outlet } from 'react-router-dom';

export function AppLayout() {
  return (
    <div className="single-page-shell">
      <header className="topbar topbar-simple">
        <div className="brand">
          <h1>LeadGen System</h1>
          <p>B2B 智能客户开发平台</p>
        </div>
      </header>
      <main className="single-page-content">
        <Outlet />
      </main>
    </div>
  );
}
