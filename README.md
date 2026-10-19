AulaCheck es un sistema de asistencia académica en desarrollo con una API FastAPI y una interfaz de escritorio PySide6. Incluye inicio de sesión para administradores y profesores, administración de cuentas y asignación de clases.

> **Estado actual:** esta es una versión de desarrollo local. La integración completa con la aplicación Flutter, la lectura física del QR mediante ESP32-CAM y la validación criptográfica de tokens dinámicos todavía están pendientes.

## Funcionalidades actuales

### Interfaz de escritorio (PySide6)

- Consultar las clases disponibles en el backend.
- Acceso con cuenta de profesor; la cuenta debe estar activa.
- Gestionar estudiantes y asistencia solo en las clases asignadas al profesor.
- Consultar y gestionar los estudiantes vinculados a una clase.
- Vincular estudiantes mediante su correo institucional, siempre que estén registrados en la tabla `estudiantes`.
- Configurar la tolerancia de asistencia de una clase.
- Iniciar y finalizar sesiones de asistencia.
- Registrar asistencia manual desde la interfaz.
- Consultar la lista y el estado de asistencia de una sesión.
- Consultar sesiones anteriores e historial, según los datos disponibles en el backend.
- Exportar registros a CSV si se utiliza la opción de exportación de la interfaz.
- Actualizar los datos periódicamente: la interfaz documentada consulta el backend cada 30 segundos para reflejar cambios realizados desde la API o por otros medios, siempre que la vista correspondiente vuelva a cargar esos datos.

### Backend (FastAPI)

- Inicio de sesión con contraseñas almacenadas con hash y tokens de acceso.
- Rutas administrativas protegidas para crear, activar, desactivar, cambiar contraseña y eliminar profesores.
- Asignar cada clase a un profesor activo. Un profesor puede tener varias clases.
- Crear y consultar clases.
- Generar NRC para las nuevas clases.
- Vincular estudiantes a clases.
- Crear sesiones de asistencia.
- Registrar asistencia manual o intentos de registro por QR.
- Consultar las asistencias registradas.
- Finalizar sesiones y generar registros de ausencia para estudiantes sin asistencia.
- Exponer documentación interactiva mediante Swagger UI en `/docs`.

## Tecnologías

- Python
- FastAPI
- SQLAlchemy
- MySQL
- PyMySQL
- Uvicorn
- PySide6
- Requests
- PyJWT y pwdlib (hash de contraseñas)

## Requisitos previos

Cada integrante debe tener instalado:

- Python 3.10 o una versión compatible con las dependencias del proyecto.
- MySQL Server y MySQL Workbench (o un cliente equivalente).
- Git, si va a clonar el repositorio.

Los comandos siguientes se ejecutan desde la carpeta raíz del repositorio, donde se encuentran `main.py`, `requirements.txt`, `seed.py` y el archivo de la interfaz.

## 1. Descargar el proyecto

Si todavía no tienes el repositorio en tu computador, clónalo usando la URL del repositorio de AulaCheck:

```powershell
git clone URL_DEL_REPOSITORIO
cd NOMBRE_DE_LA_CARPETA
```

Sustituye `URL_DEL_REPOSITORIO` por la URL real de GitHub y `NOMBRE_DE_LA_CARPETA` por la carpeta creada al clonar. Si ya tienes el repositorio, abre PowerShell en su carpeta raíz.

## 2. Crear la base de datos

Inicia MySQL y ejecuta en MySQL Workbench:

```sql
CREATE DATABASE aulacheck
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Si la base de datos ya existe, no hace falta volver a crearla.

## 3. Crear el entorno e instalar dependencias

Abre PowerShell en la carpeta raíz del proyecto y ejecuta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install PySide6 requests
```

El último comando instala las dependencias de la interfaz si todavía no están incluidas en `requirements.txt`. Si PowerShell no permite activar el entorno virtual, puedes usar directamente su Python:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install PySide6 requests
```

Si el equipo tiene varias instalaciones de Python, asegúrate de utilizar el mismo intérprete para instalar dependencias y ejecutar el proyecto.

## 4. Configurar MySQL

Copia `.env.example` y crea un archivo llamado `.env` en la raíz del proyecto. Completa las credenciales de tu instalación local de MySQL:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=aulacheck
DB_USER=root
DB_PASSWORD=TU_CONTRASEÑA
CORS_ORIGINS=*
```

Cambia `DB_USER` y `DB_PASSWORD` según la configuración de tu computador. No compartas ni subas el archivo `.env` a GitHub, porque contiene credenciales locales.

## 5. Crear administrador y datos de prueba

Define `AUTH_SECRET_KEY` en `.env` con un valor aleatorio de al menos 32 caracteres. Puedes generarlo con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Guarda el resultado en la línea `AUTH_SECRET_KEY=` de `.env`. Con MySQL encendido y el entorno virtual activado, crea el primer administrador:

```powershell
python crear_admin.py
```

Para la prueba local puedes escribir usuario `admin` y contraseña `admin` (no uses esa contraseña fuera de pruebas locales). El asistente confirma los datos dos veces. Si ya existe un administrador, te ofrecerá restablecer sus credenciales. Después podrás agregar y administrar profesores desde la interfaz.

Opcionalmente puedes cargar los datos de muestra:

```powershell
python seed.py
```

El script carga estudiantes ficticios y una clase de ejemplo si está definido en `seed.py`. Al iniciar, la API crea tablas nuevas y agrega `professor_id` a instalaciones existentes; las clases previas quedan inicialmente sin asignar para que el administrador las asigne.

## 6. Ejecutar el sistema

La API y la interfaz gráfica se ejecutan en terminales separadas. Mantén ambas abiertas.

