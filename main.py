# ---------------------------------------------
# IMPORTACIONES: herramientas que usa el programa
# ---------------------------------------------

# Esta herramienta permite trabajar con fechas y horas, como la hora actual o el límite de tardanza.
from datetime import datetime, date, time, timedelta

# Esta herramienta permite leer configuraciones del sistema operativo, como los sitios permitidos por CORS.
import os

# Estas herramientas permiten crear una API web y responder a las solicitudes del navegador.
from fastapi import FastAPI, Depends, HTTPException, status

# Esta herramienta permite configurar CORS, es decir, qué páginas web pueden comunicarse con la API.
from fastapi.middleware.cors import CORSMiddleware

# Estas herramientas permiten construir consultas y operaciones para buscar datos en la base de datos.
from sqlalchemy import select, func

# Estas herramientas permiten manejar sesiones de base de datos y cargar datos relacionados.
from sqlalchemy.orm import Session, selectinload

# Esta herramienta permite detectar si se intentó guardar un registro duplicado.
from sqlalchemy.exc import IntegrityError

# Importa la configuración de la base de datos, el motor de conexión y una forma de pedir una sesión.
from database import Base, engine, get_db

# Importa las tablas u objetos que representan estudiantes, clases, matrículas, sesiones y asistencias.
from models import Student, Class, ClassStudent, AttendanceSession, AttendanceRecord

# Importa los formatos que definen qué datos pueden recibir o devolver las rutas de la API.
from schemas import (
    StudentOut, ClassCreate, ClassOut, EnrollStudent,
    SessionOut, AttendanceScan, ManualAttendance, AttendanceOut
)

# ---------------------------------------------
# CREACIÓN DE TABLAS Y CONFIGURACIÓN DE LA API
# ---------------------------------------------

# Esta línea crea automáticamente las tablas que todavía no existan en la base de datos.
# Es práctica para este prototipo; en un proyecto real se usaría un sistema de migraciones llamado Alembic.
Base.metadata.create_all(bind=engine)

# Crea la aplicación web principal y guarda su nombre, descripción y versión.
app = FastAPI(
    title="AulaCheck API",
    description="Backend inicial para clases, estudiantes y asistencia QR.",
    version="0.1.0",
)

# Lee desde el entorno qué páginas web pueden usar la API; si no existe, permite todas con el símbolo *.
origins_setting = os.getenv("CORS_ORIGINS", "*")

# Si se permite todo, usa una sola lista con *. Si no, separa la configuración por comas y elimina espacios vacíos.
origins = ["*"] if origins_setting == "*" else [o.strip() for o in origins_setting.split(",") if o.strip()]

# Activa la configuración CORS en la aplicación para permitir que otras páginas hagan solicitudes.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False if origins == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------
# FUNCIONES QUE ORGANIZAN Y PREPARAN LOS DATOS
# ---------------------------------------------


def class_to_out(db: Session, course: Class) -> ClassOut:
    """Convierte una clase de la base de datos al formato que reciben las pantallas."""
    # Cuenta cuántos estudiantes están matriculados en la misma NRC de esta clase.
    count = db.scalar(
        select(func.count()).select_from(ClassStudent).where(ClassStudent.nrc == course.nrc)
    ) or 0

    # Crea el objeto de salida con los datos visibles de la clase y la cantidad de estudiantes.
    return ClassOut(
        nrc=course.nrc,
        name=course.name,
        start_time=course.start_time,
        tolerance_minutes=course.tolerance_minutes,
        student_count=count,
    )


def attendance_to_out(record: AttendanceRecord) -> AttendanceOut:
    """Incluye los datos del estudiante en la respuesta de una asistencia."""
    # Convierte el registro interno a un formato con nombre y datos que puede mostrar la pantalla.
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
    """Busca la clase por su código y devuelve un error claro si no existe."""
    # Busca una clase usando su NRC como identificador principal.
    course = db.get(Class, nrc)

    # Si no se encontró ninguna clase, responde con el código de error 404 y un mensaje claro.
    if not course:
        raise HTTPException(status_code=404, detail=f"No existe la clase con NRC {nrc}.")

    # Si sí existe, devuelve la clase encontrada.
    return course


