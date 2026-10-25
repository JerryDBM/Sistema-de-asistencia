class AppConfig {
  AppConfig._();

  // En el emulador Android, 10.0.2.2 apunta al computador anfitrión.
  // Sobrescribir al ejecutar con --dart-define=API_BASE_URL=...
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
