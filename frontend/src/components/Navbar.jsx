import { Link } from 'react-router-dom'
import Logo from './Logo.jsx'
import { homeFor } from './ProtectedRoute.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Navbar() {
  const { user, logout } = useAuth()
  return (
    <header className="sticky top-0 z-20 border-b border-navy/5 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />
        <nav className="flex items-center gap-2">
          {user ? (
            <>
              <Link to={homeFor(user)} className="btn-ghost">{user.role === 'admin' ? 'Admin' : 'Dashboard'}</Link>
              <button onClick={logout} className="btn-primary">Log out</button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn-ghost">Log in</Link>
              <Link to="/register" className="btn-primary">Get started</Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