def get_session_or_404(db: Session, session_id: int) -> AttendanceSession:
    """Busca una toma de asistencia por su número o informa que no se encontró."""
    # Busca la sesión de asistencia por su número identificador.
    session = db.get(AttendanceSession, session_id)

    # Si no existe, informa que no se encontró esa sesión.
    if not session:
        raise HTTPException(status_code=404, detail="No existe esa sesión de asistencia.")

    # Si existe, devuelve los datos de la sesión.
    return session


def get_enrolled_student(db: Session, nrc: str, email: str) -> Student:
    """Comprueba que el correo exista y que esa persona esté matriculada en la clase."""
    # Limpia el correo quitando espacios externos y convirtiendo las letras a minúsculas.
    student = db.get(Student, email.strip().lower())

    # Si el correo no está registrado como estudiante, devuelve un error.
    if not student:
        raise HTTPException(status_code=404, detail="El correo no existe en la tabla estudiantes.")

    # Busca si el estudiante tiene una matrícula en la clase indicada por NRC.
    membership = db.get(ClassStudent, {"nrc": nrc, "student_email": student.email})

    # Si no tiene matrícula en esa clase, no puede registrar asistencia allí.
    if not membership:
        raise HTTPException(status_code=400, detail="El estudiante no está vinculado a esta clase.")

    # Si todas las comprobaciones pasan, devuelve el estudiante válido.
    return student


def record_attendance(db: Session, session: AttendanceSession, email: str, source: str) -> AttendanceRecord:
    """Valida la sesión, calcula el estado y guarda un único registro de asistencia."""
    # Impide registrar asistencia cuando la sesión ya fue cerrada.
    if session.status != "active":
        raise HTTPException(status_code=409, detail="La sesión ya está finalizada.")

    # Obtiene la clase asociada con la sesión y valida que el estudiante esté matriculado.
    course = get_class_or_404(db, session.nrc)
    student = get_enrolled_student(db, course.nrc, email)

    # Busca si ese estudiante ya registró asistencia dentro de esta misma sesión.
    existing = db.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_email == student.email,
        )
    )

    # Si ya existe un registro, rechaza el intento para evitar duplicados.
    if existing:
        raise HTTPException(status_code=409, detail="DUPLICATE: el estudiante ya tiene un registro en esta sesión.")

    # Obtiene la hora actual y prepara el cálculo del límite permitido.
    now = datetime.now()

    # Construye la hora de inicio programada usando la fecha de la sesión y la hora de la clase.
    scheduled_start = datetime.combine(session.started_at.date(), course.start_time)

    # Suma a la hora de inicio los minutos de tolerancia configurados para calcular el último instante permitido.
    deadline = scheduled_start + timedelta(minutes=course.tolerance_minutes)

    # Si el registro fue hecho manualmente por el profesor, lo marca como asistencia manual.
    if source == "manual":
        result_status = "manual"
        notes = "Asistencia añadida manualmente por el profesor."

    # Si el QR llegó antes o exactamente al límite, el estudiante está presente.
    elif now <= deadline:
        result_status = "present"
        notes = None

    # Si llegó después del límite, conserva el intento pero lo marca como tardanza.
    else:
        result_status = "tardy"
        notes = "Registro fuera del tiempo de tolerancia."

    # Construye el nuevo registro de asistencia con todos sus datos.
    record = AttendanceRecord(
        session_id=session.id,
        student_email=student.email,
        registered_at=now,
        status=result_status,
        source=source,
        notes=notes,
    )

    # Añade el registro nuevo a la lista pendiente de cambios de la base de datos.
    db.add(record)

    # Intenta guardar los cambios de forma segura.
    try:
        db.commit()

    # Si la base de datos detecta un duplicado, deshace el intento y devuelve un error.
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="DUPLICATE: el estudiante ya tiene un registro en esta sesión.")

    # Vuelve a cargar el registro desde la base de datos para incluir cualquier dato generado automáticamente.
    db.refresh(record)

    # Devuelve el registro ya guardado.
    return record


