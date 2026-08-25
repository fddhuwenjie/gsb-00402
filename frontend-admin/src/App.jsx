import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './components/AdminLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import SignaturesPage from './pages/SignaturesPage'
import SignatureDetailPage from './pages/SignatureDetailPage'
import AnalysesPage from './pages/AnalysesPage'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import CreateAnalysisPage from './pages/CreateAnalysisPage'
import BaselinesPage from './pages/BaselinesPage'
import BaselineDetailPage from './pages/BaselineDetailPage'
import UsersPage from './pages/UsersPage'

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <PrivateRoute>
              <AdminLayout>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/signatures" element={<SignaturesPage />} />
                  <Route path="/signatures/:id" element={<SignatureDetailPage />} />
                  <Route path="/analyses" element={<AnalysesPage />} />
                  <Route path="/analyses/new" element={<CreateAnalysisPage />} />
                  <Route path="/analyses/:id" element={<AnalysisDetailPage />} />
                  <Route path="/baselines" element={<BaselinesPage />} />
                  <Route path="/baselines/:id" element={<BaselineDetailPage />} />
                  <Route path="/baselines/:id/diffs/:diffId" element={<BaselineDetailPage />} />
                  <Route path="/users" element={<UsersPage />} />
                </Routes>
              </AdminLayout>
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}
