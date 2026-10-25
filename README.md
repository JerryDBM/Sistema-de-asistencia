# AulaCheck

Sistema local de asistencia académica. Incluye una API FastAPI conectada a MySQL, una interfaz de escritorio para el docente hecha con PySide6 y una app Flutter para que cada estudiante consulte y muestre su QR fijo.

## Estado actual

- El docente puede crear clases, vincular estudiantes existentes, iniciar y finalizar sesiones, registrar asistencia manual, consultar el historial y exportar un CSV.
- La app Flutter solicita el correo institucional a la API. Si ese correo está registrado, muestra el nombre y un QR fijo cuyo contenido es el correo.
- El endpoint QR del backend puede recibir un correo decodificado y registrar la asistencia, pero la cámara ESP32-CAM y el lector físico todavía no están integrados.
- El QR fijo se puede copiar. El prototipo no autentica que quien escribe el correo sea su dueño, así que no debe usarse como un mecanismo seguro de identidad.

## Componentes principales

| Ruta o archivo | Función |
|---|---|
| `main.py` | API FastAPI y reglas de clases, sesiones y asistencias. |
| `interfaz.py` | Aplicación de escritorio del docente. |
| `database.py` | Conexión y sesiones de SQLAlchemy para MySQL. |
| `models.py` | Tablas y relaciones de la base de datos. |
| `schemas.py` | Formatos y validación de datos de la API. |
| `seed.py` | Carga estudiantes y una clase ficticia para pruebas. |
| `student_app/` | Aplicación móvil Flutter del estudiante. |
| `.env.example` | Plantilla de variables de conexión a MySQL. |
| `requirements.txt` | Dependencias de Python para backend e interfaz. |

## Requisitos

- Windows 10 u 11.
- Python 3.10 o posterior; se recomienda Python 3.12.
- MySQL Server iniciado. MySQL Workbench es opcional, pero facilita crear la base de datos.
- Flutter SDK estable y agregado a `PATH`.
- Android Studio con Android SDK, Android SDK Command-line Tools, Platform Tools y un emulador Android. Si el build solicita un NDK específico, instala la versión exacta indicada por el error desde **SDK Manager → SDK Tools → Show Package Details → NDK (Side by side)**.
- VS Code con las extensiones **Python**, **Pylance**, **Flutter** y **Dart**.

Comprueba las herramientas con:

```powershell
python --version
flutter --version
flutter doctor
```

Para Android, acepta las licencias si `flutter doctor` las solicita:

```powershell
flutter doctor --android-licenses
```

## Preparación inicial

Ejecuta estos pasos una sola vez desde la carpeta raíz del repositorio, donde está `main.py`.

### 1. Crear la base de datos

Inicia MySQL y ejecuta en MySQL Workbench o en otro cliente SQL:

```sql
CREATE DATABASE aulacheck
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Si la base ya existe, omite este paso.

### 2. Crear el entorno de Python e instalar dependencias

Abre una terminal de PowerShell en la raíz del repositorio:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` incluye FastAPI, SQLAlchemy, PyMySQL, PySide6 y requests. No necesitas instalar PySide6 o requests por separado.

### 3. Configurar MySQL

Copia la plantilla y edita las credenciales:

```powershell
Copy-Item .env.example .env
```

En `.env`, completa `DB_USER` y `DB_PASSWORD` con los datos de tu MySQL local. El archivo `.env` está excluido de Git; no lo subas al repositorio.

### 4. Cargar datos ficticios (solo cuando sea necesario)

Con MySQL activo, desde la raíz del proyecto ejecuta:

```powershell
.\.venv\Scripts\python.exe seed.py
```

Esto crea tablas y agrega estudiantes de prueba y la clase de ejemplo con NRC `10001`. El script evita duplicar esos datos si vuelves a ejecutarlo. **No hace falta correr `seed.py` cada vez que inicias la aplicación.**

## Ejecutar toda la aplicación

Inicia MySQL primero. Después abre tres terminales de VS Code, todas en la carpeta raíz del proyecto, y deja abiertas las terminales de la API y de la interfaz.

### Terminal 1: API

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

La API queda en `http://127.0.0.1:8000`. Para comprobarla abre `http://127.0.0.1:8000/health`; la documentación interactiva está en `http://127.0.0.1:8000/docs`.

### Terminal 2: interfaz del docente

```powershell
.\.venv\Scripts\python.exe interfaz.py
```

La interfaz se conecta a `http://127.0.0.1:8000`, así que inicia la API antes de abrirla.

### Terminal 3: app del estudiante en Android

Primero inicia el emulador desde Android Studio (**Tools → Device Manager**, botón ▶). Confirma que Flutter lo detecte:

```powershell
cd student_app
flutter devices
```

En la primera ejecución o después de cambiar dependencias, instala los paquetes Flutter:

```powershell
flutter pub get
```

Luego inicia la app, reemplazando `emulator-5554` por el ID Android que muestre `flutter devices` si es distinto:

