from datetime import datetime, timedelta
import re

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from auth_security import create_access_token, decode_access_token, hash_password, verify_password
from database import get_db
from models import AttendanceRecord, AttendanceSession, Class, ClassStudent, Student, User
from schema_updates import initialize_schema
from schemas import (
    AttendanceOut,
    AttendanceScan,
    ClassCreate,
    ClassOut,
    EnrollStudent,
    LoginOut,
    LoginRequest,
    ManualAttendance,
    ProfessorAssignment,
    ProfessorCreate,
    ProfessorPasswordUpdate,
    ProfessorStatusUpdate,
    SessionOut,
    StudentOut,
    UserOut,
)


initialize_schema()

app = FastAPI(
    title="AulaCheck API",
    description="API de asistencia académica con roles de administrador y profesor.",
    version="0.2.0",
)

origins_setting = __import__("os").getenv("CORS_ORIGINS", "*")
origins = ["*"] if origins_setting == "*" else [item.strip() for item in origins_setting.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False if origins == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Inicia sesión para continuar.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, RuntimeError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.role not in {"admin", "professor"}:
        raise unauthorized
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Esta operación requiere una cuenta de administrador.")
    return current_user


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=422, detail="Escribe un correo electrónico válido.")
    return normalized


def ensure_class_access(course: Class, user: User) -> None:
    if user.role == "professor" and course.professor_id != user.id:
        # Use 404 so an instructor cannot enumerate other professors' classes.
        raise HTTPException(status_code=404, detail="No existe la clase solicitada.")


def get_class_or_404(db: Session, nrc: str) -> Class:
    course = db.scalar(
        select(Class).options(selectinload(Class.professor)).where(Class.nrc == nrc)
    )
    if course is None:
        raise HTTPException(status_code=404, detail=f"No existe la clase con NRC {nrc}.")
    return course


def get_session_or_404(db: Session, session_id: int, user: User) -> AttendanceSession:
    session = db.get(AttendanceSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="No existe esa sesión de asistencia.")
    ensure_class_access(get_class_or_404(db, session.nrc), user)
    return session


def class_to_out(db: Session, course: Class) -> ClassOut:
    count = db.scalar(
        select(func.count()).select_from(ClassStudent).where(ClassStudent.nrc == course.nrc)
    ) or 0
    return ClassOut(
        nrc=course.nrc,
        name=course.name,
        start_time=course.start_time,
        tolerance_minutes=course.tolerance_minutes,
        student_count=count,
        professor_id=course.professor_id,
        professor_email=course.professor.email if course.professor else None,
    )


def attendance_to_out(record: AttendanceRecord) -> AttendanceOut:
    return AttendanceOut(
        id=record.id,
        session_id=record.session_id,
        student_email=record.student_email,
        student_name=record.student.full_name,
        registered_at=record.registered_at,
        status=record.status,
        source=record.source,
        notes=record.notes,
    )


def get_enrolled_student(db: Session, nrc: str, email: str) -> Student:
    student = db.get(Student, email.strip().lower())
    if student is None:
        raise HTTPException(status_code=404, detail="El correo no existe en la tabla estudiantes.")
    membership = db.get(ClassStudent, {"nrc": nrc, "student_email": student.email})
    if membership is None:
        raise HTTPException(status_code=400, detail="El estudiante no está vinculado a esta clase.")
    return student


