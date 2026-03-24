import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Dashboard } from '../api'
import {
  exportSheets,
  fetchClubAssignedStudents,
  fetchDashboard,
  syncSheets,
} from '../api'
import { AdminNav } from '../components/AdminNav'
import { ADMIN_TOKEN_KEY } from './AdminLogin'

export function AdminDashboard() {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY)
  const [d, setD] = useState<Dashboard | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [detailClubId, setDetailClubId] = useState<number | null>(null)
  const [detailStudents, setDetailStudents] = useState<
    { student_number: string; name: string }[]
  >([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailErr, setDetailErr] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [exportingSheets, setExportingSheets] = useState(false)

  function load() {
    if (!token) return
    setErr(null)
    fetchDashboard(token)
      .then(setD)
      .catch((e: Error) => setErr(e.message))
  }

  useEffect(() => {
    load()
  }, [token])

  useEffect(() => {
    if (!token || detailClubId == null) {
      setDetailStudents([])
      setDetailLoading(false)
      setDetailErr(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    setDetailErr(null)
    fetchClubAssignedStudents(token, detailClubId)
      .then((r) => {
        if (!cancelled) {
          setDetailStudents(r.students)
          setDetailLoading(false)
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setDetailErr(e.message)
          setDetailStudents([])
          setDetailLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [token, detailClubId])

  async function onSync() {
    if (!token || syncing) return
    setSyncing(true)
    setErr(null)
    setMsg(null)
    try {
      const r = await syncSheets(token)
      const counts = `학생 ${r.students_upserted ?? 0}명 · 동아리 ${r.clubs_upserted ?? 0}개`
      const pre =
        r.ok && r.preassignments_applied != null && r.preassignments_applied > 0
          ? ` · 시트 선정 반영 ${r.preassignments_applied}명`
          : ''
      setMsg(`${r.message} (${counts}${pre})`)
      load()
    } catch (e: unknown) {
      const aborted =
        (typeof DOMException !== 'undefined' && e instanceof DOMException && e.name === 'AbortError') ||
        (e instanceof Error && e.name === 'AbortError')
      if (aborted) {
        setErr('동기화 요청 시간 초과(3분). 서버·구글 시트 응답이 느립니다. 잠시 후 다시 시도하거나 Railway 로그를 확인하세요.')
      } else {
        setErr(e instanceof Error ? e.message : '동기화 실패')
      }
    } finally {
      setSyncing(false)
    }
  }

  async function onExportSheets() {
    if (!token || exportingSheets) return
    setExportingSheets(true)
    setErr(null)
    try {
      const r = await exportSheets(token)
      setMsg(r.message)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : '보내기 실패')
    } finally {
      setExportingSheets(false)
    }
  }

  if (!token) {
    return (
      <div className="layout">
        <p>로그인이 필요합니다.</p>
        <Link to="/admin/login">로그인</Link>
      </div>
    )
  }

  return (
    <div className="layout">
      <AdminNav
        token={token}
        tools={
          <>
            <a
              href="#csv"
              onClick={(e) => {
                e.preventDefault()
                if (token) {
                  fetch('/api/admin/export/csv', {
                    headers: { Authorization: `Bearer ${token}` },
                  })
                    .then((r) => r.blob())
                    .then((b) => {
                      const u = URL.createObjectURL(b)
                      const a = document.createElement('a')
                      a.href = u
                      a.download = 'applications.csv'
                      a.click()
                      URL.revokeObjectURL(u)
                    })
                }
              }}
            >
              CSV 받기
            </a>
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault()
                if (token) {
                  fetch('/api/admin/export/xlsx', {
                    headers: { Authorization: `Bearer ${token}` },
                  })
                    .then((r) => r.blob())
                    .then((b) => {
                      const u = URL.createObjectURL(b)
                      const a = document.createElement('a')
                      a.href = u
                      a.download = 'applications.xlsx'
                      a.click()
                      URL.revokeObjectURL(u)
                    })
                }
              }}
            >
              엑셀 받기
            </a>
          </>
        }
      />

      <div className="card card--accent">
        <h1 className="page-title">
          <span className="page-title__emoji" aria-hidden>
            ✨
          </span>
          관리자 대시보드
        </h1>
        <p className="page-lead">구글 시트와 맞추고, 한눈에 동아리 현황을 확인해요.</p>
        <div className="row" style={{ marginBottom: 4 }}>
          <button type="button" onClick={onSync} disabled={syncing}>
            {syncing ? '동기화 중… (구글·DB 처리로 1~2분 걸릴 수 있음)' : '학생/동아리 동기화'}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={onExportSheets}
            disabled={exportingSheets}
          >
            {exportingSheets ? '전송 중…' : '결과 → 구글 시트'}
          </button>
        </div>
        {msg && <p className="success">{msg}</p>}
        {err && <p className="error">{err}</p>}
        {d && (
          <div className="stat-row">
            <span className="stat-chip stat-chip--lavender">
              전체 <strong>{d.total_students}</strong>명
            </span>
            <span className="stat-chip stat-chip--mint">
              배정 완료 <strong>{d.applied_count}</strong>명
            </span>
            <span className="stat-chip stat-chip--peach">
              미배정 <strong>{d.unassigned_count}</strong>명
            </span>
            <span className="stat-chip stat-chip--sky">
              신청 창 <strong>{d.is_application_open ? '열림' : '닫힘'}</strong>
            </span>
          </div>
        )}
      </div>

      {d && (
        <div className="card">
          <h2 className="page-title" style={{ fontSize: '1.15rem' }}>
            동아리별 요약
          </h2>
          <p className="muted" style={{ marginTop: 0 }}>
            동아리 이름을 누르면 배정된 학생 명단이 펼쳐져요.
          </p>
          <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>동아리</th>
                <th>정원</th>
                <th>신청</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {d.clubs.map((c) => (
                <Fragment key={c.club_id}>
                  <tr>
                    <td>
                      <button
                        type="button"
                        className="link-button"
                        onClick={() =>
                          setDetailClubId((prev) =>
                            prev === c.club_id ? null : c.club_id,
                          )
                        }
                        aria-expanded={detailClubId === c.club_id}
                      >
                        {c.club_name}
                      </button>
                    </td>
                    <td>{c.capacity}</td>
                    <td>{c.applied}</td>
                    <td>{c.full ? '마감' : c.is_open ? '신청 가능' : '닫힘'}</td>
                  </tr>
                  {detailClubId === c.club_id && (
                    <tr className="club-detail-row">
                      <td colSpan={4}>
                        {detailLoading && <p className="muted">불러오는 중…</p>}
                        {detailErr && <p className="error">{detailErr}</p>}
                        {!detailLoading && !detailErr && (
                          <>
                            {detailStudents.length === 0 ? (
                              <p className="muted">배정된 학생이 없습니다.</p>
                            ) : (
                              <table className="nested-table">
                                <thead>
                                  <tr>
                                    <th>학번</th>
                                    <th>이름</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {detailStudents.map((s) => (
                                    <tr key={s.student_number}>
                                      <td>{s.student_number}</td>
                                      <td>{s.name}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}
    </div>
  )
}
