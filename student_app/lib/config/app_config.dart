/// Contiene ajustes globales que usa la app para localizar el servidor AulaCheck.
class AppConfig {
  AppConfig._();

  // En el emulador Android, 10.0.2.2 apunta al computador anfitrión.
  // Sobrescribir al ejecutar con --dart-define=API_BASE_URL=...
  // Permite cambiar la dirección al iniciar la app; si no se cambia, usa el emulador Android.
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