def record_attendance(db: Session, session: AttendanceSession, email: str, source: str) -> AttendanceRecord:
    if session.status != "active":
        raise HTTPException(status_code=409, detail="La sesión ya está finalizada.")
    course = get_class_or_404(db, session.nrc)
    student = get_enrolled_student(db, course.nrc, email)
    existing = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_email == student.email,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="El estudiante ya tiene un registro en esta sesión.")

    now = datetime.now()
    scheduled_start = datetime.combine(session.started_at.date(), course.start_time)
    deadline = scheduled_start + timedelta(minutes=course.tolerance_minutes)
    if source == "manual":
        result_status = "manual"
        notes = "Asistencia añadida manualmente por el profesor."
    elif now <= deadline:
        result_status = "present"
        notes = None
    else:
        result_status = "tardy"
        notes = "Registro fuera del tiempo de tolerancia."

    record = AttendanceRecord(
        session_id=session.id,
        student_email=student.email,
        registered_at=now,
        status=result_status,
        source=source,
        notes=notes,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El estudiante ya tiene un registro en esta sesión.")
    db.refresh(record)
    return record


@app.get("/health")
def health():
    return {"status": "ok", "service": "AulaCheck API"}


@app.post("/auth/login", response_model=LoginOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.email.strip().lower()
    # Allow the explicitly selected local bootstrap username for the first admin.
    email = "admin" if identifier == "admin" else normalize_email(identifier)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
    try:
        token = create_access_token(user.id, user.role)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return LoginOut(access_token=token, user=UserOut.model_validate(user))


@app.get("/auth/me", response_model=UserOut)
def who_am_i(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/admin/professors", response_model=list[UserOut])
def list_professors(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.scalars(
        select(User).where(User.role == "professor").order_by(User.email)
    ).all()


@app.post("/admin/professors", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_professor(
    payload: ProfessorCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    email = normalize_email(payload.email)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")
    professor = User(
        email=email,
        password_hash=hash_password(payload.password),
        role="professor",
        is_active=payload.is_active,
    )
    db.add(professor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo.")
    db.refresh(professor)
    return professor


@app.patch("/admin/professors/{professor_id}/status", response_model=UserOut)
def update_professor_status(
    professor_id: int,
    payload: ProfessorStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    professor = db.get(User, professor_id)
    if professor is None or professor.role != "professor":
        raise HTTPException(status_code=404, detail="No existe ese profesor.")
    professor.is_active = payload.is_active
    db.commit()
    db.refresh(professor)
    return professor


@app.put("/admin/professors/{professor_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def change_professor_password(
    professor_id: int,
    payload: ProfessorPasswordUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    professor = db.get(User, professor_id)
    if professor is None or professor.role != "professor":
        raise HTTPException(status_code=404, detail="No existe ese profesor.")
    professor.password_hash = hash_password(payload.password)
    db.commit()


@app.delete("/admin/professors/{professor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_professor(
    professor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    professor = db.get(User, professor_id)
    if professor is None or professor.role != "professor":
        raise HTTPException(status_code=404, detail="No existe ese profesor.")
    for course in db.scalars(select(Class).where(Class.professor_id == professor_id)).all():
        course.professor_id = None
    db.delete(professor)
    db.commit()


@app.patch("/admin/classes/{nrc}/professor", response_model=ClassOut)
def assign_class_professor(
    nrc: str,
    payload: ProfessorAssignment,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    course = get_class_or_404(db, nrc)
    professor = db.get(User, payload.professor_id)
    if professor is None or professor.role != "professor" or not professor.is_active:
        raise HTTPException(status_code=422, detail="Selecciona un profesor activo.")
    course.professor_id = professor.id
    db.commit()
    db.refresh(course)
    return class_to_out(db, course)


@app.get("/students/by-email/{email}", response_model=StudentOut)
def find_student_by_email(
    email: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    student = db.get(Student, email.strip().lower())
    if student is None:
        raise HTTPException(status_code=404, detail="Correo no encontrado en estudiantes.")
    return student


@app.get("/classes", response_model=list[ClassOut])
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Class).options(selectinload(Class.professor)).order_by(Class.name)
    if current_user.role == "professor":
        query = query.where(Class.professor_id == current_user.id)
    return [class_to_out(db, course) for course in db.scalars(query).all()]


@app.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    professor = db.get(User, payload.professor_id)
    if professor is None or professor.role != "professor" or not professor.is_active:
        raise HTTPException(status_code=422, detail="Selecciona un profesor activo.")
    existing_nrcs = db.scalars(select(Class.nrc)).all()
    numeric_nrcs = [int(nrc) for nrc in existing_nrcs if nrc.isdigit()]
    nrc = str(max(numeric_nrcs, default=10000) + 1)
    course = Class(
        nrc=nrc,
        name=payload.name.strip(),
        start_time=payload.start_time,
        tolerance_minutes=payload.tolerance_minutes,
        professor_id=professor.id,
    )
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo generar el NRC. Intenta de nuevo.")
    db.refresh(course)
    return class_to_out(db, course)


@app.get("/classes/{nrc}", response_model=ClassOut)
def get_class(
    nrc: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = get_class_or_404(db, nrc)
    ensure_class_access(course, current_user)
    return class_to_out(db, course)


@app.patch("/classes/{nrc}/tolerance", response_model=ClassOut)
def update_tolerance(
    nrc: str,
    tolerance_minutes: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if tolerance_minutes < 0 or tolerance_minutes > 180:
        raise HTTPException(status_code=422, detail="La tolerancia debe estar entre 0 y 180 minutos.")
    course = get_class_or_404(db, nrc)
    ensure_class_access(course, current_user)
    course.tolerance_minutes = tolerance_minutes
    db.commit()
    db.refresh(course)
    return class_to_out(db, course)


@app.post("/classes/{nrc}/students", status_code=status.HTTP_201_CREATED)
def enroll_student(
    nrc: str,
    payload: EnrollStudent,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = get_class_or_404(db, nrc)
    ensure_class_access(course, current_user)
    email = payload.email.strip().lower()
    student = db.get(Student, email)
    if student is None:
        raise HTTPException(status_code=404, detail="Ese correo no existe en la tabla estudiantes.")
    if db.get(ClassStudent, {"nrc": nrc, "student_email": email}):
        raise HTTPException(status_code=409, detail="El estudiante ya pertenece a esta clase.")
    db.add(ClassStudent(nrc=nrc, student_email=email))
    db.commit()
    return {"message": "Estudiante vinculado a la clase.", "nrc": nrc, "student": student.full_name, "email": email}


@app.get("/classes/{nrc}/students", response_model=list[StudentOut])
def list_class_students(
    nrc: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = get_class_or_404(db, nrc)
    ensure_class_access(course, current_user)
    return db.scalars(
        select(Student)
        .join(ClassStudent, Student.email == ClassStudent.student_email)
        .where(ClassStudent.nrc == course.nrc)
        .order_by(Student.full_name)
    ).all()


@app.post("/classes/{nrc}/sessions/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(
    nrc: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = get_class_or_404(db, nrc)
    ensure_class_access(course, current_user)
    existing = db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.nrc == nrc,
            AttendanceSession.status == "active",
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya hay una sesión activa para este NRC (sesión {existing.id}).")
    count = db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.nrc == nrc)) or 0
    if count == 0:
        raise HTTPException(status_code=400, detail="No se puede iniciar asistencia: la clase no tiene estudiantes.")
    session = AttendanceSession(nrc=nrc, started_at=datetime.now(), status="active")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.post("/sessions/{session_id}/attendance/scan", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def register_qr_attempt(
    session_id: int,
    payload: AttendanceScan,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_session_or_404(db, session_id, current_user)
    record = record_attendance(db, session, payload.email, source="qr")
    return attendance_to_out(record)


@app.post("/sessions/{session_id}/attendance/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def add_manual_attendance(
    session_id: int,
    payload: ManualAttendance,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_session_or_404(db, session_id, current_user)
    record = record_attendance(db, session, payload.email, source="manual")
    return attendance_to_out(record)


@app.get("/sessions/{session_id}/attendance", response_model=list[AttendanceOut])
def list_session_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_session_or_404(db, session_id, current_user)
    records = db.scalars(
        select(AttendanceRecord)
        .options(selectinload(AttendanceRecord.student))
        .where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.registered_at)
    ).all()
    return [attendance_to_out(record) for record in records]


@app.post("/sessions/{session_id}/finish", response_model=SessionOut)
def finish_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = get_session_or_404(db, session_id, current_user)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="La sesión ya estaba finalizada.")
    course = get_class_or_404(db, session.nrc)
    roster = db.scalars(select(ClassStudent).where(ClassStudent.nrc == course.nrc)).all()
    registered_emails = set(
        db.scalars(select(AttendanceRecord.student_email).where(AttendanceRecord.session_id == session.id)).all()
    )
    for member in roster:
        if member.student_email not in registered_emails:
            db.add(AttendanceRecord(
                session_id=session.id,
                student_email=member.student_email,
                registered_at=None,
                status="absent",
                source="system",
                notes="Sin registro al finalizar la sesión.",
            ))
    session.status = "finished"
    session.finished_at = datetime.now()
    db.commit()
    db.refresh(session)
    return session


@app.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    nrc: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AttendanceSession).order_by(AttendanceSession.started_at.desc())
    if current_user.role == "professor":
        query = query.join(Class, AttendanceSession.nrc == Class.nrc).where(Class.professor_id == current_user.id)
    if nrc:
        query = query.where(AttendanceSession.nrc == nrc)
    return db.scalars(query).all()