### Terminal 1: iniciar FastAPI

```powershell
python -m uvicorn main:app --reload
```

Direcciones locales:

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs
- Comprobación de estado: http://127.0.0.1:8000/health

Si el comando no encuentra `main`, comprueba que PowerShell esté ubicado en la carpeta que contiene `main.py`.

### Terminal 2: iniciar la aplicación de escritorio

Ejecuta:

```powershell
python interfaz.py
```

La pantalla presenta pestañas separadas para administrador y profesor. El profesor inicia sesión con el correo y contraseña que le asignó el administrador. La interfaz usa `http://127.0.0.1:8000` por defecto; se puede cambiar definiendo `AULACHECK_API_URL`.

## 7. Probar la interfaz

1. Inicia el backend y abre `interfaz.py`.
2. Inicia sesión como administrador, agrega un profesor con correo y contraseña, y crea/asigna una clase.
3. Cierra sesión e inicia como profesor con las credenciales creadas.
4. Vincula un estudiante cuyo correo ya esté registrado en `estudiantes`.
5. Inicia la sesión de asistencia y registra la asistencia desde la interfaz.
7. Para probar un registro externo, abre `/docs` y usa `GET /sessions?nrc=EL_NRC` para localizar la sesión. Utiliza el **ID de la sesión**, no el NRC, en las rutas `/sessions/{id}/...`.
8. Registra una asistencia desde `POST /sessions/{id}/attendance/manual` con un cuerpo como:

```json
{
  "email": "ana.martinez@utb.edu.co"
}
```

9. La interfaz actualiza sus datos cada 30 segundos. Espera ese intervalo para comprobar si el registro externo aparece; si no, utiliza la opción de recarga disponible en la interfaz y verifica primero que la API guardó el registro.
10. Finaliza la sesión y revisa el historial.

Para consultar una asistencia por SQL:

```sql
USE aulacheck;

SELECT
    e.full_name AS estudiante,
    e.email,
    s.nrc,
    a.registered_at,
    a.status,
    a.source
FROM asistencias AS a
JOIN estudiantes AS e ON e.email = a.student_email
JOIN sesiones_asistencia AS s ON s.id = a.session_id
ORDER BY a.registered_at DESC;
```

## Endpoints principales

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/health` | Comprobar que la API responde |
| `POST` | `/auth/login` | Iniciar sesión de administrador o profesor |
| `GET` | `/auth/me` | Consultar la cuenta autenticada |
| `GET/POST` | `/admin/professors` | Listar o crear profesores (solo administrador) |
| `PATCH` | `/admin/professors/{id}/status` | Activar o desactivar profesor |
| `PUT` | `/admin/professors/{id}/password` | Cambiar contraseña de profesor |
| `DELETE` | `/admin/professors/{id}` | Eliminar profesor; sus clases quedan sin asignar |
| `PATCH` | `/admin/classes/{nrc}/professor` | Asignar o reasignar profesor |
| `GET` | `/students/by-email/{email}` | Buscar estudiante (solo administrador) |
| `GET` | `/classes` | Listar clases visibles para la cuenta |
| `POST` | `/classes` | Crear clase y asignarla a un profesor (solo administrador) |
| `GET` | `/classes/{nrc}` | Consultar una clase |
| `PATCH` | `/classes/{nrc}/tolerance?tolerance_minutes=30` | Cambiar la tolerancia |
| `POST` | `/classes/{nrc}/students` | Vincular estudiante por correo |
| `GET` | `/classes/{nrc}/students` | Consultar estudiantes de una clase |
| `POST` | `/classes/{nrc}/sessions/start` | Iniciar sesión de asistencia |
| `POST` | `/sessions/{id}/attendance/scan` | Registrar un intento de asistencia por QR |
| `POST` | `/sessions/{id}/attendance/manual` | Registrar asistencia manual |
| `GET` | `/sessions/{id}/attendance` | Consultar registros de la sesión |
| `POST` | `/sessions/{id}/finish` | Finalizar sesión y registrar ausencias |
| `GET` | `/sessions?nrc=10001` | Consultar sesiones de una clase |

Consulta `/docs` para ver los esquemas y parámetros exactos de cada endpoint.

## Reglas actuales de la demo

- Cada clase tiene un NRC.
- Un estudiante debe estar registrado y vinculado a la clase para poder registrar su asistencia.
- No se permite más de un registro de asistencia por estudiante en la misma sesión.
- Los estados utilizados por el backend incluyen `present`, `tardy` y `absent`.
- La asistencia manual se identifica con el origen `manual`.
- Al finalizar una sesión, el backend registra como ausentes a los estudiantes que no tengan registro de asistencia.
- La interfaz consulta periódicamente la API para reflejar cambios guardados en el backend.

La lógica exacta de puntualidad depende de la hora programada de la clase, la tolerancia configurada y la implementación actual del backend. Revisa los resultados de la API al probar casos límite.

## Limitaciones y trabajo pendiente

- Integrar la aplicación móvil Flutter para generar y mostrar QR dinámicos.
- Implementar validación criptográfica y expiración real del token QR. El endpoint de escaneo disponible no debe considerarse una validación de seguridad completa mientras esto no esté implementado.
- Integrar la cámara ESP32-CAM y los indicadores LED físicos.
- Validar criptográficamente y expirar de forma real los tokens QR.
- Adoptar migraciones versionadas con Alembic y endurecer la configuración para producción.

## Seguridad

Este proyecto está pensado para desarrollo local y pruebas académicas. No uses contraseñas reales en archivos versionados, no subas `.env` ni credenciales a GitHub y no expongas el servidor de desarrollo directamente a Internet.
