import 'package:flutter/material.dart';

import 'screens/student_qr_screen.dart';

void main() {
  runApp(const AulaCheckStudentApp());
}

class AulaCheckStudentApp extends StatelessWidget {
  const AulaCheckStudentApp({super.key});

  @override
  Widget build(BuildContext context) {
    const navy = Color(0xFF172B4D);
    const blue = Color(0xFF3867E8);

    return MaterialApp(
      title: 'AulaCheck Estudiante',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: blue,
          primary: blue,
          surface: const Color(0xFFF5F7FB),
        ),
        scaffoldBackgroundColor: const Color(0xFFF5F7FB),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFF5F7FB),
          foregroundColor: navy,
          centerTitle: false,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: Color(0xFFDDE3ED)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: Color(0xFFDDE3ED)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: const BorderSide(color: blue, width: 1.5),
          ),
        ),
      ),
      home: const StudentQrScreen(),
    );
  }
}