# ---------------------------------------------
# RUTAS PARA COMPROBAR Y CONSULTAR INFORMACIÓN
# ---------------------------------------------


@app.get("/health")
def health():
    """Permite comprobar rápidamente que el servicio web está encendido."""
    # Devuelve una respuesta sencilla que confirma que el servicio está funcionando.
    return {"status": "ok", "service": "AulaCheck API"}


@app.get("/students/by-email/{email}", response_model=StudentOut)
def find_student_by_email(email: str, db: Session = Depends(get_db)):
    """Busca el perfil por correo; la app usa esta ruta antes de crear el QR."""
    # Busca el estudiante después de eliminar espacios y convertir el correo a minúsculas.
    student = db.get(Student, email.strip().lower())

    # Si no existe ese correo, responde con un error claro.
    if not student:
        raise HTTPException(status_code=404, detail="Correo no encontrado en estudiantes.")

    # Si existe, devuelve los datos del estudiante.
    return student


@app.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    """Devuelve todas las clases ordenadas por nombre."""
    # Consulta todas las clases y las ordena alfabéticamente por nombre.
    courses = db.scalars(select(Class).order_by(Class.name)).all()

    # Convierte cada clase al formato de salida que espera la aplicación.
    return [class_to_out(db, course) for course in courses]


@app.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    """Crea una clase nueva y le asigna el siguiente código numérico disponible."""
    # Consulta los NRC actuales para poder generar el siguiente número disponible.
    existing_nrcs = db.scalars(select(Class.nrc)).all()

    # Conserva solamente los NRC que contienen únicamente números.
    numeric_nrcs = [int(n) for n in existing_nrcs if n.isdigit()]

    # Usa el número mayor existente y suma uno; si no hay números usa 10001 como primer NRC nuevo.
    nrc = str(max(numeric_nrcs, default=10000) + 1)

    # Construye una clase nueva con el NRC generado y los datos enviados por la aplicación.
    course = Class(
        nrc=nrc,
        name=payload.name.strip(),
        start_time=payload.start_time,
        tolerance_minutes=payload.tolerance_minutes,
    )

    # Añade la nueva clase a la base de datos.
    db.add(course)

    # Guarda de manera permanente la nueva clase.
    db.commit()

    # Recarga la clase para obtener todos los datos finales almacenados.
    db.refresh(course)

    # Devuelve la clase en el formato que puede leer la pantalla.
    return class_to_out(db, course)


@app.get("/classes/{nrc}", response_model=ClassOut)
def get_class(nrc: str, db: Session = Depends(get_db)):
    """Devuelve los datos de una clase específica."""
    # Busca la clase por NRC y la convierte al formato de salida.
    return class_to_out(db, get_class_or_404(db, nrc))


@app.patch("/classes/{nrc}/tolerance", response_model=ClassOut)
def update_tolerance(nrc: str, tolerance_minutes: int, db: Session = Depends(get_db)):
    """Cambia los minutos que se permiten después de la hora de inicio."""
    # Comprueba que los minutos estén entre cero y tres horas.
    if tolerance_minutes < 0 or tolerance_minutes > 180:
        raise HTTPException(status_code=422, detail="La tolerancia debe estar entre 0 y 180 minutos.")

    # Busca la clase existente por NRC.
    course = get_class_or_404(db, nrc)

    # Cambia solamente el valor de tolerancia de esa clase.
    course.tolerance_minutes = tolerance_minutes

    # Guarda el cambio en la base de datos.
    db.commit()

    # Recarga la clase para confirmar los datos guardados.
    db.refresh(course)

    # Devuelve la clase actualizada.
    return class_to_out(db, course)


