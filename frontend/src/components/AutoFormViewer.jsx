import { useEffect, useState } from 'react'
import { Download, Save, RefreshCw, ChevronLeft, ChevronRight, CheckCircle2, AlertCircle, FileText, Sparkles } from 'lucide-react'
import { api, fetchBlob } from '../lib/api.js'

export default function AutoFormViewer({ onRefresh }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [values, setValues] = useState({})
  const [currentPage, setCurrentPage] = useState(0)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [activeTab, setActiveTab] = useState('all')

  const loadData = async () => {
    try {
      setLoading(true)
      const res = await api('/applications/me/auto-form')
      setData(res)
      if (res.fields) {
        const initial = {}
        res.fields.forEach((f) => {
          initial[f.field_id] = f.value ?? ''
        })
        setValues(initial)
      }
      await loadPreview(0)
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  const loadPreview = async (page) => {
    try {
      const blob = await fetchBlob(`/applications/me/auto-form/preview/${page}?t=${Date.now()}`)
      const url = URL.createObjectURL(blob)
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return url
      })
      setCurrentPage(page)
    } catch {
      // preview might not be ready yet
    }
  }

  useEffect(() => {
    loadData()
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [])

  const handleValueChange = (fieldId, val) => {
    setValues((prev) => ({ ...prev, [fieldId]: val }))
  }

  const saveEdits = async () => {
    setSaving(true)
    setMsg('')
    setErr('')
    try {
      const res = await api('/applications/me/auto-form', {
        method: 'PUT',
        body: { edits: values },
      })
      setData(res)
      await loadPreview(currentPage)
      setMsg('Changes saved and form updated successfully!')
      if (onRefresh) onRefresh()
    } catch (e) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  const downloadPdf = async () => {
    setDownloading(true)
    setErr('')
    try {
      const blob = await fetchBlob('/applications/me/auto-form/download')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'edu-sahaya-completed-admission-form.pdf'
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErr(e.message)
    } finally {
      setDownloading(false)
    }
  }

  if (loading) {
    return (
      <div className="card p-8 text-center text-ink/70">
        <RefreshCw className="mx-auto h-8 w-8 animate-spin text-teal" />
        <p className="mt-3 text-base font-medium">Analyzing admission form layout & pre-filling details...</p>
      </div>
    )
  }

  if (!data || data.status === 'no_form_uploaded') {
    return (
      <div className="card border-dashed border-2 border-navy/20 p-8 text-center">
        <FileText className="mx-auto h-12 w-12 text-ink/40" />
        <h3 className="mt-3 text-lg font-bold text-navy">No Blank Admission Form Uploaded</h3>
        <p className="mt-1 text-sm text-ink/70">
          Upload your college's blank admission form (PDF or Image) on the Upload page to have it automatically filled with your document details!
        </p>
        <a href="/upload" className="btn-primary mt-4 inline-block">
          Go to Upload Page
        </a>
      </div>
    )
  }

  const fields = data.fields || []
  const filteredFields = fields.filter((f) => {
    if (activeTab === 'personal') return f.section === 'personal'
    if (activeTab === 'academic') return f.section === 'academic'
    return true
  })

  const filledCount = fields.filter((f) => (values[f.field_id] || '').trim()).length

  return (
    <div className="space-y-6">
      {/* Top Banner and Summary */}
      <div className="card bg-gradient-to-r from-navy/5 via-teal/5 to-transparent p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-teal text-white">
                <Sparkles className="h-4 w-4" />
              </span>
              <h2 className="text-xl font-bold text-navy">Auto-Filled College Admission Form</h2>
            </div>
            <p className="mt-1 text-sm text-ink/80">
              Extracted from your supporting documents and filled directly into your uploaded form ({data.document?.original_name}). Original layout, tables, and alignment preserved.
            </p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-teal/10 px-2.5 py-1 font-medium text-teal">
                <CheckCircle2 className="mr-1 inline h-3.5 w-3.5" />
                {filledCount} of {fields.length} fields filled
              </span>
              <span className="rounded-full bg-mist px-2.5 py-1 text-ink/70">
                {fields.length - filledCount} left blank (ready to fill)
              </span>
              <span className="rounded-full bg-navy/10 px-2.5 py-1 font-medium text-navy">
                {data.pages_count} Page{data.pages_count > 1 ? 's' : ''}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={saveEdits}
              disabled={saving}
              className="btn-ghost flex items-center gap-1.5 border border-navy/20 bg-white"
            >
              <Save className="h-4 w-4" />
              {saving ? 'Saving...' : 'Save Edits'}
            </button>
            <button
              onClick={downloadPdf}
              disabled={downloading}
              className="btn-primary flex items-center gap-1.5 shadow-md"
            >
              <Download className="h-4 w-4" />
              {downloading ? 'Preparing...' : 'Download Completed PDF'}
            </button>
          </div>
        </div>

        {msg && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-teal/10 px-4 py-2.5 text-sm font-medium text-teal">
            <CheckCircle2 className="h-4 w-4" />
            {msg}
          </div>
        )}
        {err && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2.5 text-sm font-medium text-red-700">
            <AlertCircle className="h-4 w-4" />
            {err}
          </div>
        )}
      </div>

      {/* Main Two-Column View: Live Preview + Review/Edit Controls */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column: Visual Document Preview (7 cols) */}
        <div className="lg:col-span-7">
          <div className="card sticky top-4 overflow-hidden border border-navy/15 bg-slate-50 p-4">
            <div className="flex items-center justify-between border-b border-navy/10 pb-3">
              <span className="text-sm font-semibold text-navy">Form Document Visual Preview</span>
              {data.pages_count > 1 && (
                <div className="flex items-center gap-2 text-xs">
                  <button
                    onClick={() => loadPreview(Math.max(0, currentPage - 1))}
                    disabled={currentPage === 0}
                    className="rounded border bg-white p-1 hover:bg-slate-100 disabled:opacity-40"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="font-medium">
                    Page {currentPage + 1} of {data.pages_count}
                  </span>
                  <button
                    onClick={() => loadPreview(Math.min(data.pages_count - 1, currentPage + 1))}
                    disabled={currentPage >= data.pages_count - 1}
                    className="rounded border bg-white p-1 hover:bg-slate-100 disabled:opacity-40"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>

            <div className="mt-3 flex min-h-[500px] items-center justify-center overflow-auto rounded bg-white shadow-inner">
              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt={`Filled Admission Form Page ${currentPage + 1}`}
                  className="max-h-[750px] w-auto border object-contain"
                />
              ) : (
                <div className="text-center text-sm text-ink/50">
                  <RefreshCw className="mx-auto h-6 w-6 animate-spin" />
                  <p className="mt-2">Rendering page preview...</p>
                </div>
              )}
            </div>
            <p className="mt-2 text-center text-xs text-ink/60">
              The preview reflects your filled values stamped directly onto your original document layout.
            </p>
          </div>
        </div>

        {/* Right Column: Interactive Review & Edit Panel (5 cols) */}
        <div className="space-y-4 lg:col-span-5">
          <div className="card p-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-navy">Review & Edit Form Fields</h3>
              <div className="flex rounded-lg bg-mist p-0.5 text-xs font-medium">
                {['all', 'personal', 'academic'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`rounded-md px-2.5 py-1 capitalize ${
                      activeTab === tab ? 'bg-navy text-white shadow-sm' : 'text-ink/70 hover:text-navy'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <p className="mt-1 text-xs text-ink/70">
              Check the auto-filled information below. You can edit any field or fill in any blank fields, then click "Save Edits" to update the form.
            </p>

            <div className="mt-4 max-h-[620px] space-y-3 overflow-y-auto pr-1">
              {filteredFields.map((f) => {
                const val = values[f.field_id] ?? ''
                const isBlank = !val.trim()
                const isEdited = f.is_edited || val !== (f.suggested_value ?? '')

                return (
                  <div
                    key={f.field_id}
                    className={`rounded-lg border p-3 transition-colors ${
                      isBlank
                        ? 'border-dashed border-navy/20 bg-amber-50/40'
                        : isEdited
                        ? 'border-teal/40 bg-teal/5'
                        : 'border-navy/10 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <label htmlFor={f.field_id} className="text-xs font-semibold text-navy">
                        {f.label}
                      </label>
                      <div className="flex items-center gap-1.5 text-[11px]">
                        {f.matched_key && (
                          <span className="rounded bg-navy/5 px-1.5 py-0.5 font-mono text-ink/60">
                            {f.matched_key}
                          </span>
                        )}
                        {isBlank ? (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">Blank</span>
                        ) : isEdited ? (
                          <span className="rounded bg-teal/10 px-1.5 py-0.5 font-medium text-teal">Edited</span>
                        ) : (
                          <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-800">Auto-filled</span>
                        )}
                      </div>
                    </div>

                    <div className="mt-1.5">
                      {f.field_type === 'checkbox' ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id={f.field_id}
                            checked={val.toLowerCase() === '✓' || val.toLowerCase() === 'yes' || val === 'true'}
                            onChange={(e) => handleValueChange(f.field_id, e.target.checked ? '✓' : '')}
                            className="h-4 w-4 rounded border-navy/30 text-teal focus:ring-teal"
                          />
                          <span className="text-xs text-ink/80">Mark checkbox</span>
                        </div>
                      ) : (
                        <input
                          type="text"
                          id={f.field_id}
                          value={val}
                          placeholder="Leave blank or type value..."
                          onChange={(e) => handleValueChange(f.field_id, e.target.value)}
                          className="w-full rounded border border-navy/20 bg-white px-2.5 py-1.5 text-sm text-ink focus:border-teal focus:outline-none focus:ring-1 focus:ring-teal"
                        />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-navy/10 flex justify-end">
              <button
                onClick={saveEdits}
                disabled={saving}
                className="btn-primary w-full flex items-center justify-center gap-2 text-sm py-2"
              >
                <Save className="h-4 w-4" />
                {saving ? 'Saving...' : 'Save & Refresh Preview'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

