import { useNavigate } from 'react-router-dom'
import { TOKEN_KEY } from '../pages/StudentVerify'

type Props = { clubName: string }

export function StudentAssignedComplete({ clubName }: Props) {
  const nav = useNavigate()

  function onConfirm() {
    sessionStorage.removeItem(TOKEN_KEY)
    nav('/', { replace: true })
  }

  const line = `${clubName}동아리에 배정 완료되었습니다`

  return (
    <div className="layout layout-student">
      <div className="card card--hello">
        <div className="result-blob">
          <div className="result-blob__icon" aria-hidden>
            🎉
          </div>
        </div>
        <h1 className="page-title" style={{ textAlign: 'center' }}>
          배정 완료
        </h1>
        <p
          className="success"
          style={{ textAlign: 'center', fontSize: '1.08rem', fontWeight: 700, marginTop: '0.35rem' }}
        >
          {line}
        </p>
        <p className="muted" style={{ textAlign: 'center', marginTop: '1rem' }}>
          확인을 누르면 로그인 화면으로 돌아갑니다.
        </p>
        <div style={{ marginTop: '1.25rem', textAlign: 'center' }}>
          <button type="button" onClick={onConfirm} style={{ minWidth: 200, padding: '0.65rem 1.5rem' }}>
            확인
          </button>
        </div>
      </div>
    </div>
  )
}