@app.post("/classes/{nrc}/students", status_code=status.HTTP_201_CREATED)
def enroll_student(nrc: str, payload: EnrollStudent, db: Session = Depends(get_db)):
    """Agrega a una clase un estudiante que ya debe existir en el sistema."""
    # Verifica que la clase exista antes de matricular a alguien.
    course = get_class_or_404(db, nrc)

    # Limpia el correo recibido y lo convierte a minúsculas.
    email = payload.email.strip().lower()

    # Busca si el estudiante ya existe en la tabla de estudiantes.
    student = db.get(Student, email)

    # Si el correo no pertenece a ningún estudiante, devuelve un error.
    if not student:
        raise HTTPException(status_code=404, detail="Ese correo no existe en la tabla estudiantes.")

    # Busca si esta persona ya está vinculada a esta clase.
    membership = db.get(ClassStudent, {"nrc": nrc, "student_email": email})

    # Si ya está vinculada, evita crear la misma matrícula otra vez.
    if membership:
        raise HTTPException(status_code=409, detail="El estudiante ya pertenece a esta clase.")

    # Crea una nueva relación entre la clase y el estudiante.
    db.add(ClassStudent(nrc=nrc, student_email=email))

    # Guarda permanentemente esa relación en la base de datos.
    db.commit()

    # Confirma que la matrícula fue creada y devuelve la información principal.
    return {"message": "Estudiante vinculado a la clase.", "nrc": nrc, "student": student.full_name, "email": email}


@app.get("/classes/{nrc}/students", response_model=list[StudentOut])
def list_class_students(nrc: str, db: Session = Depends(get_db)):
    """Muestra, ordenados por nombre, los estudiantes matriculados en una clase."""
    # Verifica primero que la clase indicada exista.
    course = get_class_or_404(db, nrc)

    # Busca estudiantes vinculados a la clase y los ordena por nombre completo.
    return db.scalars(
        select(Student)
        .join(ClassStudent, Student.email == ClassStudent.student_email)
        .where(ClassStudent.nrc == course.nrc)
        .order_by(Student.full_name)
    ).all()


@app.post("/classes/{nrc}/sessions/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def start_session(nrc: str, db: Session = Depends(get_db)):
    """Abre la toma de asistencia, si la clase tiene estudiantes y no está abierta."""
    # Comprueba que la clase exista antes de abrir una sesión.
    course = get_class_or_404(db, nrc)

    # Busca si esa misma clase ya tiene una sesión abierta y activa.
    existing = db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.nrc == nrc,
            AttendanceSession.status == "active",
        )
    )

    # Si ya existe una sesión activa, impide iniciar otra para esa clase.
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya hay una sesión activa para este NRC (sesión {existing.id}).")

    # Cuenta cuántos estudiantes están matriculados en la clase.
    count = db.scalar(select(func.count()).select_from(ClassStudent).where(ClassStudent.nrc == nrc)) or 0

    # Si no hay estudiantes, no permite iniciar una toma de asistencia.
    if count == 0:
        raise HTTPException(status_code=400, detail="No se puede iniciar asistencia: la clase no tiene estudiantes.")

    # Crea una nueva sesión activa con la hora exacta en que fue iniciada.
    session = AttendanceSession(nrc=nrc, started_at=datetime.now(), status="active")

    # Añade la sesión a la base de datos.
    db.add(session)

    # Guarda la sesión de forma permanente.
    db.commit()

    # Recarga la sesión para obtener su número identificador generado.
    db.refresh(session)

    # Devuelve los datos de la sesión recién creada.
    return session


