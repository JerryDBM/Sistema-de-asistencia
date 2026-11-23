// Esta primera parte permite usar herramientas que ayudan a leer y preparar
// la información recibida desde Internet.
import 'dart:convert';
// "dart:convert" incluye funciones para transformar texto con formato JSON
// en información que una aplicación escrita en Dart puede comprender.

// Esta parte carga el paquete encargado de realizar solicitudes a Internet.
import 'package:http/http.dart' as http;
// Las instrucciones anteriores permiten escribir "http" para indicar que
// las solicitudes y respuestas se refieren al envío de datos por la web.

// Esta ruta trae la dirección de la API desde una configuración separada.
import '../config/app_config.dart';
// Esta ruta trae el modelo que representa los datos de un estudiante.
import '../models/student.dart';

// Esta clase reúne todas las operaciones necesarias para buscar estudiantes.
// Sus datos y funciones trabajan como una pequeña oficina especial de consultas.
class StudentApi {
  // Este es el constructor: recibe una conexión opcional y prepara el servicio.
  // Si no se entrega una conexión, la aplicación crea una automáticamente.
  StudentApi({http.Client? client}) : _client = client ?? http.Client();
  // "_client" guarda la conexión que se utilizará para comunicarse con la API.
  // El símbolo "_" indica que esta conexión es privada y solo se usa dentro de esta clase.
  final http.Client _client;

  // Esta función busca el perfil de un estudiante por medio de su correo.
  // Cuando termine, entregará un objeto Student con los datos encontrados.
  Future<Student> findByEmail(String email) async {
    // La palabra "async" permite que la función espere la respuesta del servidor.
    // "Future<Student>" significa que el resultado llegará más adelante.
    // "email" es el texto recibido con el correo que la persona desea buscar.

    // Primero se convierte la dirección configurada de la API en una dirección web.
    final base = Uri.parse(AppConfig.apiBaseUrl);
    // "final base" guarda esa dirección sin permitir que se cambie después.
    // "Uri.parse" transforma el texto escrito en una dirección que Internet entiende.
    // "AppConfig.apiBaseUrl" contiene la dirección principal configurada para la API.

    // Ahora se construye la dirección completa que realizará la búsqueda.
    final uri = base.replace(
      // "replace" conserva la dirección principal y modifica sus partes finales.
      // "pathSegments" contiene las partes escritas después del dominio web.
      pathSegments: [
        // Primero se conservan todas las partes existentes que no estén vacías.
        ...base.pathSegments.where((segment) => segment.isNotEmpty),
        // Luego se agrega "students" para indicar que se buscan estudiantes.
        'students',
        // Luego se agrega "by-email" para indicar que se buscará por correo.
        'by-email',
        // Finalmente se coloca el correo recibido como último dato de la dirección.
        email,
      ],
    );

    // Este paso reserva una variable para guardar la respuesta del servidor.
    // Se usa "late" porque la respuesta todavía no existe al comenzar la función.
    late final http.Response response;

    // "try" inicia un bloque para intentar realizar una acción que puede fallar.
    try {
      // Se envía una solicitud a la dirección creada anteriormente.
      response = await _client.get(
        // "await" hace que la función espere hasta recibir una respuesta.
        // "_client.get" realiza una solicitud de lectura a la API.
        uri,
        // "uri" indica exactamente qué dirección debe consultar la solicitud.
        headers: const {'Accept': 'application/json'},
        // El encabezado informa a la API que la app desea recibir información JSON.
      ).timeout(const Duration(seconds: 8));
      // Si pasan ocho segundos sin respuesta, se cancela la espera automáticamente.
      // Esto evita que la pantalla quede detenida esperando indefinidamente.

      // Si aparece cualquier problema relacionado con la conexión, se ejecuta esta parte.
    } on Exception {
      // Se reemplaza el problema técnico por un aviso sencillo para la persona.
      throw const StudentApiException(
        // "throw" indica que ocurrió un error y que la búsqueda no continuará.
        // "const" crea el mensaje como un texto que no cambiará durante su uso.
        'No se pudo conectar con AulaCheck. Revisa que la API esté encendida y que la dirección sea correcta.',
        // Este texto explica que puede haber fallado Internet o que la API no está disponible.
      );
    }

    // El servidor devuelve un código numérico que indica qué ocurrió con la solicitud.
    // El código 404 significa que el recurso solicitado no se encontró.
    if (response.statusCode == 404) {
      // Si no se encontró el correo, se muestra un aviso relacionado con el registro.
      throw const StudentApiException(
        'Ese correo no aparece registrado. Verifica que escribiste el correo institucional correcto.',
      );
    }

    // Cualquier código distinto de 200 indica que la solicitud no fue exitosa.
    // El código 200 significa que el servidor encontró y entregó correctamente la información.
    if (response.statusCode != 200) {
      // Se prepara un aviso que incluye el código recibido del servidor.
      throw StudentApiException(
        // Las llaves y el signo $ permiten insertar el número dentro del texto.
        'La API respondió con el código ${response.statusCode}. Inténtalo de nuevo.',
      );
    }

    // Cuando todo salió bien, se intenta convertir el texto recibido en datos utilizables.
    try {
      // "jsonDecode" convierte el JSON leído en estructuras de Dart.
      // "utf8.decode" convierte los bytes recibidos a texto con caracteres correctamente interpretados.
      // "response.bodyBytes" contiene los datos en bruto entregados por el servidor.
      final json = jsonDecode(utf8.decode(response.bodyBytes));

      // Esta comprobación verifica que el resultado tenga forma de objeto JSON.
      // En Dart, "Map<String, dynamic>" representa un conjunto de pares clave-valor.
      if (json is! Map<String, dynamic>) {
        // Si no tiene esa forma, se crea un error de formato para esta situación.
        throw const FormatException();
      }

      // Si el formato es correcto, se entregan los datos al modelo Student.
      // "fromJson" transforma las claves y valores recibidos en propiedades del estudiante.
      return Student.fromJson(json);

      // Si apareció un error de formato mientras se intentaba interpretar la respuesta:
    } on FormatException {
      // Se entrega un mensaje entendible en lugar de mostrar el error técnico.
      throw const StudentApiException(
        'La API devolvió una respuesta que la app no pudo interpretar.',
      );
    }
  }

