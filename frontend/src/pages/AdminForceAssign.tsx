import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { fetchAdminClubs, forceAssign } from '../api'
import { AdminNav } from '../components/AdminNav'
import { ADMIN_TOKEN_KEY } from './AdminLogin'

type ForceAssignNavState = {
  studentId?: number
  studentNumber?: string
  studentName?: string
  currentClubName?: string
}

export function AdminForceAssign() {
  const loc = useLocation() as { state?: ForceAssignNavState }
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY)
  const [studentId, setStudentId] = useState(
    loc.state?.studentId != null ? String(loc.state.studentId) : '',
  )
  const [fromAppsHint, setFromAppsHint] = useState<ForceAssignNavState | null>(
    loc.state?.studentId != null ? (loc.state ?? null) : null,
  )
  const [clubId, setClubId] = useState<number | ''>('')
  const [reason, setReason] = useState('')
  const [cancelExisting, setCancelExisting] = useState(true)
  const [allowOver, setAllowOver] = useState(false)
  const [clubs, setClubs] = useState<{ id: number; club_name: string; remaining: number }[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    const s = loc.state
    if (s?.studentId != null) {
      setStudentId(String(s.studentId))
      setFromAppsHint(s)
    }
  }, [loc.state])

  useEffect(() => {
    if (!token) return
    fetchAdminClubs(token)
      .then((r) =>
        setClubs(
          r.items.map((c) => ({
            id: c.id,
            club_name: c.club_name,
            remaining: c.remaining,
          })),
        ),
      )
      .catch(() => {})
  }, [token])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    setErr(null)
    setMsg(null)
    const sid = Number.parseInt(String(studentId), 10)
    const cid = typeof clubId === 'number' ? clubId : Number(clubId)
    if (!sid || !cid) {
      setErr('학생 ID와 동아리를 선택하세요.')
      return
    }
    try {
      const r = await forceAssign(token, {
        student_id: sid,
        club_id: cid,
        reason,
        cancel_existing: cancelExisting,
        allow_over_capacity: allowOver,
      })
      setMsg(r.message)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : '실패')
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
            🎯
          </span>
          강제배정 · 재배정
        </h1>
        <p className="page-lead">미배정 학생을 넣거나, 이미 배정된 학생을 다른 동아리로 옮길 수 있어요.</p>
        {fromAppsHint?.studentId != null && (
          <p className="muted" style={{ marginTop: 0 }}>
            조정 대상:{' '}
            <strong>
              {fromAppsHint.studentNumber ?? ''} {fromAppsHint.studentName ?? ''}
            </strong>
            {fromAppsHint.currentClubName ? (
              <> · 현재 동아리: {fromAppsHint.currentClubName}</>
            ) : null}
          </p>
        )}
        <form className="form-stack" onSubmit={onSubmit}>
          <label>학생 ID (내부 번호 · 신청 현황「조정」으로 자동 입력)</label>
          <input value={studentId} onChange={(e) => setStudentId(e.target.value)} />
          <div style={{ height: 10 }} />
          <label>동아리</label>
          <select
            value={clubId === '' ? '' : String(clubId)}
            onChange={(e) => setClubId(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">선택</option>
            {clubs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.club_name} (잔여 {c.remaining})
              </option>
            ))}
          </select>
          <div style={{ height: 10 }} />
          <label>사유</label>
          <textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} required />
          <div style={{ height: 10 }} />
          <label className="row">
            <input
              type="checkbox"
              checked={cancelExisting}
              onChange={(e) => setCancelExisting(e.target.checked)}
            />
            기존 신청 취소 후 배정
          </label>
          <label className="row">
            <input type="checkbox" checked={allowOver} onChange={(e) => setAllowOver(e.target.checked)} />
            정원 초과 허용
          </label>
          {err && <p className="error">{err}</p>}
          {msg && <p className="success">{msg}</p>}
          <div style={{ height: 12 }} />
          <button type="submit">강제배정 실행</button>
        </form>
      </div>
    </div>
  )
}
