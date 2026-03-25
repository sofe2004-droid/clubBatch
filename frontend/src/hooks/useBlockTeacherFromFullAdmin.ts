import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ADMIN_ROLE_KEY } from '../pages/AdminLogin'

/** 교사 조회 계정이 /admin/apps 등 전체 관리 메뉴로 들어가지 못하게 */
export function useBlockTeacherFromFullAdmin() {
  const nav = useNavigate()
  useEffect(() => {
    if (sessionStorage.getItem(ADMIN_ROLE_KEY) === 'teacher') {
      nav('/teacher', { replace: true })
    }
  }, [nav])
}
