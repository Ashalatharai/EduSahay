import { Link, Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import Logo from '../components/Logo.jsx'

export default function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t border-navy/5 bg-mist">
        <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <Logo />
            <p className="mt-3 text-sm">Simplifying admissions through intelligent document processing.</p>
          </div>
          <nav aria-label="Account">
            <h2 className="text-sm font-semibold text-navy">Account</h2>
            <ul className="mt-3 space-y-2 text-sm">
              <li><Link to="/login" className="hover:underline">Log in</Link></li>
              <li><Link to="/register" className="hover:underline">Create account</Link></li>
            </ul>
          </nav>
          <div>
            <h2 className="text-sm font-semibold text-navy">Documents</h2>
            <ul className="mt-3 space-y-2 text-sm"><li>Aadhaar card</li><li>SSLC marks card</li><li>PUC marks card</li></ul>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-navy">Privacy</h2>
            <p className="mt-3 text-sm">Documents are encrypted at rest and shown only to you and the administrators reviewing your application.</p>
          </div>
        </div>
        <p className="border-t border-navy/5 px-5 py-4 text-center text-xs text-ink/70">
          &copy; {new Date().getFullYear()} Edu Sahaya. Checks are preliminary and do not verify documents with any government authority.
        </p>
      </footer>
    </div>
  )
}
