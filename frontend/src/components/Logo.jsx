import { Link } from 'react-router-dom'
import { GraduationCap } from 'lucide-react'

export default function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-extrabold text-navy text-lg">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-navy text-white">
        <GraduationCap size={18} />
      </span>
      Edu Sahaya
    </Link>
  )
}
