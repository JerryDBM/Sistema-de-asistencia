"""Define las tablas y relaciones donde se guardan estudiantes y asistencias."""

# Importa herramientas de Python para representar fechas completas y horas del día.
from datetime import datetime, time
# Importa los tipos de dato y reglas que se usarán en las columnas de la base de datos.
from sqlalchemy import (
    # Texto de longitud limitada, números enteros y fechas con o sin hora.
    String, Integer, DateTime, Time, ForeignKey, UniqueConstraint, Text
)
# Importa las herramientas de SQLAlchemy para declarar columnas y relaciones entre tablas.
from sqlalchemy.orm import Mapped, mapped_column, relationship
# Importa la clase base del proyecto, que permite a SQLAlchemy reconocer estos modelos.
from database import Base


# Define la información de una persona estudiante y la conecta con la tabla común del proyecto.
class Student(Base):
    """Tabla de personas que pueden consultar y registrar su asistencia."""
    # Indica el nombre con el que esta tabla aparecerá en la base de datos.
    __tablename__ = "estudiantes"

    # Guarda el correo como texto de hasta 160 caracteres y lo usa como identificador único.
    email: Mapped[str] = mapped_column(String(160), primary_key=True)
    # Guarda el nombre completo; nullable=False exige que siempre tenga un valor.
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Expone las clases asociadas a este estudiante como una lista de objetos Class.
    # La tabla intermedia conecta ambas tablas y back_populates enlaza la relación inversa.
    classes: Mapped[list["Class"]] = relationship(
        # Nombra la tabla que guarda qué estudiantes pertenecen a qué clases.
        secondary="clase_estudiante", back_populates="students"
    )


# Define la información de una asignatura o clase.
class Class(Base):
    """Tabla de clases con su hora de inicio y margen permitido de llegada."""
    # Indica el nombre de la tabla de clases en la base de datos.
    __tablename__ = "clases"

    # Guarda el código institucional como texto de hasta 12 caracteres y lo usa como identificador.
    nrc: Mapped[str] = mapped_column(String(12), primary_key=True)
    # Guarda el nombre de la asignatura como texto y exige que no quede vacío.
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Guarda la hora programada de inicio, sin incluir una fecha, y exige un valor.
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Guarda los minutos de tolerancia; si no se especifican, se usan 10.
    tolerance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # Guarda la fecha y hora de creación; datetime.now se ejecuta al crear el registro.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Permite obtener la lista de estudiantes de esta clase usando la tabla intermedia.
    students: Mapped[list[Student]] = relationship(
        # Usa la tabla de matrículas y enlaza esta relación con Student.classes.
        secondary="clase_estudiante", back_populates="classes"
    )
    # Permite obtener todas las sesiones de asistencia asociadas a esta clase.
    sessions: Mapped[list["AttendanceSession"]] = relationship(back_populates="course")


# Define la tabla intermedia que registra las inscripciones de estudiantes en clases.
class ClassStudent(Base):
    """Tabla intermedia que indica qué estudiantes pertenecen a cada clase."""
    # Indica el nombre de la tabla de matrículas en la base de datos.
    __tablename__ = "clase_estudiante"
    # El NRC apunta a una clase existente y, junto al correo, identifica una matrícula.
    nrc: Mapped[str] = mapped_column(ForeignKey("clases.nrc", ondelete="CASCADE"), primary_key=True)
    # El correo apunta a un estudiante existente; si se elimina, también se elimina su matrícula.
    student_email: Mapped[str] = mapped_column(
        # Hace que la eliminación del estudiante quite también esta inscripción.
        ForeignKey("estudiantes.email", ondelete="CASCADE"), primary_key=True
    )
    # Guarda cuándo se agregó la matrícula; usa la hora actual si no se indica otra.
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


# Define una toma de asistencia concreta para una clase.
class AttendanceSession(Base):
    """Un evento de toma de asistencia que se abre y se cierra para una clase."""
    # Indica el nombre de la tabla que almacena las sesiones.
    __tablename__ = "sesiones_asistencia"

    # Crea un número identificador único que la base de datos asigna automáticamente.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Guarda el NRC de la clase a la que pertenece la sesión y exige que se indique.
    nrc: Mapped[str] = mapped_column(ForeignKey("clases.nrc"), nullable=False)
    # Guarda la fecha y hora de apertura; usa el momento actual si no se especifica.
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    # Guarda cuándo terminó la sesión; puede quedar vacío mientras sigue abierta.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Guarda el estado de la sesión; comienza como "active" y no puede quedar vacío.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    # Permite acceder desde la sesión a la clase relacionada; course enlaza con Class.sessions.
    course: Mapped[Class] = relationship(back_populates="sessions")
    # Permite acceder a todos los registros individuales de esta sesión.
    attendance: Mapped[list["AttendanceRecord"]] = relationship(back_populates="session")


# Define un resultado de asistencia de una persona dentro de una sesión.
class AttendanceRecord(Base):
    """Un resultado individual de asistencia dentro de una sesión."""
    # Indica el nombre de la tabla donde se guardan los resultados.
    __tablename__ = "asistencias"
    # Configura reglas adicionales para toda la tabla.
    __table_args__ = (
        # Impide que el mismo estudiante tenga más de un registro en la misma sesión.
        UniqueConstraint("session_id", "student_email", name="uq_asistencia_sesion_estudiante"),
    )

    # Crea un número identificador único que la base de datos asigna automáticamente.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Guarda la sesión relacionada; la referencia debe existir y no puede faltar.
    session_id: Mapped[int] = mapped_column(
        # Si se elimina la sesión, también se eliminan sus registros de asistencia.
        ForeignKey("sesiones_asistencia.id", ondelete="CASCADE"), nullable=False
    )
    # Guarda el correo del estudiante relacionado y exige que corresponda a alguien existente.
    student_email: Mapped[str] = mapped_column(
        # Esta clave conecta el registro con la persona de la tabla estudiantes.
        ForeignKey("estudiantes.email"), nullable=False
    )
    # Guarda el momento del registro; puede quedar vacío, por ejemplo, si se marca ausencia.
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Guarda el resultado, por ejemplo presente, manual, tarde o ausente; exige un valor.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Guarda el medio del registro, como QR, docente o sistema; por defecto usa "qr".
    source: Mapped[str] = mapped_column(String(20), default="qr", nullable=False)
    # Guarda una nota opcional en texto largo; puede dejarse vacía.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Permite acceder a la sesión de la que forma parte este registro de asistencia.
    session: Mapped[AttendanceSession] = relationship(back_populates="attendance")
    # Permite acceder a los datos del estudiante asociado a este registro.
    student: Mapped[Student] = relationship()
