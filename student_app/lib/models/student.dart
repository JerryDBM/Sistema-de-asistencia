class Student {
  const Student({required this.email, required this.fullName});

  final String email;
  final String fullName;

  factory Student.fromJson(Map<String, dynamic> json) {
    final email = json['email'];
    final fullName = json['full_name'];
    if (email is! String || fullName is! String) {
      throw const FormatException('La respuesta de la API no contiene los datos del estudiante.');
    }
    return Student(email: email, fullName: fullName);
  }
}
