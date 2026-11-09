import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Download, FileSpreadsheet, LayoutTemplate, Sparkles, UploadCloud } from 'lucide-react'
import { Banner, Page } from '../components/ui.jsx'
import { api, fetchBlob } from '../lib/api.js'
import AutoFormViewer from '../components/AutoFormViewer.jsx'

const SECTIONS = { personal: 'Personal information', academic: 'Academic information' }
// While any document is in one of these stages, details are still being read, so the form keeps refreshing itself.
const BUSY = ['ocr_queued', 'ocr_running', 'ocr_done', 'extracting']

export default function AdmissionForm() {
  const navigate = useNavigate()
  const formRef = useRef(null)
  const [form, setForm] = useState(null)
  const [values, setValues] = useState({})
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [hasUploadedForm, setHasUploadedForm] = useState(false)
  const [viewTab, setViewTab] = useState('uploaded_form') // 'uploaded_form' | 'standard_form'

  // preserve = true keeps anything the student has typed but not saved yet, so a refresh never overwrites their edits
  const load = (f, preserve = false) => {
    const before = formRef.current
    formRef.current = f
    setForm(f)
    setValues((prev) => Object.fromEntries(f.fields.map((x) => {
      const old = before?.fields.find((y) => y.key === x.key)
      const dirty = preserve && old && prev[x.key] !== undefined && prev[x.key] !== (old.value ?? '')
      return [x.key, dirty ? prev[x.key] : x.value ?? '']
    })))
  }

  useEffect(() => {
    api('/applications/me/form').then((f) => load(f))
    api('/documents').then((docs) => {
      const found = docs.some((d) => d.slot === 'admission_form')
      setHasUploadedForm(found)
      if (!found) setViewTab('standard_form')
    }).catch(() => {})
  }, [])

  // Fill the form automatically as soon as the documents finish being read.
  useEffect(() => {
    let stop = false, tries = 0, was = false, timer
    const tick = async () => {
      try {
        const docs = await api('/documents')
        const working = docs.some((d) => BUSY.includes(d.status))
        if (working || was) load(await api('/applications/me/form'), true)
        was = working
        setProcessing(working)
        if (working && !stop && ++tries < 40) timer = setTimeout(tick, 3000)
      } catch { /* the form stays usable if a refresh fails */ }
    }
    tick()
    return () => { stop = true; clearTimeout(timer) }
  }, [])

  if (!form) return null
  const changed = Object.fromEntries(form.fields.filter((f) => (values[f.key] ?? '') !== (f.value ?? '')).map((f) => [f.key, values[f.key]]))
  const hasChanges = Object.keys(changed).length > 0
  const missing = form.fields.filter((f) => f.required && !(values[f.key] || '').trim())
  const incorrect = form.fields.filter((f) => f.error && (values[f.key] || '').trim() && !(f.key in changed))
  const unsure = form.fields.filter((f) => f.needs_review && !(f.key in changed) && (values[f.key] || '').trim() && !f.error)

  async function save() {
    setErr(''); setMsg('')
    try { load(await api('/applications/me/form', { method: 'PUT', body: { values: changed } })); setMsg('Saved') } catch (e) { setErr(e.message) }
  }
  async function submit() {
    setBusy(true); setErr('')
    try {
      if (hasChanges) await api('/applications/me/form', { method: 'PUT', body: { values: changed } })
      await api('/applications/me/submit', { method: 'POST', body: { confirm } })
      navigate('/status')
    } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }
  async function download() {
    setDownloading(true); setErr('')
    try {
      if (form.editable && hasChanges) load(await api('/applications/me/form', { method: 'PUT', body: { values: changed } }))  // PDF reflects your edits
      const url = URL.createObjectURL(await fetchBlob('/applications/me/form.pdf?download=true'))
      const a = document.createElement('a')
      a.href = url; a.download = 'edu-sahaya-admission-form.pdf'; a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setErr(e.message) } finally { setDownloading(false) }
  }

  return (
    <Page
      title="Admission Form"
      subtitle={
        hasUploadedForm
          ? "Your blank college form has been automatically filled with details extracted from your documents. Review, edit, and download your completed form."
          : "Filled in automatically from your documents. Check every field, edit anything that is wrong, then confirm."
      }
    >
      {/* Tab Switcher if student uploaded a blank admission form */}
      {hasUploadedForm ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-navy/10 pb-4">
          <div className="inline-flex rounded-xl bg-mist p-1">
            <button
              onClick={() => setViewTab('uploaded_form')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all ${
                viewTab === 'uploaded_form'
                  ? 'bg-white text-navy shadow-sm'
                  : 'text-ink/70 hover:text-navy'
              }`}
            >
              <LayoutTemplate className="h-4 w-4 text-teal" />
              <span>Auto-Filled College Form</span>
              <span className="rounded-full bg-teal/10 px-2 py-0.5 text-xs text-teal">Uploaded</span>
            </button>
            <button
              onClick={() => setViewTab('standard_form')}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all ${
                viewTab === 'standard_form'
                  ? 'bg-white text-navy shadow-sm'
                  : 'text-ink/70 hover:text-navy'
              }`}
            >
              <FileSpreadsheet className="h-4 w-4 text-ink/60" />
              <span>Standard System Form</span>
            </button>
          </div>

          <Link
            to="/upload"
            className="flex items-center gap-1.5 text-xs font-medium text-ink/70 hover:text-navy hover:underline"
          >
            <UploadCloud className="h-3.5 w-3.5" />
            Upload a different form
          </Link>
        </div>
      ) : (
        <div className="rounded-xl border border-teal/20 bg-teal/5 p-4 text-sm text-ink/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Sparkles className="h-5 w-5 text-teal shrink-0" />
            <span>
              <strong>Tip:</strong> Upload your college's blank admission form (PDF or scanned image) to have it filled automatically preserving its exact layout, tables, and format!
            </span>
          </div>
          <Link to="/upload" className="btn-secondary text-xs font-semibold py-1.5 px-3">
            Upload College Form
          </Link>
        </div>
      )}

      {/* View Content */}
      {hasUploadedForm && viewTab === 'uploaded_form' ? (
        <AutoFormViewer onRefresh={() => api('/applications/me/form').then((f) => load(f, true))} />
      ) : (
        <>
          {processing && <Banner>Still reading your documents. This form updates by itself as details are found. Anything you type is kept.</Banner>}
          {!form.editable && <Banner>Your application has been submitted, so the form can no longer be edited.</Banner>}
          {form.editable && !processing && (missing.length > 0 || incorrect.length > 0 || unsure.length > 0) && (
            <Banner>
              Please check the highlighted fields.
              {missing.length > 0 && <> Missing: {missing.map((f) => f.label).join(', ')}.</>}
              {incorrect.length > 0 && <> Incorrect: {incorrect.map((f) => f.label).join(', ')}.</>}
              {unsure.length > 0 && <> Please verify: {unsure.map((f) => f.label).join(', ')}.</>}
            </Banner>
          )}
          {Object.entries(SECTIONS).map(([key, title]) => (
            <div key={key} className="card p-5">
              <h2 className="font-semibold text-navy">{title}</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {form.fields.filter((f) => f.section === key).map((f) => {
                  const empty = f.required && !(values[f.key] || '').trim()
                  const edited = f.key in changed
                  const flag = !edited && (f.needs_review || f.error) || empty
                  const problem = !edited && f.error ? f.error : empty ? `${f.label} is required` : null
                  return (
                    <label key={f.key} className={`block rounded-lg border p-3 text-sm font-medium ${flag ? 'border-amber-400 bg-amber-50' : 'border-navy/10'}`}>
                      {f.label}{f.required && <span className="text-red-700"> *</span>}
                      {f.key === 'address'
                        ? <textarea rows={2} value={values[f.key]} disabled={!form.editable} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} className="mt-1 w-full rounded-lg border border-navy/20 bg-white px-3 py-1.5 text-base" />
                        : <input value={values[f.key]} disabled={!form.editable} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} className="mt-1 w-full rounded-lg border border-navy/20 bg-white px-3 py-1.5 text-base" />}
                      <span className="mt-1 block text-xs font-normal">{f.source === 'documents' ? (f.needs_review ? 'From your documents. Please check' : 'From your documents')
                        : f.source === 'edited' ? 'Edited by you' : f.source === 'account' ? 'From your account' : 'Enter this yourself'}</span>
                      {problem && <span role="alert" className="mt-1 block text-xs font-medium text-red-700">{problem}</span>}
                    </label>
                  )
                })}
              </div>
            </div>
          ))}
          {err && <Banner tone="red">{err}</Banner>}
          {msg && <p role="status" className="text-sm text-[#0f7d79]">{msg}</p>}
          <div className="card space-y-4 p-5">
            {form.editable && (
              <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} className="mt-1" />
                I confirm that these details are correct and match my documents.</label>
            )}
            <div className="flex flex-wrap gap-3">
              {form.editable && <button onClick={save} disabled={!hasChanges} className="btn-ghost">Save changes</button>}
              <button onClick={download} disabled={downloading} className="btn-ghost"><Download size={16} /> {downloading ? 'Preparing...' : 'Download Standard Form'}</button>
              {form.editable && <button onClick={submit} disabled={!confirm || busy} className="btn-primary">{busy ? 'Submitting...' : 'Submit application'}</button>}
            </div>
            {form.editable && <p className="text-xs">Until you submit, the downloaded form is marked as a draft.</p>}
          </div>
        </>
      )}
    </Page>
  )
}
