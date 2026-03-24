import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminLogin } from '../api'

const ADMIN_TOKEN_KEY = 'club_admin_token'

export function AdminLogin() {
  const nav = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setLoading(true)
    try {
      const res = await adminLogin(username, password)
      sessionStorage.setItem(ADMIN_TOKEN_KEY, res.access_token)
      nav('/admin', { replace: true })
    } catch (e2: unknown) {
      setErr(e2 instanceof Error ? e2.message : '로그인 실패')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="layout">
      <div className="card card--accent login-card">
        <h1 className="page-title">
          <span className="page-title__emoji" aria-hidden>
            🔐
          </span>
          관리자 로그인
        </h1>
        <p className="page-lead">선생님 전용 화면이에요.</p>
        <form onSubmit={onSubmit}>
          <label>아이디</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
          <div style={{ height: 12 }} />
          <label>비밀번호</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          {err && <div className="error">{err}</div>}
          <div style={{ height: 16 }} />
          <button type="submit" disabled={loading}>
            {loading ? '로그인 중…' : '로그인'}
          </button>
        </form>
      </div>
    </div>
  )
}

export { ADMIN_TOKEN_KEY }
