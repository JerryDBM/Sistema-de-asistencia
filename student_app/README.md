# App AulaCheck del estudiante

Aplicación Flutter que consulta un perfil mediante el correo institucional y muestra el QR fijo asociado a ese correo. El QR identifica al estudiante, pero todavía no reemplaza la autenticación ni está conectado a la cámara ESP32-CAM.

## Ejecución rápida en Android Emulator

Desde la carpeta `student_app`:

```powershell
flutter pub get
flutter devices
flutter run -d emulator-5554
```

Reemplaza `emulator-5554` por el ID Android que aparezca en `flutter devices`. Inicia primero el backend desde la raíz del repositorio. La app usa `http://10.0.2.2:8000` para conectar el emulador con la API local.

Para requisitos completos, configuración de MySQL, ejecución conjunta de API/interfaz/app y solución de problemas, consulta el [README principal](../README.md).
