import { Link } from 'react-router-dom'

type AdminNavProps = {
  token: string | null
  tools?: React.ReactNode
}

export function AdminNav({ token, tools }: AdminNavProps) {
  if (!token) return null
  return (
    <nav className="admin-nav card">
      <div className="admin-nav__links">
        <Link className="admin-nav__link" to="/admin">
          대시보드
        </Link>
        <Link className="admin-nav__link" to="/admin/apps">
          신청 현황
        </Link>
        <Link className="admin-nav__link" to="/admin/unassigned">
          미배정
        </Link>
        <Link className="admin-nav__link" to="/admin/force">
          강제배정
        </Link>
      </div>
      {tools ? <div className="admin-nav__tools">{tools}</div> : null}
    </nav>
  )
}