```powershell
flutter run -d emulator-5554
```

La app ya tiene configurada `http://10.0.2.2:8000` como dirección del backend para Android Emulator. `10.0.2.2` permite que el emulador llegue al computador anfitrión. El `AndroidManifest.xml` habilita HTTP sin cifrar para desarrollo local; para publicar la app se debe usar HTTPS y retirar esa excepción.

Si todavía no existe `student_app/android/`, genera una vez los archivos nativos desde `student_app/`:

```powershell
flutter create --platforms android .
```

Después revisa que `android/app/src/main/AndroidManifest.xml` tenga `android:usesCleartextTraffic="true"` dentro de `<application>` para que el emulador pueda consultar la API local por HTTP.

### Ejecutar en un teléfono Android físico (opcional)

Conecta el teléfono a la misma red Wi-Fi del computador y habilita la depuración USB. Inicia Uvicorn permitiendo conexiones de la red local:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 0.0.0.0
```

Desde `student_app`, pasa la IP local del computador (reemplaza el ejemplo por la IP real):

```powershell
flutter run -d <ID_DEL_TELEFONO> --dart-define=API_BASE_URL=http://192.168.1.20:8000
```

Puede ser necesario permitir el puerto 8000 en el Firewall de Windows. Usa HTTP solo en la red local de desarrollo.

## Probar el flujo

1. Inicia MySQL, la API y la interfaz del docente.
2. Abre la app Flutter en el emulador.
3. Escribe un correo existente, por ejemplo `ana.martinez@utb.edu.co` si cargaste el seed.
4. Pulsa **Mostrar mi código**. La app debe consultar el perfil y presentar su QR.
5. Para probar un correo que no exista, espera el mensaje indicando que no está registrado.

La app móvil **solo muestra** el QR. Para registrar asistencia escaneándolo se necesita una estación/lector que decodifique el correo y envíe `{"email":"correo@universidad.edu.co"}` a `POST /sessions/{id}/attendance/scan` mientras la sesión correspondiente esté activa. Esa integración física está pendiente. El docente sí puede registrar asistencia manualmente desde la interfaz.

## Endpoints principales

| Método | Ruta | Función |
|---|---|---|
| `GET` | `/health` | Verificar que la API responde. |
| `GET` | `/students/by-email/{email}` | Consultar un estudiante por correo. |
| `GET` | `/classes` | Listar clases. |
| `POST` | `/classes` | Crear una clase y generar su NRC. |
| `GET` | `/classes/{nrc}` | Consultar una clase. |
| `PATCH` | `/classes/{nrc}/tolerance?tolerance_minutes=30` | Cambiar la tolerancia. |
| `POST` | `/classes/{nrc}/students` | Vincular un estudiante existente a una clase. |
| `GET` | `/classes/{nrc}/students` | Listar estudiantes de una clase. |
| `POST` | `/classes/{nrc}/sessions/start` | Iniciar una sesión. |
| `POST` | `/sessions/{id}/attendance/scan` | Registrar un intento QR enviado por un lector. |
| `POST` | `/sessions/{id}/attendance/manual` | Registrar asistencia manual. |
| `GET` | `/sessions/{id}/attendance` | Consultar los registros de una sesión. |
| `POST` | `/sessions/{id}/finish` | Finalizar una sesión y marcar ausencias. |
| `GET` | `/sessions?nrc=10001` | Consultar sesiones, opcionalmente por clase. |

## Solución de problemas

- **`python` o `.venv` no se reconoce:** confirma que la terminal está en la raíz (donde existe `main.py`) y que ya ejecutaste `python -m venv .venv`.
- **Error de MySQL o `Access denied`:** verifica que el servicio MySQL esté iniciado y revisa `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` y `DB_PASSWORD` en `.env`.
- **La interfaz no conecta:** comprueba que Uvicorn siga activo y que `http://127.0.0.1:8000/health` abra en el computador.
- **El emulador no aparece:** abre el emulador en Android Studio y verifica con `flutter devices`; debe aparecer como Android y estar en línea.
- **La app Flutter no conecta:** abre `http://10.0.2.2:8000/health` en el navegador del emulador, comprueba que Uvicorn esté activo y verifica `android:usesCleartextTraffic="true"` dentro de `<application>` en el manifiesto Android principal.
- **Gradle dice que falta un NDK:** instala en Android Studio la versión exacta que aparece en el error desde **SDK Manager → SDK Tools → Show Package Details → NDK (Side by side)**.

## Seguridad y limitaciones

Este proyecto es un prototipo para desarrollo local y pruebas académicas. No uses contraseñas reales en archivos versionados ni expongas el servidor de desarrollo a Internet. El QR fijo contiene el correo institucional y puede copiarse; la consulta del correo no equivale a iniciar sesión ni autentica la identidad del estudiante. La autenticación, la conexión segura HTTPS y la estación ESP32-CAM están pendientes.
