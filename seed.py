"""Carga estudiantes ficticios para pruebas locales. Ejecutar una sola vez o cuando quieras completar datos."""
from database import SessionLocal, Base, engine
from models import Student, Class, ClassStudent
from datetime import time

Base.metadata.create_all(bind=engine)

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

db = SessionLocal()
try:
    for name, email in SAMPLE_STUDENTS:
        if not db.get(Student, email):
            db.add(Student(full_name=name, email=email))
    db.commit()

    # Clase de ejemplo. Se crea vacía y después se vinculan los correos de prueba.
    course = db.get(Class, "10001")
    if not course:
        course = Class(nrc="10001", name="Computación e Interfaces", start_time=time(8, 0), tolerance_minutes=10)
        db.add(course)
        db.commit()

    for _, email in SAMPLE_STUDENTS:
        if not db.get(ClassStudent, {"nrc": "10001", "student_email": email}):
            db.add(ClassStudent(nrc="10001", student_email=email))
    db.commit()
    print("Datos de prueba listos. Clase de ejemplo: NRC 10001.")
finally:
    db.close()
