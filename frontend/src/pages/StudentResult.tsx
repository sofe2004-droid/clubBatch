import { Navigate, useLocation } from 'react-router-dom'
import type { ApplyRes } from '../api'
import { StudentAssignedComplete } from '../components/StudentAssignedComplete'

export function StudentResult() {
  const loc = useLocation()
  const res = loc.state as ApplyRes | undefined
  if (!res) {
    return <Navigate to="/" replace />
  }
  if (res.ok && res.club_name) {
    return <StudentAssignedComplete clubName={res.club_name} />
  }
  return (
    <div className="layout layout-student">
      <div className="card card--hello">
        <div className="result-blob">
          <div className="result-blob__icon" aria-hidden>
            😢
          </div>
        </div>
        <h1 className="page-title" style={{ textAlign: 'center' }}>
          신청 결과
        </h1>
        <p className="error" style={{ textAlign: 'center', fontSize: '1.05rem', fontWeight: 700 }}>
          {res.message}
        </p>
      </div>
    </div>
  )
}
