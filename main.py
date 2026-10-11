from datetime import datetime, date, time, timedelta
import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError

from database import Base, engine, get_db
from models import Student, Class, ClassStudent, AttendanceSession, AttendanceRecord
from schemas import (
    StudentOut, ClassCreate, ClassOut, EnrollStudent,
    SessionOut, AttendanceScan, ManualAttendance, AttendanceOut
)

# Para un prototipo local crea las tablas automáticamente.
# En un entorno real conviene utilizar migraciones (Alembic).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AulaCheck API",
    description="Backend inicial para clases, estudiantes y asistencia QR.",
    version="0.1.0",
)

origins_setting = os.getenv("CORS_ORIGINS", "*")
origins = ["*"] if origins_setting == "*" else [o.strip() for o in origins_setting.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False if origins == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def get_class_or_404(db: Session, nrc: str) -> Class:
    course = db.get(Class, nrc)
    if not course:
        raise HTTPException(status_code=404, detail=f"No existe la clase con NRC {nrc}.")
    return course


def get_session_or_404(db: Session, session_id: int) -> AttendanceSession:
    session = db.get(AttendanceSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="No existe esa sesión de asistencia.")
    return session


def get_enrolled_student(db: Session, nrc: str, email: str) -> Student:
    student = db.get(Student, email.strip().lower())
    if not student:
        raise HTTPException(status_code=404, detail="El correo no existe en la tabla estudiantes.")
    membership = db.get(ClassStudent, {"nrc": nrc, "student_email": student.email})
    if not membership:
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
        raise HTTPException(status_code=409, detail="DUPLICATE: el estudiante ya tiene un registro en esta sesión.")

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
        # Se guarda el intento tardío para que el profesor vea la hora,
        # pero el estado tardy no cuenta como asistencia válida.
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
        raise HTTPException(status_code=409, detail="DUPLICATE: el estudiante ya tiene un registro en esta sesión.")
    db.refresh(record)
    return record


@app.get("/health")
def health():
    return {"status": "ok", "service": "AulaCheck API"}


@app.get("/students/by-email/{email}", response_model=StudentOut)
def find_student_by_email(email: str, db: Session = Depends(get_db)):
    student = db.get(Student, email.strip().lower())
    if not student:
        raise HTTPException(status_code=404, detail="Correo no encontrado en estudiantes.")
    return student


@app.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    courses = db.scalars(select(Class).order_by(Class.name)).all()
    return [class_to_out(db, course) for course in courses]


@app.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    # NRC generado para el prototipo. En producción puede venir del sistema académico.
    existing_nrcs = db.scalars(select(Class.nrc)).all()
    numeric_nrcs = [int(n) for n in existing_nrcs if n.isdigit()]
    nrc = str(max(numeric_nrcs, default=10000) + 1)
    course = Class(
        nrc=nrc,
        name=payload.name.strip(),
        start_time=payload.start_time,
        tolerance_minutes=payload.tolerance_minutes,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return class_to_out(db, course)


@app.get("/classes/{nrc}", response_model=ClassOut)
def get_class(nrc: str, db: Session = Depends(get_db)):
    return class_to_out(db, get_class_or_404(db, nrc))


@app.patch("/classes/{nrc}/tolerance", response_model=ClassOut)
def update_tolerance(nrc: str, tolerance_minutes: int, db: Session = Depends(get_db)):
    if tolerance_minutes < 0 or tolerance_minutes > 180:
        raise HTTPException(status_code=422, detail="La tolerancia debe estar entre 0 y 180 minutos.")
    course = get_class_or_404(db, nrc)
    course.tolerance_minutes = tolerance_minutes
    db.commit()
    db.refresh(course)
    return class_to_out(db, course)


@app.post("/classes/{nrc}/students", status_code=status.HTTP_201_CREATED)
def enroll_student(nrc: str, payload: EnrollStudent, db: Session = Depends(get_db)):
    course = get_class_or_404(db, nrc)
    email = payload.email.strip().lower()
    student = db.get(Student, email)
    if not student:
        raise HTTPException(status_code=404, detail="Ese correo no existe en la tabla estudiantes.")
    membership = db.get(ClassStudent, {"nrc": nrc, "student_email": email})
    if membership:
        raise HTTPException(status_code=409, detail="El estudiante ya pertenece a esta clase.")
    db.add(ClassStudent(nrc=nrc, student_email=email))
    db.commit()
    return {"message": "Estudiante vinculado a la clase.", "nrc": nrc, "student": student.full_name, "email": email}


@app.get("/classes/{nrc}/students", response_model=list[StudentOut])
def list_class_students(nrc: str, db: Session = Depends(get_db)):
    course = get_class_or_404(db, nrc)
    return db.scalars(
        select(Student)
        .join(ClassStudent, Student.email == ClassStudent.student_email)
        .where(ClassStudent.nrc == course.nrc)
        .order_by(Student.full_name)
    ).all()


@app.post("/classes/{nrc}/sessions/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(nrc: str, db: Session = Depends(get_db)):
    course = get_class_or_404(db, nrc)
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
def register_qr_attempt(session_id: int, payload: AttendanceScan, db: Session = Depends(get_db)):
    session = get_session_or_404(db, session_id)
    # TODO: validar payload.token cuando implementemos el generador de QR dinámico en Flutter.
    record = record_attendance(db, session, payload.email, source="qr")
    return attendance_to_out(record)


@app.post("/sessions/{session_id}/attendance/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def add_manual_attendance(session_id: int, payload: ManualAttendance, db: Session = Depends(get_db)):
    session = get_session_or_404(db, session_id)
    record = record_attendance(db, session, payload.email, source="manual")
    return attendance_to_out(record)


@app.get("/sessions/{session_id}/attendance", response_model=list[AttendanceOut])
def list_session_attendance(session_id: int, db: Session = Depends(get_db)):
    get_session_or_404(db, session_id)
    records = db.scalars(
        select(AttendanceRecord)
        .options(selectinload(AttendanceRecord.student))
        .where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.registered_at)
    ).all()
    return [attendance_to_out(record) for record in records]


@app.post("/sessions/{session_id}/finish", response_model=SessionOut)
def finish_session(session_id: int, db: Session = Depends(get_db)):
    session = get_session_or_404(db, session_id)
    if session.status != "active":
        raise HTTPException(status_code=409, detail="La sesión ya estaba finalizada.")
    course = get_class_or_404(db, session.nrc)
    roster = db.scalars(
        select(ClassStudent).where(ClassStudent.nrc == course.nrc)
    ).all()
    registered_emails = set(db.scalars(
        select(AttendanceRecord.student_email).where(AttendanceRecord.session_id == session.id)
    ).all())
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
def list_sessions(nrc: str | None = None, db: Session = Depends(get_db)):
    query = select(AttendanceSession).order_by(AttendanceSession.started_at.desc())
    if nrc:
        query = query.where(AttendanceSession.nrc == nrc)
    return db.scalars(query).all()
