import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Login from './pages/Login'
import Landing from './pages/Landing'
import EngineerDashboard from './pages/EngineerDashboard'
import EngineerRequestForm from './pages/EngineerRequestForm'
import AIProcessing from './pages/AIProcessing'
import OfficerDashboard from './pages/OfficerDashboard'
import OfficerReview from './pages/OfficerReview'
import LiveOps from './pages/LiveOps'

function ProtectedRoute({ children, role }: { children: React.ReactNode; role?: string }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center bg-gray-50"><div className="text-gray-500">Loading...</div></div>
  if (!user) return <Navigate to="/login" replace />
  if (role && user.role !== role) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  const { user } = useAuth()

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/engineer" element={<ProtectedRoute role="engineer"><EngineerDashboard /></ProtectedRoute>} />
        <Route path="/engineer/new" element={<ProtectedRoute role="engineer"><EngineerRequestForm /></ProtectedRoute>} />
        <Route path="/engineer/request/:id" element={<ProtectedRoute role="engineer"><AIProcessing /></ProtectedRoute>} />
        <Route path="/officer" element={<ProtectedRoute role="officer"><OfficerDashboard /></ProtectedRoute>} />
        <Route path="/officer/review/:id" element={<ProtectedRoute role="officer"><OfficerReview /></ProtectedRoute>} />
        <Route path="/live" element={<ProtectedRoute><LiveOps /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to={user?.role === 'officer' ? '/officer' : user?.role === 'engineer' ? '/engineer' : '/'} replace />} />
      </Routes>
    </BrowserRouter>
  )
}
