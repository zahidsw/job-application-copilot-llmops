import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { OverviewPage } from './pages/OverviewPage'
import { ProfileVaultPage } from './pages/ProfileVaultPage'
import { RunDetailPage } from './pages/RunDetailPage'
import { SubmitPage } from './pages/SubmitPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="/submit" element={<SubmitPage />} />
          <Route path="/profile" element={<ProfileVaultPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
