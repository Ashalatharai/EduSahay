import { useEffect, useState } from 'react'
import { Download } from 'lucide-react'
import { Banner, Page } from '../components/ui.jsx'
import { fetchBlob } from '../lib/api.js'

export default function ProfilePreview() {
  const [url, setUrl] = useState(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    let u
    fetchBlob('/applications/me/profile.pdf').then((b) => { u = URL.createObjectURL(b); setUrl(u) }).catch(() => setErr('Submit your application to generate the admission profile.'))
    return () => u && URL.revokeObjectURL(u)
  }, [])
  return (
    <Page title="Admission profile" subtitle="Preview and download your consolidated profile.">
      {err && <Banner>{err}</Banner>}
      {url && <>
        <a href={url} download="edu-sahaya-admission-profile.pdf" className="btn-primary w-fit"><Download size={16} /> Download PDF</a>
        <iframe title="Admission profile preview" src={url} className="h-[75vh] w-full rounded-xl border border-navy/10" />
      </>}
    </Page>
  )
}
