import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';

import { AppLayout } from './components/Layout/AppLayout';
import { LeadDiscoveryPage } from './pages/LeadDiscovery';
import { ContactIntelligencePage } from './pages/ContactIntelligence';
import { OutreachPage } from './pages/Outreach';
import { TestingPage } from './pages/Testing';
import { HistoryPage } from './pages/History';
import { ReviewsPage } from './pages/Reviews';
import { LoginPage } from './pages/Login';
import { AdminUsersPage } from './pages/AdminUsers';
import { AdminTasksPage } from './pages/AdminTasks';
import { useAuthStore } from './stores/useAuthStore';
import './styles/global.css';

const queryClient = new QueryClient();

function RequireAuth() {
  const { token, user, hydrated, authLoading, bootstrap } = useAuthStore();

  React.useEffect(() => {
    if (!hydrated || !token) return;
    void bootstrap();
  }, [hydrated, token]);

  if (!hydrated || (token && authLoading && !user)) {
    return <div className="auth-shell"><section className="auth-card"><p className="muted-text">正在加载账号信息…</p></section></div>;
  }
  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

function RequireAdmin() {
  const user = useAuthStore((state) => state.user);
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'admin') return <Navigate to="/" replace />;
  return <Outlet />;
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<LeadDiscoveryPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="reviews" element={<ReviewsPage />} />
              <Route path="contacts" element={<ContactIntelligencePage />} />
              <Route element={<RequireAdmin />}>
                <Route path="outreach" element={<OutreachPage />} />
                <Route path="testing" element={<TestingPage />} />
                <Route path="admin/users" element={<AdminUsersPage />} />
                <Route path="admin/tasks" element={<AdminTasksPage />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