@app.post("/sessions/{session_id}/attendance/scan", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def register_qr_attempt(session_id: int, payload: AttendanceScan, db: Session = Depends(get_db)):
    """Registra como QR la asistencia enviada por la estación lectora."""
    # Comprueba que la sesión exista.
    session = get_session_or_404(db, session_id)

    # El QR contiene el correo; este correo llega ya leído dentro de payload.email.
    record = record_attendance(db, session, payload.email, source="qr")

    # Convierte el registro a datos visibles y lo devuelve como respuesta.
    return attendance_to_out(record)


@app.post("/sessions/{session_id}/attendance/manual", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
def add_manual_attendance(session_id: int, payload: ManualAttendance, db: Session = Depends(get_db)):
    """Registra manualmente la asistencia de un estudiante desde la pantalla docente."""
    # Comprueba que la sesión indicada exista.
    session = get_session_or_404(db, session_id)

    # Registra manualmente al estudiante usando su correo.
    record = record_attendance(db, session, payload.email, source="manual")

    # Convierte el registro a datos visibles y lo devuelve.
    return attendance_to_out(record)


@app.get("/sessions/{session_id}/attendance", response_model=list[AttendanceOut])
def list_session_attendance(session_id: int, db: Session = Depends(get_db)):
    """Devuelve todos los resultados de una sesión en orden de registro."""
    # Comprueba que la sesión exista antes de consultar sus registros.
    get_session_or_404(db, session_id)

    # Busca todos los registros de esta sesión y carga también los datos de cada estudiante.
    records = db.scalars(
        select(AttendanceRecord)
        .options(selectinload(AttendanceRecord.student))
        .where(AttendanceRecord.session_id == session_id)
        .order_by(AttendanceRecord.registered_at)
    ).all()

    # Convierte todos los registros al formato que puede mostrar la aplicación.
    return [attendance_to_out(record) for record in records]


@app.post("/sessions/{session_id}/finish", response_model=SessionOut)
def finish_session(session_id: int, db: Session = Depends(get_db)):
    """Cierra la toma y crea una marca de ausencia para cada estudiante sin registro."""
    # Busca la sesión y muestra un error si no existe.
    session = get_session_or_404(db, session_id)

    # Impide finalizar una sesión que ya había sido cerrada anteriormente.
    if session.status != "active":
        raise HTTPException(status_code=409, detail="La sesión ya estaba finalizada.")

    # Obtiene los datos de la clase asociada con la sesión.
    course = get_class_or_404(db, session.nrc)

    # Consulta la lista completa de matrículas de esa clase.
    roster = db.scalars(
        select(ClassStudent).where(ClassStudent.nrc == course.nrc)
    ).all()

    # Obtiene los correos de quienes ya tienen algún registro en esta sesión.
    registered_emails = set(db.scalars(
        select(AttendanceRecord.student_email).where(AttendanceRecord.session_id == session.id)
    ).all())

    # Recorre uno por uno a todos los estudiantes matriculados.
    for member in roster:
        # Si el estudiante no aparece entre los registrados, crea un registro de ausencia.
        if member.student_email not in registered_emails:
            db.add(AttendanceRecord(
                session_id=session.id,
                student_email=member.student_email,
                registered_at=None,
                status="absent",
                source="system",
                notes="Sin registro al finalizar la sesión.",
            ))

    # Cambia el estado de la sesión a finalizada.
    session.status = "finished"

    # Guarda la hora exacta en que se cerró la sesión.
    session.finished_at = datetime.now()

    # Guarda todos los cambios: ausencias y estado final de la sesión.
    db.commit()

    # Recarga la sesión desde la base de datos para devolver sus datos finales.
    db.refresh(session)

    # Devuelve la sesión ya finalizada.
    return session


@app.get("/sessions", response_model=list[SessionOut])
def list_sessions(nrc: str | None = None, db: Session = Depends(get_db)):
    """Lista las sesiones recientes, opcionalmente filtradas por el código de clase."""
    # Prepara una consulta que ordena las sesiones desde la más reciente a la más antigua.
    query = select(AttendanceSession).order_by(AttendanceSession.started_at.desc())

    # Si se indicó un NRC, agrega un filtro para mostrar únicamente sus sesiones.
    if nrc:
        query = query.where(AttendanceSession.nrc == nrc)

    # Ejecuta la consulta y devuelve todas las sesiones encontradas.
    return db.scalars(query).all()
