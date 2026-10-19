from datetime import datetime, time
from sqlalchemy import (
    String, Integer, DateTime, Time, ForeignKey, UniqueConstraint, Text, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Student(Base):
    __tablename__ = "estudiantes"

    email: Mapped[str] = mapped_column(String(160), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Los NRC adjuntos se representan mediante la relación clase_estudiante,
    # no como una lista de texto, para mantener integridad referencial.
    classes: Mapped[list["Class"]] = relationship(
        secondary="clase_estudiante", back_populates="students"
    )


class User(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="professor")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    classes: Mapped[list["Class"]] = relationship(back_populates="professor")


class Class(Base):
    __tablename__ = "clases"

    nrc: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    professor_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )

    students: Mapped[list[Student]] = relationship(
        secondary="clase_estudiante", back_populates="classes"
    )
    professor: Mapped[User | None] = relationship(back_populates="classes")
    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="course")


class ClassStudent(Base):
    __tablename__ = "clase_estudiante"
    nrc: Mapped[str] = mapped_column(ForeignKey("clases.nrc", ondelete="CASCADE"), primary_key=True)
    student_email: Mapped[str] = mapped_column(
        ForeignKey("estudiantes.email", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AttendanceSession(Base):
    __tablename__ = "sesiones_asistencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nrc: Mapped[str] = mapped_column(ForeignKey("clases.nrc"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    course: Mapped[Class] = relationship(back_populates="sessions")
    attendance: Mapped[list["AttendanceRecord"]] = relationship(back_populates="session")


class AttendanceRecord(Base):
    __tablename__ = "asistencias"
    __table_args__ = (
        UniqueConstraint("session_id", "student_email", name="uq_asistencia_sesion_estudiante"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sesiones_asistencia.id", ondelete="CASCADE"), nullable=False
    )
    student_email: Mapped[str] = mapped_column(
        ForeignKey("estudiantes.email"), nullable=False
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="qr", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[AttendanceSession] = relationship(back_populates="attendance")
    student: Mapped[Student] = relationship()
