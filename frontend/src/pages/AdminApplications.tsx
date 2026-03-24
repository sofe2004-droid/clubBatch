import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { ApplicationListItem } from '../api'
import { cancelStudentApplicationAdmin, fetchApplications } from '../api'
import { AdminNav } from '../components/AdminNav'
import { ADMIN_TOKEN_KEY } from './AdminLogin'

export function AdminApplications() {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY)
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [items, setItems] = useState<ApplicationListItem[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [busyDelId, setBusyDelId] = useState<number | null>(null)

  function load() {
    if (!token) return
    fetchApplications(token, q)
      .then((r) => setItems(r.items))
      .catch((e: Error) => setErr(e.message))
  }

  useEffect(() => {
    load()
  }, [token])

  async function onDelete(row: ApplicationListItem) {
    if (!token) return
    if (
      !window.confirm(
        `${row.student_number} ${row.name} 학생의 동아리 배정을 삭제할까요?\n삭제 후에는 해당 학생만 다시 신청할 수 있습니다.`,
      )
    ) {
      return
    }
    setBusyDelId(row.application_id)
    setErr(null)
    try {
      await cancelStudentApplicationAdmin(token, row.application_id)
      load()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : '삭제 실패')
    } finally {
      setBusyDelId(null)
    }
  }

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
            📋
          </span>
          신청 현황
        </h1>
        <p className="page-lead">
          현재 배정이 확정된 학생만 보여요. 조정하면 기존 배정이 취소되고 새 동아리로 다시 배정돼요.
        </p>
        <div className="row">
          <input
            placeholder="학번/이름 검색"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ maxWidth: 260 }}
          />
          <button type="button" onClick={load}>
            검색
          </button>
        </div>
        {err && <p className="error">{err}</p>}
        <div className="table-wrap" style={{ marginTop: 14 }}>
          <table>
            <thead>
              <tr>
                <th>학번</th>
                <th>이름</th>
                <th>동아리</th>
                <th style={{ width: 168 }}>관리</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.student_id}>
                  <td>{row.student_number}</td>
                  <td>{row.name}</td>
                  <td>{row.club_name}</td>
                  <td>
                    <div className="row" style={{ gap: '0.35rem', flexWrap: 'nowrap' }}>
                      <button
                        type="button"
                        className="secondary btn-compact"
                        onClick={() =>
                          navigate('/admin/force', {
                            state: {
                              studentId: row.student_id,
                              studentNumber: row.student_number,
                              studentName: row.name,
                              currentClubName: row.club_name,
                            },
                          })
                        }
                      >
                        조정
                      </button>
                      <button
                        type="button"
                        className="danger btn-compact"
                        disabled={busyDelId !== null}
                        onClick={() => onDelete(row)}
                      >
                        {busyDelId === row.application_id ? '…' : '삭제'}
                      </button>
                    </div>
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
