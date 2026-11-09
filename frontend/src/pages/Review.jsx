import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Banner, CheckBadge, Page, PrototypeNote } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { DOC_NAMES, checkLabel, fieldLabel } from '../lib/labels.js'

function FieldRow({ docId, f, onSaved }) {
  const [value, setValue] = useState(f.value ?? '')
  const [err, setErr] = useState('')
  async function save() {
    if (value === (f.value ?? '')) return
    try { onSaved(await api(`/documents/${docId}/fields/${f.field_name}`, { method: 'PUT', body: { value } })); setErr('') } catch (e) { setErr(e.message) }
  }
  const flagged = f.needs_review
  return (
    <div className={`rounded-lg border p-3 ${flagged ? 'border-amber-400 bg-amber-50' : 'border-navy/10'}`}>
      <label className="block text-sm font-medium">{fieldLabel(f.field_name)}
        <input value={value} onChange={(e) => setValue(e.target.value)} onBlur={save} className="mt-1 w-full rounded-lg border border-navy/20 bg-white px-3 py-1.5 text-base" />
      </label>
      <p className="mt-1 text-xs">{f.source === 'manual' ? 'Edited by you' : flagged ? (f.value ? `Needs review (${Math.round((f.confidence || 0) * 100)}% confidence)` : 'Not found. Please enter it') : `Confidence ${Math.round((f.confidence || 0) * 100)}%`}</p>
      {err && <p role="alert" className="text-xs text-red-700">{err}</p>}
    </div>
  )
}

function DocFields({ doc }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (doc.slot !== 'admission_form') {
      api(`/documents/${doc.id}/fields`).then(setData)
    }
  }, [doc.id, doc.status, doc.slot])

  if (doc.slot === 'admission_form') {
    return (
      <div className="card p-5 border border-teal/20 bg-teal/5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-navy">{DOC_NAMES[doc.slot]}</h2>
            <p className="mt-1 text-sm text-ink/80">
              Form field layouts and bounding regions have been detected. Your extracted details from Aadhaar, SSLC, and PUC are automatically filled into this original document layout.
            </p>
          </div>
          <Link to="/form" className="btn-secondary text-sm">
            View Auto-Filled Form &rarr;
          </Link>
        </div>
      </div>
    )
  }

  if (!data) return null
  const update = (u) => setData({ ...data, fields: data.fields.map((f) => (f.field_name === u.field_name ? u : f)) })
  return (
    <div className="card p-5">
      <h2 className="font-semibold text-navy">{DOC_NAMES[doc.slot]}</h2>
      {data.fields.length ? <>
        <div className="mt-3"><PrototypeNote model={data.model} /></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">{data.fields.map((f) => <FieldRow key={f.field_name} docId={doc.id} f={f} onSaved={update} />)}</div>
      </> : <p className="mt-2 text-sm">No details were extracted automatically from this document. You can enter them in the admission form.</p>}
    </div>
  )
}

export default function Review() {
  const [docs, setDocs] = useState([])
  const [val, setVal] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api('/documents').then(setDocs); api('/applications/me/validation').then(setVal) }, [])
  async function check() { setBusy(true); try { setVal(await api('/applications/me/validate', { method: 'POST' })) } finally { setBusy(false) } }
  return (
    <Page title="Review extracted information" subtitle="Check each value against your document. Edits save when you leave a field.">
      <div className="card p-5">
        <div className="flex items-center justify-between gap-2"><h2 className="font-semibold text-navy">Document checks</h2>
          <button onClick={check} disabled={busy} className="btn-ghost">{busy ? 'Checking...' : 'Check again'}</button></div>
        {val?.results.length ? <ul className="mt-4 divide-y divide-navy/5">{val.results.map((r) => (
          <li key={r.field_name} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
            <span><span className="font-medium capitalize">{checkLabel(r.field_name)}</span><span className="block text-ink/70">{r.detail}</span></span><CheckBadge status={r.status} /></li>))}</ul>
          : <p className="mt-3 text-sm">Press "Check again" to compare your documents.</p>}
        {val && <p className="mt-4 text-xs text-ink/70">{val.disclaimer}</p>}
      </div>
      {docs.map((d) => <DocFields key={d.id} doc={d} />)}
      {docs.length > 0 && <Link to="/form" className="btn-primary">Continue to admission form</Link>}
    </Page>
  )
}
