// Importa las herramientas visuales de Flutter para crear la aplicación.
import 'package:flutter/material.dart';

// Importa la pantalla que muestra el código QR del estudiante.
import 'screens/student_qr_screen.dart';

// Flutter ejecuta esta función al abrir la aplicación: es el punto de partida.
void main() {
  // Crea la aplicación principal y pide a Flutter que la muestre.
  runApp(const AulaCheckStudentApp());
}

/// Describe la aplicación principal, su diseño general y su pantalla de inicio.
class AulaCheckStudentApp extends StatelessWidget {
  // Constructor de la aplicación; la llave permite a Flutter identificar este elemento.
  const AulaCheckStudentApp({super.key});

  @override

  /// Flutter usa este método para crear la interfaz que se verá en pantalla.
  Widget build(BuildContext context) {
    // Guarda el azul oscuro que se usará en textos y otros elementos.
    const navy = Color(0xFF172B4D);
    // Guarda el azul principal que se usará para destacar elementos.
    const blue = Color(0xFF3867E8);

    // MaterialApp reúne el estilo general y la pantalla inicial de la aplicación.
    return MaterialApp(
      // Define el nombre de la aplicación.
      title: 'AulaCheck Estudiante',
      // Oculta la marca de depuración que aparece durante el desarrollo.
      debugShowCheckedModeBanner: false,
      // Aquí se definen los estilos y colores compartidos por las pantallas.
      theme: ThemeData(
        // Activa la versión más reciente del estilo visual Material Design.
        useMaterial3: true,
        // Crea una paleta de colores para los elementos de la aplicación.
        colorScheme: ColorScheme.fromSeed(
          // Toma el azul principal como base para crear esa paleta.
          seedColor: blue,
          // Establece el color principal de botones y elementos destacados.
          primary: blue,
          // Establece un gris muy claro para los fondos de superficies.
          surface: const Color(0xFFF5F7FB),
        ),
        // Usa gris muy claro como fondo general de cada pantalla.
        scaffoldBackgroundColor: const Color(0xFFF5F7FB),
        // Define el aspecto que compartirán las barras de la parte superior.
        appBarTheme: const AppBarTheme(
          // Da a la barra superior el mismo fondo gris claro que las pantallas.
          backgroundColor: Color(0xFFF5F7FB),
          // Muestra los textos e iconos de la barra en azul oscuro.
          foregroundColor: navy,
          // Coloca el título al inicio de la barra, en vez de centrarlo.
          centerTitle: false,
        ),
        // Define el aspecto que compartirán los campos donde se escribe.
        inputDecorationTheme: InputDecorationTheme(
          // Activa un color de fondo dentro de los campos.
          filled: true,
          // El fondo de los campos será blanco.
          fillColor: Colors.white,
          // Define la forma y el borde normal de los campos.
          border: OutlineInputBorder(
            // Hace que las esquinas del borde sean redondeadas.
            borderRadius: BorderRadius.circular(14),
            // Pinta el borde con un gris claro.
            borderSide: const BorderSide(color: Color(0xFFDDE3ED)),
          ),
          // Define el borde que se ve cuando el campo está disponible para usarse.
          enabledBorder: OutlineInputBorder(
            // Redondea las esquinas del borde del campo disponible.
            borderRadius: BorderRadius.circular(14),
            // Pinta ese borde con un gris claro.
            borderSide: const BorderSide(color: Color(0xFFDDE3ED)),
          ),
          // Define el borde que se ve cuando la persona selecciona un campo.
          focusedBorder: OutlineInputBorder(
            // Mantiene redondeadas las esquinas del campo seleccionado.
            borderRadius: BorderRadius.circular(14),
            // Resalta el campo con azul y una línea algo más gruesa.
            borderSide: const BorderSide(color: blue, width: 1.5),
          ),
        ),
      ),
      // Muestra la pantalla del código QR cuando se abre la aplicación.
      home: const StudentQrScreen(),
    );
  }
}
