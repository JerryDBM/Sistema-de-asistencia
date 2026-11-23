"""Carga estudiantes ficticios para pruebas locales. Ejecutar una sola vez o cuando quieras completar datos."""
# Importa la conexión y el catálogo de tablas para preparar una base utilizable.
from database import SessionLocal, Base, engine
# Importa las tablas que se van a llenar con los datos de ejemplo.
from models import Student, Class, ClassStudent
# Permite definir la hora de inicio de la clase de muestra.
from datetime import time

# Crea las tablas si todavía no existen; no borra datos que ya están guardados.
Base.metadata.create_all(bind=engine)

# Lista de estudiantes inventados que sirven para probar el sistema localmente.
SAMPLE_STUDENTS = [
    ("Ana Martínez", "ana.martinez@utb.edu.co"),
    ("Carlos Pérez", "carlos.perez@utb.edu.co"),
    ("Laura Gómez", "laura.gomez@utb.edu.co"),
    ("Andrés Torres", "andres.torres@utb.edu.co"),
    ("Valentina Ruiz", "valentina.ruiz@utb.edu.co"),
    ("Daniel Herrera", "daniel.herrera@utb.edu.co"),
    ("Sofía Castro", "sofia.castro@utb.edu.co"),
    ("Mateo Díaz", "mateo.diaz@utb.edu.co"),
]

# Abre una sesión para realizar todas las inserciones de ejemplo.
db = SessionLocal()
try:
    # Recorre cada estudiante y evita agregarlo si ya estaba registrado.
    for name, email in SAMPLE_STUDENTS:
        if not db.get(Student, email):
            db.add(Student(full_name=name, email=email))
    # Guarda los estudiantes antes de crear los vínculos con la clase.
    db.commit()

    # Clase de ejemplo. Se crea vacía y después se vinculan los correos de prueba.
    course = db.get(Class, "10001")
    if not course:
        course = Class(nrc="10001", name="Computación e Interfaces", start_time=time(8, 0), tolerance_minutes=10)
        db.add(course)
        db.commit()

    # Vincula uno por uno los correos a la clase, sin duplicar vínculos existentes.
    for _, email in SAMPLE_STUDENTS:
        if not db.get(ClassStudent, {"nrc": "10001", "student_email": email}):
            db.add(ClassStudent(nrc="10001", student_email=email))
    # Confirma en la base todos los vínculos de matrícula creados.
    db.commit()
    # Informa en la consola cuál clase quedó lista para probar.
    print("Datos de prueba listos. Clase de ejemplo: NRC 10001.")
finally:
    # Cierra la sesión aun si algo falla durante la carga de datos.
    db.close()
