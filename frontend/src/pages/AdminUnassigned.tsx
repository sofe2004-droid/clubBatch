import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchUnassigned } from '../api'
import { AdminNav } from '../components/AdminNav'
import { ADMIN_TOKEN_KEY } from './AdminLogin'

export function AdminUnassigned() {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY)
  const [items, setItems] = useState<
    { student_id: number; student_number: string; name: string; reason: string }[]
  >([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    fetchUnassigned(token)
      .then((r) => setItems(r.items))
      .catch((e: Error) => setErr(e.message))
  }, [token])

  if (!token) {
    return (
      <div className="layout">
        <Link to="/admin/login">로그인</Link>
      </div>
    )
  }

  return (
    <div className="layout">
      <AdminNav token={token} />
      <div className="card card--accent">
        <h1 className="page-title">
          <span className="page-title__emoji" aria-hidden>
            🌱
          </span>
          미배정 학생
        </h1>
        <p className="page-lead">아직 동아리가 정해지지 않은 친구들이에요. 강제배정으로 도와줄 수 있어요.</p>
        {err && <p className="error">{err}</p>}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>학번</th>
                <th>이름</th>
                <th>사유</th>
                <th style={{ width: 120 }} />
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.student_id}>
                  <td>{s.student_number}</td>
                  <td>{s.name}</td>
                  <td>{s.reason}</td>
                  <td>
                    <Link className="pill-link" to="/admin/force" state={{ studentId: s.student_id }}>
                      강제배정
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
