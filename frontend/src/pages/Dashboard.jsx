import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApplicationSteps, Badge, CheckBadge, Page } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { api } from '../lib/api.js'

export default function Dashboard() {
  const { user } = useAuth()
  const [app, setApp] = useState(null)
  const [docs, setDocs] = useState([])
  const [val, setVal] = useState(null)
  useEffect(() => {
    api('/applications/me').then(setApp)
    api('/documents').then(setDocs)
    api('/applications/me/validation').then(setVal)
  }, [])
  if (!app) return null
  const next = { documents_not_uploaded: ['/upload', 'Upload documents'], documents_uploaded: ['/review', 'Review extracted details'],
    processing: ['/results', 'See processing'], review_required: ['/form', 'Open admission form'], correction_requested: ['/form', 'Make corrections'],
    submitted: ['/status', 'View status'], approved: ['/profile-preview', 'Download admission profile'] }[app.status]
  return (
    <Page title={`Welcome, ${user.full_name.split(' ')[0]}`} subtitle="Your admission application at a glance.">
      <div className="card p-6"><ApplicationSteps status={app.status} /></div>
      <div className="grid gap-5 md:grid-cols-3">
        <div className="card p-5"><h2 className="font-semibold text-navy">Application</h2><div className="mt-3"><Badge status={app.status} /></div>
          <Link to={next[0]} className="btn-primary mt-5">{next[1]}</Link></div>
        <div className="card p-5"><h2 className="font-semibold text-navy">Documents</h2><p className="mt-3 text-3xl font-bold">{docs.length}<span className="text-base font-normal"> of 3 uploaded</span></p>
          <Link to="/upload" className="mt-3 inline-block text-sm font-semibold text-navy underline">Manage documents</Link></div>
        <div className="card p-5"><h2 className="font-semibold text-navy">Checks</h2>
          {val && val.results.length ? <div className="mt-3 flex flex-wrap gap-2">{Object.entries(val.summary).filter(([, n]) => n).map(([s, n]) => <span key={s} className="flex items-center gap-1 text-sm"><CheckBadge status={s} />{n}</span>)}</div>
            : <p className="mt-3 text-sm">Run the checks from the Review page.</p>}
          <Link to="/review" className="mt-3 inline-block text-sm font-semibold text-navy underline">Review details</Link></div>
      </div>
    </Page>
  )
}
