import { NavLink, Outlet } from 'react-router-dom'

const links = [['dashboard', 'Dashboard'], ['upload', 'Upload'], ['results', 'Processing'], ['review', 'Review'], ['form', 'Form'], ['status', 'Status']]

export default function StudentLayout() {
  return (
    <>
      <nav aria-label="Student sections" className="border-b border-navy/5 bg-mist">
        <div className="mx-auto flex max-w-5xl gap-1 overflow-x-auto px-5 py-2">
          {links.map(([to, label]) => (
            <NavLink key={to} to={`/${to}`} className={({ isActive }) =>
              `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${isActive ? 'bg-navy text-white' : 'text-navy hover:bg-white'}`}>{label}</NavLink>
          ))}
        </div>
      </nav>
      <Outlet />
    </>
  )
}
