"""Prepara una API AulaCheck con SQLite temporal para las pruebas.

No necesita MySQL: DATABASE_URL se define antes de importar la aplicación.
"""
# Herramientas de Python para configurar el entorno y ubicar la carpeta del proyecto.
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def api_app(tmp_path_factory):
    """Crea una base SQLite temporal y carga la aplicación una sola vez por ejecución."""
    # Guarda la base de prueba en una carpeta temporal, separada de los datos reales.
    db_file = tmp_path_factory.mktemp("db") / "pruebas.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    import main  # noqa: E402  (se importa después de definir DATABASE_URL)
    return main.app


@pytest.fixture()
def client(api_app):
    """Cada prueba empieza con la base de datos vacía."""
    # Cliente local que simula solicitudes web sin abrir un servidor real.
    from fastapi.testclient import TestClient
    from database import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(api_app)


@pytest.fixture()
def db_session(api_app):
    """Abre la base temporal para que una prueba pueda preparar sus datos."""
    from database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def crear_clase(db, nrc, inicio, tolerancia, correos):
    """Prepara una clase y sus estudiantes para reutilizarlos en varias pruebas."""
    from models import Class, ClassStudent, Student
    for correo in correos:
        if not db.get(Student, correo):
            db.add(Student(email=correo, full_name=correo.split("@")[0].replace(".", " ").title()))
    db.add(Class(nrc=nrc, name=f"Clase {nrc}", start_time=inicio, tolerance_minutes=tolerancia))
    db.flush()
    for correo in correos:
        db.add(ClassStudent(nrc=nrc, student_email=correo))
    db.commit()


@pytest.fixture()
def sesion_a_tiempo(client, db_session):
    """Clase que empezó hace 1 minuto con 10 de tolerancia: un registro ahora es «presente»."""
    # La hora de inicio se fija un minuto atrás para que la asistencia sea puntual.
    nrc = "20001"
    inicio = (datetime.now() - timedelta(minutes=1)).time().replace(microsecond=0)
    crear_clase(db_session, nrc, inicio, 10, ["ana.martinez@utb.edu.co", "carlos.perez@utb.edu.co"])
    response = client.post(f"/classes/{nrc}/sessions/start")
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture()
def sesion_tarde(client, db_session):
    """Clase que empezó hace 2 horas con 10 de tolerancia: un registro ahora es «tarde»."""
    # La hora se fija dos horas atrás para comprobar el estado de llegada tarde.
    nrc = "20002"
    inicio = (datetime.now() - timedelta(hours=2)).time().replace(microsecond=0)
    crear_clase(db_session, nrc, inicio, 10, ["laura.gomez@utb.edu.co"])
    response = client.post(f"/classes/{nrc}/sessions/start")
    assert response.status_code == 201, response.text
    return response.json()["id"]


def foto_con_qr(texto, tamano=(640, 480), escala_qr=0.55, ruido=True):
    """Simula una foto de la ESP32-CAM: un QR sobre fondo gris, desenfocado y en JPEG."""
    import cv2
    import numpy as np
    import qrcode

    # Dibuja un QR, lo coloca en una foto simulada y añade imperfecciones de cámara.
    qr = qrcode.QRCode(border=4, box_size=10)
    qr.add_data(texto)
    qr.make(fit=True)
    imagen_qr = np.array(qr.make_image(fill_color="black", back_color="white").convert("L"))

    ancho, alto = tamano
    lado = int(min(ancho, alto) * escala_qr)
    imagen_qr = cv2.resize(imagen_qr, (lado, lado), interpolation=cv2.INTER_AREA)
    foto = np.full((alto, ancho), 120, dtype=np.uint8)
    y, x = (alto - lado) // 2, (ancho - lado) // 2
    foto[y:y + lado, x:x + lado] = imagen_qr
    if ruido:
        foto = cv2.GaussianBlur(foto, (3, 3), 0)
        rng = np.random.default_rng(1)
        foto = np.clip(foto.astype(np.int16) + rng.normal(0, 6, foto.shape), 0, 255).astype(np.uint8)
    ok, jpeg = cv2.imencode(".jpg", foto, [cv2.IMWRITE_JPEG_QUALITY, 70])
    assert ok
    return jpeg.tobytes()


def foto_sin_qr(tamano=(640, 480)):
    """Crea una imagen JPEG de prueba que contiene letras, pero ningún código QR."""
    import cv2
    import numpy as np
    foto = np.full((tamano[1], tamano[0], 3), 90, dtype=np.uint8)
    cv2.putText(foto, "sin QR", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
    ok, jpeg = cv2.imencode(".jpg", foto)
    return jpeg.tobytes()
