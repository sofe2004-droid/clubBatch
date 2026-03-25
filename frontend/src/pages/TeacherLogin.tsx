import { AdminLogin } from './AdminLogin'

export function TeacherLogin() {
  return (
    <AdminLogin
      title="교사 조회 로그인"
      pageLead="동아리별 배정 학생 명단만 확인할 수 있어요. (시트 동기화·강제배정 없음)"
      nextPath="/teacher"
      defaultUsername="teacher"
    />
  )
}
