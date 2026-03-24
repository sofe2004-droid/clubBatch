const jsonHeaders = { 'Content-Type': 'application/json' }

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  }
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`
  }
  const res = await fetch(path, { ...options, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) {
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  if (res.status === 204) {
    return undefined as T
  }
  const ct = res.headers.get('content-type')
  if (ct?.includes('application/json')) {
    return (await res.json()) as T
  }
  return (await res.text()) as T
}

export type StudentVerifyRes = {
  access_token: string
  student_id: number
  name: string
  student_number: string
}

export function verifyStudent(student_number: string, name: string) {
  return apiFetch<StudentVerifyRes>('/api/student/verify', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ student_number, name }),
  })
}

export type ClubItem = {
  id: number
  club_code: string
  club_name: string
  teacher_name: string | null
  capacity: number
  current_count: number
  remaining: number
  description: string | null
  is_open: boolean
}

export function fetchClubs(token: string) {
  return apiFetch<ClubItem[]>('/api/student/clubs', { token })
}

export function fetchMyAssignment(token: string) {
  return apiFetch<{ club_name: string | null }>('/api/student/my-assignment', { token })
}

export type ApplyRes = {
  ok: boolean
  message: string
  club_name: string | null
  applied_at: string | null
}

export function applyClub(token: string, club_id: number) {
  return apiFetch<ApplyRes>('/api/student/apply', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ club_id }),
    token,
  })
}

export type AdminLoginRes = { access_token: string }

export function adminLogin(username: string, password: string) {
  return apiFetch<AdminLoginRes>('/api/admin/login', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ username, password }),
  })
}

export type Dashboard = {
  total_students: number
  applied_count: number
  unassigned_count: number
  is_application_open: boolean
  application_starts_at: string | null
  application_ends_at: string | null
  is_globally_closed: boolean
  clubs: {
    club_id: number
    club_name: string
    capacity: number
    applied: number
    is_open: boolean
    full: boolean
  }[]
}

export function fetchDashboard(token: string) {
  return apiFetch<Dashboard>('/api/admin/dashboard', { token })
}

export function syncSheets(token: string) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), 180_000)
  return apiFetch<{
    ok: boolean
    message: string
    students_upserted?: number
    clubs_upserted?: number
    preassignments_applied?: number
  }>('/api/admin/sync/sheets', {
    method: 'POST',
    token,
    signal: ctrl.signal,
  }).finally(() => clearTimeout(t))
}

export function patchSettings(
  token: string,
  body: {
    application_starts_at?: string | null
    application_ends_at?: string | null
    is_globally_closed?: boolean | null
  },
) {
  return apiFetch('/api/admin/settings', {
    method: 'PATCH',
    headers: jsonHeaders,
    body: JSON.stringify(body),
    token,
  })
}

export function fetchSettings(token: string) {
  return apiFetch<{
    application_starts_at: string | null
    application_ends_at: string | null
    is_globally_closed: boolean
  }>('/api/admin/settings', { token })
}

export function fetchUnassigned(token: string) {
  return apiFetch<{
    items: {
      student_id: number
      student_number: string
      name: string
      grade: number | null
      class_no: number | null
      reason: string
    }[]
  }>('/api/admin/unassigned', { token })
}

export type ClubAssignedStudentsRes = {
  club_id: number
  club_name: string
  students: { student_number: string; name: string }[]
}

export function fetchClubAssignedStudents(token: string, clubId: number) {
  return apiFetch<ClubAssignedStudentsRes>(
    `/api/admin/clubs/${clubId}/assigned-students`,
    { token },
  )
}

export function fetchAdminClubs(token: string) {
  return apiFetch<{
    items: {
      id: number
      club_name: string
      capacity: number
      current_count: number
      remaining: number
      is_open: boolean
    }[]
  }>('/api/admin/clubs', { token })
}

export function forceAssign(
  token: string,
  payload: {
    student_id: number
    club_id: number
    reason: string
    cancel_existing: boolean
    allow_over_capacity: boolean
  },
) {
  return apiFetch<{ ok: boolean; message: string }>('/api/admin/force-assign', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
    token,
  })
}

export type ApplicationListItem = {
  student_id: number
  application_id: number
  student_number: string
  name: string
  grade: number | null
  class_no: number | null
  club_id: number
  club_name: string
}

export function fetchApplications(token: string, q = '') {
  const qs = q ? `?${new URLSearchParams({ q })}` : ''
  return apiFetch<{ items: ApplicationListItem[]; total: number }>(
    `/api/admin/applications${qs}`,
    { token },
  )
}

export function cancelStudentApplicationAdmin(token: string, applicationId: number) {
  return apiFetch<{ ok: boolean; message: string }>(
    `/api/admin/applications/${applicationId}/cancel`,
    { method: 'POST', token },
  )
}

export function exportSheets(token: string) {
  return apiFetch<{ ok: boolean; message: string }>('/api/admin/export/sheets', {
    method: 'POST',
    token,
  })
}
