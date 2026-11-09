import { Routes, Route } from 'react-router-dom'
import PublicLayout from './layouts/PublicLayout.jsx'
import StudentLayout from './layouts/StudentLayout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Upload from './pages/Upload.jsx'
import Results from './pages/Results.jsx'
import Review from './pages/Review.jsx'
import AdmissionForm from './pages/AdmissionForm.jsx'
import Status from './pages/Status.jsx'
import ProfilePreview from './pages/ProfilePreview.jsx'
import Admin from './pages/Admin.jsx'
import AdminApplication from './pages/AdminApplication.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<Landing />} />
        <Route path="register" element={<Register />} />
        <Route path="login" element={<Login />} />
        <Route element={<ProtectedRoute role="student" />}>
          <Route element={<StudentLayout />}>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="upload" element={<Upload />} />
            <Route path="results" element={<Results />} />
            <Route path="review" element={<Review />} />
            <Route path="form" element={<AdmissionForm />} />
            <Route path="status" element={<Status />} />
            <Route path="profile-preview" element={<ProfilePreview />} />
          </Route>
        </Route>
        <Route element={<ProtectedRoute role="admin" />}>
          <Route path="admin" element={<Admin />} />
          <Route path="admin/applications/:id" element={<AdminApplication />} />
        </Route>
      </Route>
    </Routes>
  )
}
