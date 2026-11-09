import { AlertTriangle, Check } from 'lucide-react'
import { APP_STATUS, STEPS, VALIDATION } from '../lib/labels.js'

export function Badge({ status }) {
  const tone = { approved: 'bg-accent/15 text-[#0f7d79]', submitted: 'bg-blue-50 text-blue-700', correction_requested: 'bg-amber-50 text-amber-700',
    review_required: 'bg-amber-50 text-amber-700' }[status] || 'bg-mist text-ink'
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>{APP_STATUS[status] || status}</span>
}

export function CheckBadge({ status }) {
  const [label, tone] = VALIDATION[status]
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
}

export function Banner({ children, tone = 'amber' }) {
  const c = tone === 'red' ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-amber-50 text-amber-900'
  return <p role="status" className={`flex gap-2 rounded-lg border px-4 py-3 text-sm ${c}`}><AlertTriangle size={16} className="mt-0.5 shrink-0" />{children}</p>
}

export function Page({ title, subtitle, children }) {
  return (
    <section className="mx-auto max-w-5xl px-5 py-10">
      <h1 className="text-3xl font-bold text-navy">{title}</h1>
      {subtitle && <p className="mt-1">{subtitle}</p>}
      <div className="mt-6 space-y-6">{children}</div>
    </section>
  )
}

export function ApplicationSteps({ status }) {
  const current = STEPS.indexOf(status === 'correction_requested' ? 'review_required' : status)
  return (
    <ol className="grid grid-cols-2 gap-3 sm:grid-cols-6" aria-label="Application progress">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-2 text-sm">
          <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-bold ${
            i < current ? 'bg-accent text-white' : i === current ? 'bg-navy text-white' : 'bg-mist text-ink/60'}`}>
            {i < current ? <Check size={14} /> : i + 1}
          </span>
          <span className={i === current ? 'font-semibold text-navy' : ''}>{APP_STATUS[s]}</span>
        </li>
      ))}
    </ol>
  )
}

export function PrototypeNote({ model }) {
  return model?.prototype ? (
    <Banner>These details came from a prototype model trained on synthetic (fictional) documents. Check every value carefully.</Banner>
  ) : null
}
