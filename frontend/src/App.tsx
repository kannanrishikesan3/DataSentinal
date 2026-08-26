import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/components/layout/app-shell'
import { ProtectedRoute } from '@/components/protected-route'
import { Toaster } from '@/components/ui/toast'
import { AuthProvider } from '@/lib/auth-context'
import { AuditLogsPage } from '@/pages/audit-logs'
import { EndpointsPage } from '@/pages/endpoints'
import { FindingsPage } from '@/pages/findings'
import { LoginPage } from '@/pages/login'
import { OverviewPage } from '@/pages/overview'
import { PiiExplorerPage } from '@/pages/pii-explorer'
import { PoliciesPage } from '@/pages/policies'
import { ReportsPage } from '@/pages/reports'
import { ScansPage } from '@/pages/scans'
import { SecretsPage } from '@/pages/secrets'
import { SettingsPage } from '@/pages/settings'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 10_000 } },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route index element={<OverviewPage />} />
              <Route path="/endpoints" element={<EndpointsPage />} />
              <Route path="/scans" element={<ScansPage />} />
              <Route path="/findings" element={<FindingsPage />} />
              <Route path="/pii-explorer" element={<PiiExplorerPage />} />
              <Route path="/secrets" element={<SecretsPage />} />
              <Route path="/policies" element={<PoliciesPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/audit-logs" element={<AuditLogsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
