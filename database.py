"""Configuración y acceso a la base de datos que usa toda la aplicación."""

# `os` permite leer valores de configuración guardados en el sistema o en `.env`.
import os
# Carga las variables de configuración del archivo `.env`, si existe.
from dotenv import load_dotenv
# Crea el motor de conexión y las herramientas para abrir sesiones de base de datos.
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Lee el archivo `.env` para que sus datos estén disponibles con `os.getenv`.
load_dotenv()

# Cada variable se puede ajustar fuera del código; los valores entre comillas son los usados por defecto.
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "aulacheck")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Si DATABASE_URL está definida se usa tal cual (las pruebas automáticas usan
# SQLite así). Si no, se arma la conexión a MySQL con los datos de .env.
# Dirección completa de la base de datos: permite usar SQLite en pruebas o MySQL en el sistema real.
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
)

# Prepara la conexión compartida; `pool_pre_ping` comprueba que siga viva antes de reutilizarla.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
# Fabrica sesiones nuevas para que cada tarea pueda consultar y guardar sus propios datos.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase común que permite a SQLAlchemy conocer las tablas del sistema."""
    pass


def get_db():
    """Entrega una sesión de base de datos a una solicitud y la cierra al terminar."""
    # Abre una conexión lógica que usará la ruta web actual.
    db = SessionLocal()
    try:
        # `yield` entrega la conexión a FastAPI mientras procesa la solicitud.
        yield db
    finally:
        # Se ejecuta incluso si ocurre un error y evita dejar conexiones abiertas.
        db.close()
