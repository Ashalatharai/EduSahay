import { useEffect, useRef, useState } from 'react'
import DocumentCard from '../components/DocumentCard.jsx'
import { api, fetchBlob, uploadFile } from '../lib/api.js'

const SLOTS = [
  ['aadhaar', '1. Aadhaar Card'],
  ['sslc', '2. SSLC Marks Card'],
  ['puc', '3. PUC Marks Card'],
  ['admission_form', '4. Blank College Admission Form (PDF or Image)'],
]
const MAX_MB = 10

function checkFile(file) {
  if (!/\.(jpe?g|png|pdf)$/i.test(file.name)) return 'Unsupported file type. Upload a JPG, PNG or PDF.'
  if (file.size > MAX_MB * 1024 * 1024) return `File is larger than ${MAX_MB} MB.`
  return null
}

export default function Upload() {
  const [docs, setDocs] = useState({})
  const [previews, setPreviews] = useState({})
  const [progress, setProgress] = useState({})
  const [errors, setErrors] = useState({})
  const [locked, setLocked] = useState(false)
  const [loadError, setLoadError] = useState('')
  const urls = useRef([])

  const put = (setter, slot, value) => setter((s) => ({ ...s, [slot]: value }))

  async function showPreview(doc) {
    if (!doc.mime_type.startsWith('image/')) return put(setPreviews, doc.slot, null)
    const url = URL.createObjectURL(await fetchBlob(`/documents/${doc.id}/file`))
    urls.current.push(url)
    put(setPreviews, doc.slot, url)
  }

  useEffect(() => {
    Promise.all([api('/documents'), api('/applications/me')])
      .then(([list, app]) => {
        setDocs(Object.fromEntries(list.map((d) => [d.slot, d])))
        setLocked(['submitted', 'approved'].includes(app.status))
        list.forEach((d) => showPreview(d).catch(() => {}))
      })
      .catch((e) => setLoadError(e.message))
    return () => urls.current.forEach(URL.revokeObjectURL)
  }, [])

  async function pick(slot, file) {
    put(setErrors, slot, null)
    const problem = checkFile(file)
    if (problem) return put(setErrors, slot, problem)
    put(setProgress, slot, 0)
    try {
      const doc = await uploadFile(`/documents/${slot}`, file, (p) => put(setProgress, slot, p))
      put(setDocs, slot, doc)
      put(setPreviews, slot, null)
      await showPreview(doc)
    } catch (e) {
      put(setErrors, slot, e.message)
    } finally {
      put(setProgress, slot, null)
    }
  }

  async function remove(slot) {
    if (!window.confirm('Remove this document?')) return
    try {
      await api(`/documents/${docs[slot].id}`, { method: 'DELETE' })
      put(setDocs, slot, null)
      put(setPreviews, slot, null)
    } catch (e) {
      put(setErrors, slot, e.message)
    }
  }

  async function viewPdf(slot) {
    try {
      window.open(URL.createObjectURL(await fetchBlob(`/documents/${docs[slot].id}/file`)), '_blank')
    } catch (e) {
      put(setErrors, slot, e.message)
    }
  }

  // keep refreshing while the server is still reading documents in the background
  const busy = Object.values(docs).some((d) => d && ['ocr_queued', 'ocr_running', 'extracting'].includes(d.status))
  useEffect(() => {
    if (!busy) return
    const t = setInterval(() => {
      api('/documents').then((list) => setDocs(Object.fromEntries(list.map((d) => [d.slot, d])))).catch(() => {})
    }, 2000)
    return () => clearInterval(t)
  }, [busy])

  const count = SLOTS.filter(([s]) => docs[s]).length
  return (
    <section className="mx-auto max-w-6xl px-5 py-12">
      <h1 className="text-3xl font-bold text-navy">Upload documents & admission form</h1>
      <p className="mt-2 text-ink/80">{count} of 4 uploaded{count === 4 && '. All supporting documents and admission form are in.'}</p>
      <div className="mt-3 rounded-lg border border-teal/20 bg-teal/5 p-3 text-xs text-navy">
        <span className="font-semibold">Automatic Form Filling Workflow:</span> Upload supporting documents + blank admission form &rarr; Details extracted automatically &rarr; Form filled preserving original layout &rarr; Review & edit &rarr; Download completed form.
      </div>
      {loadError && <p role="alert" className="mt-4 text-red-700">{loadError}</p>}
      {locked && <p className="mt-4 rounded-lg bg-mist px-4 py-3 text-sm">Your application is submitted, so documents can no longer be changed.</p>}
      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {SLOTS.map(([slot, title]) => (
          <DocumentCard key={slot} title={title} doc={docs[slot]} preview={previews[slot]} progress={progress[slot]}
            error={errors[slot]} locked={locked} onPick={(f) => pick(slot, f)}
            onDelete={() => remove(slot)} onViewPdf={() => viewPdf(slot)} />
        ))}
      </div>
    </section>
  )
}
