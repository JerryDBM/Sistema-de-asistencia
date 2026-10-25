import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../models/student.dart';

class StudentApi {
  StudentApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<Student> findByEmail(String email) async {
    final base = Uri.parse(AppConfig.apiBaseUrl);
    final uri = base.replace(
      pathSegments: [
        ...base.pathSegments.where((segment) => segment.isNotEmpty),
        'students',
        'by-email',
        email,
      ],
    );

    late final http.Response response;
    try {
      response = await _client.get(
        uri,
        headers: const {'Accept': 'application/json'},
      ).timeout(const Duration(seconds: 8));
    } on Exception {
      throw const StudentApiException(
        'No se pudo conectar con AulaCheck. Revisa que la API esté encendida y que la dirección sea correcta.',
      );
    }

    if (response.statusCode == 404) {
      throw const StudentApiException(
        'Ese correo no aparece registrado. Verifica que escribiste el correo institucional correcto.',
      );
    }
    if (response.statusCode != 200) {
      throw StudentApiException(
        'La API respondió con el código ${response.statusCode}. Inténtalo de nuevo.',
      );
    }

    try {
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      if (json is! Map<String, dynamic>) {
        throw const FormatException();
      }
      return Student.fromJson(json);
    } on FormatException {
      throw const StudentApiException('La API devolvió una respuesta que la app no pudo interpretar.');
    }
  }

  void close() => _client.close();
}

class StudentApiException implements Exception {
  const StudentApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
