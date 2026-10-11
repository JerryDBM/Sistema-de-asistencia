# AulaCheck Backend

Backend inicial para el Sistema de Asistencia Académica mediante QR dinámicos.

## Tecnologías

- FastAPI
- SQLAlchemy
- MySQL
- PyMySQL
- Uvicorn

## 1. Crear la base de datos

En MySQL Workbench o en la consola de MySQL, ejecuta:

```sql
CREATE DATABASE aulacheck
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

## 2. Preparar Python

Abre PowerShell en esta carpeta y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activación del entorno, puedes omitir la activación y usar directamente:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Configurar la conexión

Copia `.env.example` y nombra la copia `.env`. Coloca el usuario y la contraseña de tu MySQL:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=aulacheck
DB_USER=root
DB_PASSWORD=TU_CONTRASEÑA
CORS_ORIGINS=*
```

No subas el archivo `.env` a GitHub. Contiene credenciales locales.

## 4. Crear tablas y cargar datos de prueba

La primera vez que arranca la API se crean las tablas automáticamente. Después, con MySQL encendido y el entorno activado:

```powershell
python seed.py
```

Esto carga estudiantes ficticios y una clase de prueba con NRC `10001`.

## 5. Ejecutar el backend

```powershell
python -m uvicorn main:app --reload
```

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs
- Comprobación: http://127.0.0.1:8000/health

## Endpoints iniciales

| Método | Ruta | Función |
|---|---|---|
| GET | `/health` | Comprobar que la API responde |
| GET | `/students/by-email/{email}` | Buscar estudiante por correo |
| GET | `/classes` | Listar clases |
| POST | `/classes` | Crear clase y generar NRC |
| PATCH | `/classes/{nrc}/tolerance?tolerance_minutes=30` | Actualizar tolerancia |
| POST | `/classes/{nrc}/students` | Vincular estudiante por correo |
| GET | `/classes/{nrc}/students` | Consultar estudiantes de una clase |
| POST | `/classes/{nrc}/sessions/start` | Iniciar sesión de asistencia |
| POST | `/sessions/{id}/attendance/scan` | Registrar intento de QR |
| POST | `/sessions/{id}/attendance/manual` | Añadir asistencia manual |
| GET | `/sessions/{id}/attendance` | Consultar registros de la sesión |
| POST | `/sessions/{id}/finish` | Finalizar sesión y marcar ausentes |
| GET | `/sessions?nrc=10001` | Consultar sesiones |

## Probar un flujo

1. Ejecuta `seed.py`.
2. Inicia la API y abre `/docs`.
3. Consulta `GET /classes`; toma el NRC `10001`.
4. Ejecuta `POST /classes/10001/sessions/start`.
5. Copia el `id` devuelto.
6. Ejecuta `POST /sessions/{id}/attendance/scan` con un correo inscrito:

```json
{
  "email": "ana.martinez@utb.edu.co",
  "token": "TOKEN-DE-PRUEBA"
}
```

7. Consulta `GET /sessions/{id}/attendance`.
8. Ejecuta `POST /sessions/{id}/finish`.

## Reglas actuales de la demo

- NRC generado automáticamente al crear una clase.
- Un estudiante solo se puede vincular una vez a la misma clase.
- Un estudiante debe pertenecer a la clase para registrar asistencia.
- Un estudiante no puede registrar dos veces en la misma sesión.
- `present`: registro dentro de la tolerancia.
- `tardy`: intento fuera de tolerancia; se guarda para mostrar la hora, pero no cuenta como asistencia válida.
- `manual`: asistencia añadida por el profesor.
- `absent`: estudiante sin registro al finalizar la sesión.

## Pendiente para la siguiente etapa

- Conectar la interfaz PySide6 con estos endpoints.
- Implementar validación criptográfica y expiración real del token QR generado en Flutter.
- Controlar el ESP32-CAM y los LED a través del backend.
- Añadir autenticación del profesor y migraciones de base de datos.

Este es un backend de desarrollo local, no una versión lista para producción.
