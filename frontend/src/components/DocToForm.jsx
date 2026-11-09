import { FileText, CheckCircle2, AlertCircle } from 'lucide-react'

const fields = [
  ['Full name', 'Ananya K. Rao', true],
  ['Date of birth', '14/06/2008', true],
  ['Register number', 'S-0000000', false],
  ['Percentage', '91.2', true],
]

export default function DocToForm() {
  return (
    <div className="grid gap-4 sm:grid-cols-2" aria-label="Illustration with fictional data">
      <div className="card p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-navy">
          <FileText size={16} /> SSLC marks card
        </div>
        <div className="space-y-2.5">
          {[70, 100, 55, 85, 60].map((w, i) => (
            <div key={i} className="h-2.5 rounded bg-navy/10" style={{ width: `${w}%` }} />
          ))}
          <div className="rounded border-2 border-dashed border-accent bg-accent/10 px-2 py-1 text-xs font-medium text-navy">
            Ananya K. Rao
          </div>
          <div className="h-2.5 w-2/3 rounded bg-navy/10" />
          <div className="rounded border-2 border-dashed border-accent bg-accent/10 px-2 py-1 text-xs font-medium text-navy">
            14/06/2008
          </div>
        </div>
      </div>
      <div className="card p-5">
        <div className="mb-4 text-sm font-semibold text-navy">Admission form</div>
        <div className="space-y-3">
          {fields.map(([label, value, ok]) => (
            <div key={label}>
              <div className="flex items-center justify-between text-xs">
                <span>{label}</span>
                <span className={ok ? 'text-accent' : 'text-amber-600'}>
                  {ok ? <CheckCircle2 size={14} className="inline" /> : <AlertCircle size={14} className="inline" />}{' '}
                  {ok ? 'Extracted' : 'Needs review'}
                </span>
              </div>
              <div className={`mt-1 rounded-lg border px-3 py-1.5 text-sm ${ok ? 'border-navy/10' : 'border-amber-400 bg-amber-50'}`}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
