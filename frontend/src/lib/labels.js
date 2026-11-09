export const APP_STATUS = {
  documents_not_uploaded: 'Documents not uploaded', documents_uploaded: 'Documents uploaded', processing: 'Processing',
  review_required: 'Review required', submitted: 'Submitted', approved: 'Approved', correction_requested: 'Correction requested',
}
export const STEPS = ['documents_not_uploaded', 'documents_uploaded', 'processing', 'review_required', 'submitted', 'approved']
export const DOC_NAMES = {
  aadhaar: 'Aadhaar card',
  sslc: 'SSLC marks card',
  puc: 'PUC marks card',
  admission_form: 'Blank college admission form',
}
export const VALIDATION = {
  matched: ['Matched', 'bg-accent/15 text-[#0f7d79]'], mismatch: ['Mismatch', 'bg-red-50 text-red-700'],
  missing: ['Missing', 'bg-slate-100 text-slate-700'], needs_review: ['Needs review', 'bg-amber-50 text-amber-700'],
}
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
export function fieldLabel(name) {
  const m = name.match(/^subject_(\d+)_(name|marks)$/)
  if (m) return m[2] === 'name' ? `Subject ${m[1]}` : `Subject ${m[1]} marks`
  return cap(name.replace(/_/g, ' ').replace('aadhaar number masked', 'Aadhaar number (masked)'))
}
export function checkLabel(key) {
  if (key.startsWith('document:')) return DOC_NAMES[key.slice(9)]
  const [a, b] = key.includes('.') ? key.split('.') : [null, key]
  return (a ? a.toUpperCase().replace('AADHAAR', 'Aadhaar') + ' ' : '') + b.replace(/_/g, ' ')
}
export const fmtDate = (d) => (d ? new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '-')
