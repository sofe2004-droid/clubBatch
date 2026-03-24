import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { verifyStudent } from '../api'

const TOKEN_KEY = 'club_student_token'

export function StudentVerify() {
  const nav = useNavigate()
  const [sn, setSn] = useState('')
  const [name, setName] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setLoading(true)
    try {
      const res = await verifyStudent(sn.trim(), name.trim())
      sessionStorage.setItem(TOKEN_KEY, res.access_token)
      nav('/clubs', { replace: true })
    } catch (e2: unknown) {
      const raw = e2 instanceof Error ? e2.message : String(e2)
      const isMismatch =
        raw.includes('일치하지 않') ||
        raw.includes('학번과 이름') ||
        /학번.*이름|이름.*학번/.test(raw)
      if (isMismatch) {
        window.alert('학번 이름이 맞지 않습니다. 재입력')
        setSn('')
        setName('')
      } else {
        setErr(raw || '확인에 실패했습니다.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="layout layout-student">
      <div className="card card--hello">
        <div className="result-blob">
          <div className="result-blob__icon" aria-hidden>
            🌸
          </div>
        </div>
        <h1 className="page-title" style={{ textAlign: 'center' }}>
          본인 확인
        </h1>
        <p className="page-lead" style={{ textAlign: 'center' }}>
          학번과 이름을 구글 시트 명단과 똑같이 적어 주세요.
        </p>
        <form onSubmit={onSubmit}>
          <label htmlFor="sn">학번</label>
          <input
            id="sn"
            value={sn}
            onChange={(e) => setSn(e.target.value)}
            autoComplete="off"
            required
          />
          <div style={{ height: 12 }} />
          <label htmlFor="nm">이름</label>
          <input id="nm" value={name} onChange={(e) => setName(e.target.value)} required />
          {err && <div className="error">{err}</div>}
          <div style={{ height: 16 }} />
          <button type="submit" disabled={loading} style={{ width: '100%' }}>
            {loading ? '로그인 중…' : '로그인'}
          </button>
        </form>
      </div>
    </div>
  )
}

export { TOKEN_KEY }
