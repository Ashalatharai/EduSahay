import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Badge, Banner, CheckBadge, Page } from '../components/ui.jsx'
import { api, fetchBlob } from '../lib/api.js'
import { DOC_NAMES, checkLabel, fieldLabel, fmtDate } from '../lib/labels.js'

export default function AdminApplication() {
  const { id } = useParams()
  const [d, setD] = useState(null)
  const [comments, setComments] = useState('')
  const [err, setErr] = useState('')
  const load = () => api(`/admin/applications/${id}`).then(setD)
  useEffect(() => { load() }, [id])
  if (!d) return null
  const open = async (path) => window.open(URL.createObjectURL(await fetchBlob(path)), '_blank')
  const decide = async (decision) => {
    setErr('')
    try { await api(`/admin/applications/${id}/review`, { method: 'POST', body: { decision, comments } }); setComments(''); load() } catch (e) { setErr(e.message) }
  }
  return (
    <Page title={d.student.name} subtitle={`${d.student.email}  |  Submitted ${fmtDate(d.submitted_at)}`}>
      <div className="flex flex-wrap items-center gap-3"><Link to="/admin" className="text-sm font-semibold text-navy underline">All applications</Link><Badge status={d.status} />
        {['submitted', 'approved'].includes(d.status) && <button onClick={() => open(`/admin/applications/${id}/profile.pdf`)} className="btn-ghost">Admission profile (PDF)</button>}</div>
      {d.duplicates.length > 0 && (
        <div className="card space-y-3 p-5"><Banner>Possible duplicate applications. Review them manually; nothing is rejected automatically.</Banner>
          {d.duplicates.map((x) => (
            <div key={x.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span><Link to={`/admin/applications/${x.other_application_id}`} className="font-medium text-navy underline">{x.other_student}</Link> ({Math.round(x.similarity * 100)}% similar): {x.reasons.join(', ')}</span>
              {x.reviewed ? <span className="text-ink/60">Reviewed</span> : <button className="btn-ghost !py-1" onClick={() => api(`/admin/duplicates/${x.id}/review`, { method: 'POST' }).then(load)}>Mark reviewed</button>}</div>))}</div>)}
      <div className="card p-5"><h2 className="font-semibold text-navy">Application form</h2>
        <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">{d.form.map((f) => <div key={f.key}><dt className="text-ink/60">{f.label}</dt><dd className="font-medium">{f.value || '-'}</dd></div>)}</dl></div>
      <div className="card p-5"><h2 className="font-semibold text-navy">Validation results</h2>
        <ul className="mt-3 divide-y divide-navy/5 text-sm">{d.validation.results.map((r) => <li key={r.field_name} className="flex items-center justify-between gap-2 py-2"><span><span className="font-medium capitalize">{checkLabel(r.field_name)}</span> <span className="text-ink/70">{r.detail}</span></span><CheckBadge status={r.status} /></li>)}
          {!d.validation.results.length && <li className="py-2">No checks recorded.</li>}</ul><p className="mt-3 text-xs text-ink/70">{d.validation.disclaimer}</p></div>
      {d.documents.map((doc) => (
        <div key={doc.id} className="card p-5">
          <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold text-navy">{DOC_NAMES[doc.slot]}</h2>
            <button className="btn-ghost !py-1" onClick={() => open(`/documents/${doc.id}/file`)}>View document</button></div>
          <p className="mt-1 text-sm">{doc.classification ? `Detected: ${DOC_NAMES[doc.classification.label] || 'Other'} (${Math.round(doc.classification.confidence * 100)}%)` : 'Not classified'}</p>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">{doc.fields.map((f) => (
            <div key={f.field_name} className={f.needs_review ? 'rounded bg-amber-50 px-2' : 'px-2'}><dt className="text-ink/60">{fieldLabel(f.field_name)}{f.confidence != null && ` (${Math.round(f.confidence * 100)}%)`}</dt><dd className="font-medium">{f.value || '-'}</dd></div>))}</dl></div>))}
      <div className="card space-y-4 p-5"><h2 className="font-semibold text-navy">Decision</h2>
        {d.history.map((h, i) => <p key={i} className="text-sm"><span className="font-medium">{h.decision === 'approved' ? 'Approved' : 'Correction requested'}</span> by {h.admin} on {fmtDate(h.created_at)}{h.comments && `: ${h.comments}`}</p>)}
        {d.status === 'submitted' ? <>
          <textarea aria-label="Comments" rows={3} value={comments} onChange={(e) => setComments(e.target.value)} placeholder="Comments (required when requesting corrections)" className="w-full rounded-lg border border-navy/20 px-3 py-2" />
          {err && <Banner tone="red">{err}</Banner>}
          <div className="flex gap-3"><button className="btn-primary" onClick={() => decide('approved')}>Approve</button><button className="btn-ghost" onClick={() => decide('correction_requested')}>Request corrections</button></div></>
          : <p className="text-sm">Only submitted applications can be reviewed.</p>}</div>
    </Page>
  )
}
