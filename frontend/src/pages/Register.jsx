import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthCard, { Field } from '../components/AuthCard.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ full_name: '', email: '', password: '', consent: false })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await register(form)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Create your account" subtitle="Start your admission application." error={error}>
      <form onSubmit={submit}>
        <Field label="Full name" value={form.full_name} onChange={set('full_name')} required autoComplete="name" />
        <Field label="Email" type="email" value={form.email} onChange={set('email')} required autoComplete="email" />
        <Field label="Password (8+ characters)" type="password" value={form.password} onChange={set('password')}
          required minLength={8} autoComplete="new-password" />
        <label className="mt-5 flex items-start gap-2 text-sm">
          <input type="checkbox" checked={form.consent} onChange={set('consent')} required className="mt-1" />
          I agree to Edu Sahaya processing my uploaded documents to fill my admission form.
        </label>
        <button className="btn-primary mt-6 w-full" disabled={busy}>{busy ? 'Creating account...' : 'Create account'}</button>
      </form>
      <p className="mt-5 text-sm">Already registered? <Link to="/login" className="font-semibold text-navy underline">Log in</Link></p>
    </AuthCard>
  )
}
