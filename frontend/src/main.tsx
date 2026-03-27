import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AppLayout } from './components/Layout/AppLayout';
import { LeadDiscoveryPage } from './pages/LeadDiscovery';
import { ContactIntelligencePage } from './pages/ContactIntelligence';
import { OutreachPage } from './pages/Outreach';
import { TestingPage } from './pages/Testing';
import { HistoryPage } from './pages/History';
import { ReviewsPage } from './pages/Reviews';
import './styles/global.css';

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<LeadDiscoveryPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="reviews" element={<ReviewsPage />} />
            <Route path="contacts" element={<ContactIntelligencePage />} />
            <Route path="outreach" element={<OutreachPage />} />
            <Route path="testing" element={<TestingPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
