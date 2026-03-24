import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AdminApplications } from './pages/AdminApplications'
import { AdminDashboard } from './pages/AdminDashboard'
import { AdminForceAssign } from './pages/AdminForceAssign'
import { AdminLogin } from './pages/AdminLogin'
import { AdminUnassigned } from './pages/AdminUnassigned'
import { StudentClubs } from './pages/StudentClubs'
import { StudentResult } from './pages/StudentResult'
import { StudentVerify } from './pages/StudentVerify'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StudentVerify />} />
        <Route path="/clubs" element={<StudentClubs />} />
        <Route path="/result" element={<StudentResult />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/apps" element={<AdminApplications />} />
        <Route path="/admin/unassigned" element={<AdminUnassigned />} />
        <Route path="/admin/force" element={<AdminForceAssign />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
