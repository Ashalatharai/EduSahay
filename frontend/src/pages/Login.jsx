import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AuthCard, { Field } from '../components/AuthCard.jsx'
import { homeFor } from '../components/ProtectedRoute.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await login(form.email, form.password)
      navigate(location.state?.from || homeFor(user), { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Log in" subtitle="Students and administrators sign in here." error={error}>
      <form onSubmit={submit}>
        <Field label="Email" type="email" value={form.email} required autoComplete="email"
          onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Field label="Password" type="password" value={form.password} required autoComplete="current-password"
          onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? 'Logging in...' : 'Log in'}</button>
      </form>
      <p className="mt-5 text-sm">New here? <Link to="/register" className="font-semibold text-navy underline">Create an account</Link></p>
    </AuthCard>
  )
}
