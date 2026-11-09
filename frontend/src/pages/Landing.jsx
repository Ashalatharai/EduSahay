import { Link } from 'react-router-dom'
import { Upload, ScanText, ClipboardCheck, FileDown, ShieldCheck, ArrowRight, FileText, Copy, Clock, Users } from 'lucide-react'
import DocToForm from '../components/DocToForm.jsx'

const steps = [
  [Upload, 'Upload', 'Add your Aadhaar, SSLC and PUC marks cards as images or PDFs.'],
  [ScanText, 'We read them', 'Each document is identified, its text is read, and key details are pulled out.'],
  [ClipboardCheck, 'You review', 'Check the prefilled form. Anything uncertain is highlighted for you.'],
  [FileDown, 'Submit and download', 'Submit your application and download your admission profile.'],
]

const benefits = [
  [FileText, 'Fewer forms to type', 'Name, date of birth, register numbers and marks are prefilled from your documents.'],
  [ClipboardCheck, 'Mistakes caught early', 'Names, dates and mark totals are compared across your documents before you submit.'],
  [Clock, 'Clear status', 'Follow your application from upload to approval, and see exactly what to correct if asked.'],
  [Copy, 'Duplicate flags', 'Administrators see possible duplicates and decide for themselves. Nothing is rejected automatically.'],
  [FileDown, 'Admission profile PDF', 'A consolidated profile is generated once you submit.'],
  [Users, 'Admin dashboard', 'Search, filter and review applications with documents, extracted fields and checks in one place.'],
]
const documents = [
  ['Aadhaar card', 'Name, date of birth, gender and a masked number.'],
  ['SSLC marks card', 'Register number, school, year, subject marks, total and percentage.'],
  ['PUC marks card', 'Register number, college, year, subject marks, total and percentage.'],
]
const faqs = [
  ['Which files can I upload?', 'JPG, PNG or PDF, up to 10 MB each.'],
  ['What if a detail is read wrongly?', 'Uncertain values are highlighted. You can correct any of them on the review page or in the form.'],
  ['Is my Aadhaar verified?', 'No. The checks only compare your own documents with each other. They are not government verification.'],
  ['Can I change things after submitting?', 'Not unless the administrator requests corrections. Then you can edit and resubmit.'],
]

export default function Landing() {
  return (
    <>
      <section className="bg-mist">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <h1 className="text-4xl font-extrabold leading-tight text-navy sm:text-5xl">
              Simplifying admissions through intelligent document processing.
            </h1>
            <p className="mt-5 max-w-lg text-lg">
              Upload your marks cards and ID once. Edu Sahaya fills in your admission form so you only
              check it.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register" className="btn-primary">Create account <ArrowRight size={16} /></Link>
              <Link to="/login" className="btn-ghost">Log in</Link>
            </div>
          </div>
          <DocToForm />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-16">
        <h2 className="text-2xl font-bold text-navy">How it works</h2>
        <ol className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([Icon, title, text], i) => (
            <li key={title} className="card p-5">
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-accent/15 text-accent"><Icon size={18} /></span>
                <span className="text-sm font-semibold text-navy/60">Step {i + 1}</span>
              </div>
              <h3 className="mt-4 font-semibold text-navy">{title}</h3>
              <p className="mt-1 text-sm">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-16">
        <h2 className="text-2xl font-bold text-navy">What you get</h2>
        <ul className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {benefits.map(([Icon, title, text]) => (
            <li key={title} className="card p-5">
              <Icon size={20} className="text-accent" />
              <h3 className="mt-3 font-semibold text-navy">{title}</h3>
              <p className="mt-1 text-sm">{text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="bg-mist">
        <div className="mx-auto max-w-6xl px-5 py-16">
          <h2 className="text-2xl font-bold text-navy">Documents we read</h2>
          <ul className="mt-8 grid gap-5 md:grid-cols-3">
            {documents.map(([title, text]) => (
              <li key={title} className="card p-5"><h3 className="font-semibold text-navy">{title}</h3><p className="mt-1 text-sm">{text}</p></li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-5 py-16">
        <h2 className="text-2xl font-bold text-navy">Questions</h2>
        <div className="mt-6 divide-y divide-navy/10 border-y border-navy/10">
          {faqs.map(([q, a]) => (
            <details key={q} className="py-4">
              <summary className="cursor-pointer font-semibold text-navy">{q}</summary>
              <p className="mt-2 text-sm">{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-12">
        <div className="rounded-2xl bg-navy px-6 py-10 text-center text-white">
          <h2 className="text-2xl font-bold">Ready to start your application?</h2>
          <p className="mt-2">Create an account and upload your documents.</p>
          <Link to="/register" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-white px-5 py-2.5 font-semibold text-navy">Create account <ArrowRight size={16} /></Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 pb-20">
        <div className="card flex items-start gap-4 p-6">
          <ShieldCheck className="mt-0.5 shrink-0 text-accent" />
          <p className="text-sm">
            Your documents are processed only with your consent and stored privately. Aadhaar numbers are
            masked. Edu Sahaya runs consistency checks across your documents; it does not authenticate
            Aadhaar or verify documents with any authority.
          </p>
        </div>
      </section>
    </>
  )
}
