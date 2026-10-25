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


class ClassOut(BaseModel):
    nrc: str
    name: str
    start_time: time
    tolerance_minutes: int
    student_count: int


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
