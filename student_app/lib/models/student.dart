/// Guarda los dos datos del perfil que necesita mostrar la app del estudiante.
class Student {
  /// Crea un perfil cuando ya se tienen el correo y el nombre completo.
  const Student({required this.email, required this.fullName});

  final String email;
  final String fullName;

  /// Convierte los datos recibidos del servidor en un perfil seguro para usar.
  factory Student.fromJson(Map<String, dynamic> json) {
    // Lee los campos que el servidor incluye en la respuesta.
    final email = json['email'];
    final fullName = json['full_name'];
    // Verifica que ambos datos sean texto antes de usarlos en la pantalla.
    if (email is! String || fullName is! String) {
      throw const FormatException('La respuesta de la API no contiene los datos del estudiante.');
    }
    return Student(email: email, fullName: fullName);
  }
}
