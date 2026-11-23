"""Describe los datos que la API recibe y devuelve en sus mensajes."""

# Tipos de fecha y hora que acepta el intercambio de datos.
from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field


class StudentOut(BaseModel):
    """Datos públicos de un estudiante que se envían a la aplicación."""
    model_config = ConfigDict(from_attributes=True)
    # Correo con el que se identifica al estudiante.
    email: str
    # Nombre mostrado en las pantallas de AulaCheck.
    full_name: str


class ClassCreate(BaseModel):
    """Datos necesarios para crear una clase; también fija límites permitidos."""
    # Nombre que el docente asigna a la clase.
    name: str = Field(min_length=2, max_length=160)
    # Hora programada para el inicio.
    start_time: time
    # Margen para llegar tarde; debe estar entre cero y 180 minutos.
    tolerance_minutes: int = Field(default=10, ge=0, le=180)


class ClassOut(BaseModel):
    """Información de una clase que se devuelve a la interfaz."""
    # Código, nombre, hora, tolerancia y cantidad de estudiantes de la clase.
    nrc: str
    name: str
    start_time: time
    tolerance_minutes: int
    student_count: int


class EnrollStudent(BaseModel):
    """Correo del estudiante que se quiere vincular a una clase."""
    # Correo de un estudiante que ya debe existir en la base de datos.
    email: str


class SessionOut(BaseModel):
    """Información de una sesión de asistencia abierta o ya cerrada."""
    # Identificador de sesión, clase, horas y estado que se entrega a la interfaz.
    model_config = ConfigDict(from_attributes=True)
    id: int
    nrc: str
    started_at: datetime
    finished_at: datetime | None
    status: str


class AttendanceScan(BaseModel):
    """Correo leído desde el código QR del estudiante."""
    # Texto de correo leído desde el QR.
    email: str
    


class ManualAttendance(BaseModel):
    """Correo que el docente usa para registrar una asistencia manual."""
    # Correo del estudiante que el docente seleccionó manualmente.
    email: str


class AttendanceOut(BaseModel):
    """Información completa de un registro que la API devuelve a la interfaz."""
    # Datos que la interfaz necesita para mostrar quién asistió y cómo quedó su registro.
    id: int
    session_id: int
    student_email: str
    student_name: str
    registered_at: datetime | None
    status: str
    source: str
    notes: str | None
