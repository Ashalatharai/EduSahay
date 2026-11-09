import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Banner, Page } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { DOC_NAMES } from '../lib/labels.js'

const STAGE = { uploaded: 'Uploaded', classified: 'Type identified', ocr_queued: 'Waiting to read', ocr_running: 'Reading text', ocr_done: 'Text read',
  extracting: 'Finding details', extracted: 'Details found', unreadable: 'Could not read file', ocr_failed: 'Text could not be read', extraction_failed: 'Details could not be found' }

function Row({ doc }) {
  const [ocr, setOcr] = useState(null)
  useEffect(() => {
    if (['ocr_done', 'extracting', 'extracted', 'extraction_failed'].includes(doc.status)) api(`/documents/${doc.id}/ocr`).then(setOcr).catch(() => {})
  }, [doc.id, doc.status])
  const c = doc.classification
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold text-navy">{DOC_NAMES[doc.slot]}</h2>
        <span className="rounded-full bg-mist px-2.5 py-0.5 text-xs font-medium">{STAGE[doc.status] || doc.status}</span>
      </div>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div><dt className="text-ink/60">Detected type</dt><dd className="font-medium">{c ? `${DOC_NAMES[c.predicted_label] || 'Other document'} (${Math.round(c.confidence * 100)}%)` : 'Not classified'}</dd></div>
        <div><dt className="text-ink/60">Text lines read</dt><dd className="font-medium">{ocr ? `${ocr.lines.length} (average confidence ${Math.round(ocr.mean_confidence * 100)}%)` : '-'}</dd></div>
        <div><dt className="text-ink/60">File</dt><dd className="truncate font-medium">{doc.original_name}</dd></div>
      </dl>
      {doc.slot_matches === false && <div className="mt-3"><Banner>This does not look like {DOC_NAMES[doc.slot].toLowerCase()}. Replace it on the Upload page.</Banner></div>}
    </div>
  )
}

export default function Results() {
  const [docs, setDocs] = useState(null)
  useEffect(() => {
    const load = () => api('/documents').then(setDocs)
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [])
  return (
    <Page title="Processing results" subtitle="What Edu Sahaya found in each document.">
      {docs && !docs.length && <p>No documents yet. <Link to="/upload" className="font-semibold text-navy underline">Upload them</Link>.</p>}
      {docs?.map((d) => <Row key={d.id} doc={d} />)}
      {docs?.length > 0 && <Link to="/review" className="btn-primary">Review extracted details</Link>}
    </Page>
  )
}
