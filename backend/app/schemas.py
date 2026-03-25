from datetime import datetime

from pydantic import BaseModel, Field


class StudentVerifyRequest(BaseModel):
    student_number: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)


class StudentVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student_id: int
    name: str
    student_number: str


class ClubListItem(BaseModel):
    id: int
    club_code: str
    club_name: str
    teacher_name: str | None
    capacity: int
    current_count: int
    remaining: int
    description: str | None
    is_open: bool

    model_config = {"from_attributes": True}


class ApplyRequest(BaseModel):
    club_id: int


class ApplyResponse(BaseModel):
    ok: bool
    message: str
    club_name: str | None = None
    applied_at: datetime | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = "admin"


class ApplicationSettingsOut(BaseModel):
    application_starts_at: datetime | None
    application_ends_at: datetime | None
    is_globally_closed: bool


class ApplicationSettingsUpdate(BaseModel):
    application_starts_at: datetime | None = None
    application_ends_at: datetime | None = None
    is_globally_closed: bool | None = None


class DashboardClubOut(BaseModel):
    club_id: int
    club_name: str
    capacity: int
    applied: int
    is_open: bool
    full: bool


class DashboardOut(BaseModel):
    total_students: int
    applied_count: int
    unassigned_count: int
    is_application_open: bool
    application_starts_at: datetime | None
    application_ends_at: datetime | None
    is_globally_closed: bool
    clubs: list[DashboardClubOut]


class AssignedStudentItem(BaseModel):
    student_number: str
    name: str


class ClubAssignedStudentsOut(BaseModel):
    club_id: int
    club_name: str
    students: list[AssignedStudentItem]


class ClubAdminUpdate(BaseModel):
    is_open: bool | None = None


class ForceAssignRequest(BaseModel):
    student_id: int
    club_id: int
    reason: str = Field(..., min_length=1, max_length=2000)
    cancel_existing: bool = True
    allow_over_capacity: bool = False


class SyncSheetsResponse(BaseModel):
    ok: bool
    message: str
    students_upserted: int = 0
    clubs_upserted: int = 0
    preassignments_applied: int = 0
