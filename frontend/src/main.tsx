import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.tsx'
import { DashboardPage } from './pages/DashboardPage.tsx'
import { OpportunitiesPage } from './pages/OpportunitiesPage.tsx'
import { EmailQueuePage } from './pages/EmailQueuePage.tsx'
import { ListingsPage } from './pages/ListingsPage.tsx'
import { BrokerDetailPage } from './pages/BrokerDetailPage.tsx'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<App />}>
            <Route index element={<DashboardPage />} />
            <Route path="opportunities" element={<OpportunitiesPage />} />
            <Route path="emails" element={<EmailQueuePage />} />
            <Route path="listings" element={<ListingsPage />} />
            <Route path="brokers/:id" element={<BrokerDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
