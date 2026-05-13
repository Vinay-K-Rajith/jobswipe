import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Navbar from './components/Navbar'
import StudentNavbar from './components/layout/StudentNavbar'
import RecruiterNavbar from './components/layout/RecruiterNavbar'
import { homeForRole } from './config/roles'

// New Admin Pages
import AdminDashboard from './pages/AdminDashboard'
import StudentsPage from './pages/StudentsPage'
import CompaniesPage from './pages/CompaniesPage'
import EligibilityEngine from './pages/EligibilityEngine'
import MLRankedShortlist from './pages/MLRankedShortlist'
import BiasDetection from './pages/BiasDetection'
import JobSwipeFeedReplayPage from './pages/JobSwipeFeedReplay'

import LoginPage from './pages/LoginPage'
import StudentBrowse from './pages/student/StudentBrowse'
import StudentInterested from './pages/student/StudentInterested'
import StudentMatches from './pages/student/StudentMatches'
import StudentProfile from './pages/student/StudentProfile'
import StudentRejectionInsights from './pages/student/StudentRejectionInsights'
import RecruiterBrowse from './pages/recruiter/RecruiterBrowse'
import RecruiterInterested from './pages/recruiter/RecruiterInterested'
import RecruiterMatches from './pages/recruiter/RecruiterMatches'
import RecruiterPostJob from './pages/recruiter/RecruiterPostJob'
import RecruiterProfile from './pages/recruiter/RecruiterProfile'

function AdminRoute({ children }: { children: JSX.Element }) {
  const role = useAuthStore((s) => s.userRole)
  if (!role) return <Navigate to="/login" replace />
  if (role !== 'admin') return <Navigate to={homeForRole(role)} replace />
  return (
    <div>
      <Navbar />
      <div style={{ padding: '24px 0' }}>
        {children}
      </div>
    </div>
  )
}

function StudentRoute({ children }: { children: JSX.Element }) {
  const role = useAuthStore((s) => s.userRole)
  if (!role) return <Navigate to="/login" replace />
  if (role !== 'student') return <Navigate to={homeForRole(role)} replace />
  return (
    <div>
      <StudentNavbar />
      <div style={{ padding: '24px 0' }}>
        {children}
      </div>
    </div>
  )
}

function RecruiterRoute({ children }: { children: JSX.Element }) {
  const role = useAuthStore((s) => s.userRole)
  if (!role) return <Navigate to="/login" replace />
  if (role !== 'recruiter') return <Navigate to={homeForRole(role)} replace />
  return (
    <div>
      <RecruiterNavbar />
      <div style={{ padding: '24px 0' }}>
        {children}
      </div>
    </div>
  )
}

function App() {
  const role = useAuthStore((s) => s.userRole)
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to={homeForRole(role)} replace />} />
        {/* Public Route */}
        <Route path="/login" element={<LoginPage />} />
        
        {/* Admin Routes */}
        <Route path="/dashboard" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
        <Route path="/students" element={<AdminRoute><StudentsPage /></AdminRoute>} />
        <Route path="/companies" element={<AdminRoute><CompaniesPage /></AdminRoute>} />
        <Route path="/eligibility" element={<AdminRoute><EligibilityEngine /></AdminRoute>} />
        <Route path="/ranking" element={<AdminRoute><MLRankedShortlist /></AdminRoute>} />
        <Route path="/bias" element={<AdminRoute><BiasDetection /></AdminRoute>} />
        <Route path="/feed-replay" element={<AdminRoute><JobSwipeFeedReplayPage /></AdminRoute>} />

        {/* Student Routes */}
        <Route path="/student/browse" element={<StudentRoute><StudentBrowse /></StudentRoute>} />
        <Route path="/student/interested" element={<StudentRoute><StudentInterested /></StudentRoute>} />
        <Route path="/student/matches" element={<StudentRoute><StudentMatches /></StudentRoute>} />
        <Route path="/student/rejections" element={<StudentRoute><StudentRejectionInsights /></StudentRoute>} />
        <Route path="/student/profile" element={<StudentRoute><StudentProfile /></StudentRoute>} />

        {/* Recruiter Routes */}
        <Route path="/recruiter/browse" element={<RecruiterRoute><RecruiterBrowse /></RecruiterRoute>} />
        <Route path="/recruiter/interested" element={<RecruiterRoute><RecruiterInterested /></RecruiterRoute>} />
        <Route path="/recruiter/matches" element={<RecruiterRoute><RecruiterMatches /></RecruiterRoute>} />
        <Route path="/recruiter/roles" element={<RecruiterRoute><RecruiterPostJob /></RecruiterRoute>} />
        <Route path="/recruiter/post" element={<Navigate to="/recruiter/roles" replace />} />
        <Route path="/recruiter/profile" element={<RecruiterRoute><RecruiterProfile /></RecruiterRoute>} />
        
        {/* Catch all */}
        <Route path="*" element={<Navigate to={homeForRole(role)} replace />} />
      </Routes>
    </Router>
  )
}

export default App
