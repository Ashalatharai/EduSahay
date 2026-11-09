import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApplicationSteps, Badge, Banner, Page } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { fmtDate } from '../lib/labels.js'

export default function Status() {
  const [app, setApp] = useState(null)
  useEffect(() => { api('/applications/me').then(setApp) }, [])
  if (!app) return null
  return (
    <Page title="Application status">
      <div className="card space-y-5 p-6">
        <ApplicationSteps status={app.status} />
        <div className="flex flex-wrap items-center gap-4 text-sm"><Badge status={app.status} /><span>Submitted: {fmtDate(app.submitted_at)}</span></div>
        {app.status === 'correction_requested' && (
          <div className="space-y-3"><Banner>The administrator asked for corrections: {app.review_comment}</Banner><Link to="/form" className="btn-primary">Edit and resubmit</Link></div>)}
        {['submitted', 'approved'].includes(app.status) && <div className="flex flex-wrap gap-3"><Link to="/form" className="btn-ghost">Download admission form</Link><Link to="/profile-preview" className="btn-ghost">Admission profile (PDF)</Link></div>}
        {!['submitted', 'approved', 'correction_requested'].includes(app.status) && <Link to="/form" className="btn-primary">Continue your application</Link>}
      </div>
    </Page>
  )
}
