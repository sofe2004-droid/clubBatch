import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ClubItem } from '../api'
import { applyClub, fetchClubs, fetchMyAssignment } from '../api'
import { StudentAssignedComplete } from '../components/StudentAssignedComplete'
import { TOKEN_KEY } from './StudentVerify'

export function StudentClubs() {
  const nav = useNavigate()
  const token = sessionStorage.getItem(TOKEN_KEY)
  const [clubs, setClubs] = useState<ClubItem[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [assignedClub, setAssignedClub] = useState<string | null>(null)
  const [loadingGate, setLoadingGate] = useState(true)

  useEffect(() => {
    if (!token) {
      nav('/', { replace: true })
      return
    }
    let cancelled = false
    setLoadingGate(true)
    setErr(null)
    fetchMyAssignment(token)
      .then(async (r) => {
        if (cancelled) return
        if (r.club_name) {
          setAssignedClub(r.club_name)
          return
        }
        const list = await fetchClubs(token)
        if (!cancelled) setClubs(list)
      })
      .catch((e: Error) => {
        if (!cancelled) setErr(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoadingGate(false)
      })
    return () => {
      cancelled = true
    }
  }, [token, nav])

  async function onApply(clubId: number) {
    if (!token) return
    setBusyId(clubId)
    setErr(null)
    try {
      const res = await applyClub(token, clubId)
      if (res.ok) {
        nav('/result', { state: res })
      } else {
        setErr(res.message)
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : '신청 실패')
    } finally {
      setBusyId(null)
    }
  }

  if (!token) return null

  if (assignedClub) {
    return <StudentAssignedComplete clubName={assignedClub} />
  }

  if (loadingGate) {
    return (
      <div className="layout layout-student">
        <div className="card card--hello">
          <p className="page-lead" style={{ textAlign: 'center', margin: 0 }}>
            잠시만 기다려 주세요…
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="layout layout-student">
      <header className="card card--hello">
        <h1 className="page-title">
          <span className="page-title__emoji" aria-hidden>
            🎨
          </span>
          동아리 선택
        </h1>
        <p className="page-lead" style={{ marginBottom: 0 }}>
          마음에 드는 동아리를 골라 주세요. 신청 가능한 동아리만 버튼이 살아 있어요. 정원은 실시간으로
          반영돼요.
        </p>
        {err && <div className="error">{err}</div>}
      </header>

      <div className="club-grid">
        {clubs.map((c) => {
          const pct =
            c.capacity > 0 ? Math.min(100, Math.round((c.current_count / c.capacity) * 100)) : 0
          return (
            <article key={c.id} className="club-card">
              <div className="club-card__head">
                <h2 className="club-card__title">{c.club_name}</h2>
                <span className="club-card__dot" aria-hidden />
              </div>
              <p className="club-card__teacher">담당 {c.teacher_name ?? '—'}</p>
              <div className="club-card__meta">
                <span className="badge badge--capacity">정원 {c.capacity}명</span>
                <span className="badge badge--count">신청 {c.current_count}명</span>
                <span className="badge badge--remain">남은 {c.remaining}명</span>
              </div>
              <div className="club-card__bar" title={`${c.current_count} / ${c.capacity}`}>
                <div className="club-card__bar-fill" style={{ width: `${pct}%` }} />
              </div>
              {c.description ? (
                <p className="club-card__desc">{c.description}</p>
              ) : (
                <p className="club-card__desc" style={{ fontStyle: 'italic', opacity: 0.75 }}>
                  소개글이 아직 없어요.
                </p>
              )}
              <p
                className={
                  c.is_open
                    ? 'club-card__status club-card__status--open'
                    : 'club-card__status club-card__status--closed'
                }
              >
                {c.is_open ? '지금 신청할 수 있어요' : '지금은 신청할 수 없어요 (기간·정원 등)'}
              </p>
              <button
                type="button"
                disabled={!c.is_open || busyId !== null}
                onClick={() => onApply(c.id)}
              >
                {busyId === c.id ? '처리 중…' : '이 동아리에 신청하기'}
              </button>
            </article>
          )
        })}
      </div>
    </div>
  )
}
