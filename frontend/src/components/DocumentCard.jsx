import { CheckCircle2, FileText, Trash2, UploadCloud } from 'lucide-react'

const ACCEPT = '.jpg,.jpeg,.png,.pdf'
const NAMES = { aadhaar: 'an Aadhaar card', sslc: 'an SSLC marks card', puc: 'a PUC marks card' }

const STAGES = {
  ocr_queued: ['Waiting to read the text...', 'text-ink'],
  ocr_running: ['Reading the text...', 'text-ink'],
  extracting: ['Finding your details...', 'text-ink'],
  ocr_done: ['Text read successfully', 'text-[#0f7d79]'],
  extracted: ['Details found. Ready to review', 'text-[#0f7d79]'],
  ocr_failed: ['We could not read the text. Replace with a clearer copy.', 'text-red-700'],
}

function Stage({ status }) {
  const stage = STAGES[status]
  return stage ? <p className={`mt-1 text-sm ${stage[1]}`}>{stage[0]}</p> : null
}

function Detection({ doc }) {
  if (doc.status === 'unreadable')
    return <p role="alert" className="mt-2 text-sm text-red-700">We could not read this file. Upload a clearer JPG, PNG or PDF.</p>
  const c = doc.classification
  if (!c) return null
  const pct = Math.round(c.confidence * 100)
  if (!c.recognised)
    return <p className="mt-2 text-sm text-amber-700">Not recognised as an Aadhaar, SSLC or PUC document ({c.predicted_label}, {pct}%). Check the file or replace it.</p>
  if (!doc.slot_matches)
    return <p className="mt-2 text-sm text-amber-700">This looks like {NAMES[c.predicted_label]} ({pct}%). Replace it or upload it in the matching section.</p>
  return <p className="mt-2 text-sm text-[#0f7d79]">Detected as {NAMES[c.predicted_label]} ({pct}% confidence)</p>
}

function Picker({ onPick, className, children }) {
  return (
    <label className={`${className} cursor-pointer focus-within:outline focus-within:outline-2 focus-within:outline-accent`}>
      <input type="file" accept={ACCEPT} className="sr-only"
        onChange={(e) => { const f = e.target.files[0]; e.target.value = ''; f && onPick(f) }} />
      {children}
    </label>
  )
}

export default function DocumentCard({ title, doc, preview, progress, error, locked, onPick, onDelete, onViewPdf }) {
  const uploading = progress != null
  return (
    <div className="card flex flex-col p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold text-navy">{title}</h2>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
          uploading ? 'bg-amber-50 text-amber-700' : doc ? 'bg-accent/15 text-[#0f7d79]' : 'bg-mist text-ink/70'}`}>
          {uploading ? `Uploading ${progress}%` : doc ? 'Uploaded' : 'Not uploaded'}
        </span>
      </div>

      <div className="mt-4 grid h-44 place-items-center overflow-hidden rounded-xl bg-mist">
        {preview ? (
          <img src={preview} alt={`${title} preview`} className="h-full w-full object-contain" />
        ) : doc ? (
          <button onClick={onViewPdf} className="flex flex-col items-center gap-2 text-sm text-navy underline">
            <FileText size={32} /> View PDF
          </button>
        ) : (
          <Picker onPick={onPick} className="flex h-full w-full flex-col items-center justify-center gap-2 border-2 border-dashed border-navy/20 text-center text-sm">
            <UploadCloud className="text-accent" />
            <span className="font-medium text-navy">Choose a file</span>
            <span className="text-xs">JPG, PNG or PDF, up to 10 MB</span>
          </Picker>
        )}
      </div>

      {uploading && (
        <div className="mt-3 h-2 overflow-hidden rounded bg-mist" role="progressbar" aria-valuenow={progress}>
          <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}

      {doc && !uploading && (
        <div className="mt-3 flex items-center justify-between gap-2 text-sm">
          <span className="flex min-w-0 items-center gap-1.5">
            <CheckCircle2 size={16} className="shrink-0 text-accent" />
            <span className="truncate">{doc.original_name}</span>
          </span>
          {!locked && (
            <span className="flex shrink-0 gap-2">
              <Picker onPick={onPick} className="btn-ghost !px-3 !py-1.5">Replace</Picker>
              <button onClick={onDelete} aria-label={`Remove ${title}`} className="btn-ghost !px-3 !py-1.5">
                <Trash2 size={14} />
              </button>
            </span>
          )}
        </div>
      )}
      {doc && !uploading && <Detection doc={doc} />}
      {doc && !uploading && <Stage status={doc.status} />}
    </div>
  )
}
