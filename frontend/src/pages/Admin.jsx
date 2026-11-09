import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Badge, Page } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { APP_STATUS, fmtDate } from '../lib/labels.js'

const STATS = [['total_applications', 'Total applications'], ['documents_uploaded', 'Documents uploaded'], ['pending_review', 'Pending review'],
  ['needs_correction', 'Need correction'], ['approved', 'Approved']]

export default function Admin() {
  const [stats, setStats] = useState(null)
  const [rows, setRows] = useState([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  useEffect(() => { api('/admin/stats').then(setStats) }, [])
  useEffect(() => {
    const t = setTimeout(() => api(`/admin/applications?q=${encodeURIComponent(q)}${status ? `&status_filter=${status}` : ''}`).then(setRows), 250)
    return () => clearTimeout(t)
  }, [q, status])
  return (
    <Page title="Applications" subtitle="Review submitted applications.">
      <div className="grid gap-4 sm:grid-cols-5">{STATS.map(([k, label]) => (
        <div key={k} className="card p-4"><p className="text-sm text-ink/70">{label}</p><p className="mt-1 text-2xl font-bold text-navy">{stats?.[k] ?? '-'}</p></div>))}</div>
      <div className="flex flex-wrap gap-3">
        <input aria-label="Search" placeholder="Search by name, email or register number" value={q} onChange={(e) => setQ(e.target.value)} className="min-w-64 flex-1 rounded-lg border border-navy/20 px-3 py-2" />
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-navy/20 px-3 py-2">
          <option value="">All statuses</option>{Object.entries(APP_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-left text-sm"><thead className="bg-mist text-navy"><tr>{['Student', 'Status', 'SSLC reg.', 'PUC reg.', 'Submitted', 'Duplicates', ''].map((h) => <th key={h} className="px-4 py-3 font-semibold">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-navy/5">{rows.map((r) => (
            <tr key={r.id}><td className="px-4 py-3"><p className="font-medium">{r.student_name}</p><p className="text-xs text-ink/70">{r.email}</p></td>
              <td className="px-4 py-3"><Badge status={r.status} /></td><td className="px-4 py-3">{r.sslc_register_number || '-'}</td><td className="px-4 py-3">{r.puc_register_number || '-'}</td>
              <td className="px-4 py-3">{fmtDate(r.submitted_at)}</td>
              <td className="px-4 py-3">{r.possible_duplicates ? <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">{r.possible_duplicates} possible</span> : '-'}</td>
              <td className="px-4 py-3"><Link to={`/admin/applications/${r.id}`} className="font-semibold text-navy underline">Open</Link></td></tr>))}
            {!rows.length && <tr><td colSpan={7} className="px-4 py-6 text-center">No applications found.</td></tr>}</tbody></table>
      </div>
    </Page>
  )
}