  // Esta función cierra la conexión cuando ya no será necesaria.
  // Liberar recursos ayuda a evitar conexiones innecesarias abiertas.
  void close() => _client.close();
  // "void" indica que esta función no devuelve un resultado útil.
  // "=>" abreviadamente indica que se ejecutará la instrucción escrita a continuación.
  // "_client.close" termina la conexión HTTP creada para las consultas.
}
// La llave anterior finaliza la definición completa de la clase StudentApi.

// Esta clase representa los errores propios de las consultas realizadas al servicio.
// Implementar Exception permite que Dart reconozca esta clase como un tipo de error.
class StudentApiException implements Exception {
  // Este constructor recibe el texto que se mostrará como explicación del error.
  const StudentApiException(this.message);
  // "const" permite crear el error sin realizar trabajos adicionales en memoria.
  // "this.message" asigna el texto recibido a la variable que pertenece a esta clase.

  // Esta variable conserva el mensaje entendido por la aplicación y por la persona.
  final String message;
  // "final" significa que el mensaje no cambiará después de asignarse.
  // "String" indica que la variable contiene texto.

  // Esta función determina cómo se mostrará el error si se convierte a texto.
  @override
  String toString() => message;
  // "@override" indica que se está usando una presentación propia de este tipo de error.
  // "toString" entrega como texto el mensaje almacenado en lugar de datos técnicos.
}
// La llave anterior termina la definición de la clase StudentApiException.
