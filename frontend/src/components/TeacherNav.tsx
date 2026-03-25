import { useNavigate } from 'react-router-dom'
import { ADMIN_ROLE_KEY, ADMIN_TOKEN_KEY } from '../pages/AdminLogin'

export function TeacherNav() {
  const nav = useNavigate()
  function logout() {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    sessionStorage.removeItem(ADMIN_ROLE_KEY)
    nav('/teacher/login', { replace: true })
  }
  return (
    <nav className="admin-nav card">
      <div className="admin-nav__links">
        <span className="muted" style={{ padding: '8px 0' }}>
          동아리 배정 현황 (조회 전용)
        </span>
      </div>
      <div className="admin-nav__tools">
        <button type="button" className="secondary" onClick={logout}>
          로그아웃
        </button>
      </div>
    </nav>
  )
}
