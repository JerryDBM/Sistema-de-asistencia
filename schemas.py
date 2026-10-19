from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    email: str
    full_name: str


class ClassCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    start_time: time
    tolerance_minutes: int = Field(default=10, ge=0, le=180)
    professor_id: int


class ClassOut(BaseModel):
    nrc: str
    name: str
    start_time: time
    tolerance_minutes: int
    student_count: int
    professor_id: int | None = None
    professor_email: str | None = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfessorCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    is_active: bool = True


class ProfessorStatusUpdate(BaseModel):
    is_active: bool


class ProfessorPasswordUpdate(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class ProfessorAssignment(BaseModel):
    professor_id: int


class EnrollStudent(BaseModel):
    email: str


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nrc: str
    started_at: datetime
    finished_at: datetime | None
    status: str


class AttendanceScan(BaseModel):
    email: str
    # El token se conectará a la validación del QR dinámico en una siguiente etapa.
    token: str | None = None


class ManualAttendance(BaseModel):
    email: str


class AttendanceOut(BaseModel):
    id: int
    session_id: int
    student_email: str
    student_name: str
    registered_at: datetime | None
    status: str
    source: str
    notes: str | None
