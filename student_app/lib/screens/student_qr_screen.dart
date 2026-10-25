import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../models/student.dart';
import '../services/student_api.dart';

class StudentQrScreen extends StatefulWidget {
  const StudentQrScreen({super.key});

  @override
  State<StudentQrScreen> createState() => _StudentQrScreenState();
}

class _StudentQrScreenState extends State<StudentQrScreen> {
  final _emailController = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  final _api = StudentApi();
  Student? _student;
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _api.close();
    super.dispose();
  }

  Future<void> _loadStudent() async {
    if (!_formKey.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final student = await _api.findByEmail(_emailController.text.trim());
      if (!mounted) return;
      setState(() {
        _student = student;
        _loading = false;
      });
    } on StudentApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Ocurrió un problema inesperado. Inténtalo de nuevo.';
        _loading = false;
      });
    }
  }

  void _changeStudent() {
    setState(() {
      _student = null;
      _error = null;
      _emailController.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.qr_code_2_rounded, color: Color(0xFF3867E8)),
            SizedBox(width: 9),
            Text('AulaCheck'),
          ],
        ),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 220),
              child: _student == null ? _buildEntry() : _buildQrCard(_student!),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEntry() {
    return SingleChildScrollView(
      key: const ValueKey('entry'),
      padding: const EdgeInsets.fromLTRB(24, 28, 24, 32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.school_rounded, size: 54, color: Color(0xFF3867E8)),
          const SizedBox(height: 18),
          Text(
            'Tu asistencia, más fácil',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF172B4D),
                ),
          ),
          const SizedBox(height: 9),
          Text(
            'Escribe tu correo institucional para consultar tu perfil y mostrar tu código personal.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: const Color(0xFF667085)),
          ),
          const SizedBox(height: 28),
          Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextFormField(
                  controller: _emailController,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.done,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Correo institucional',
                    hintText: 'nombre@universidad.edu.co',
                    prefixIcon: Icon(Icons.email_outlined),
                  ),
                  onFieldSubmitted: (_) => _loadStudent(),
                  validator: (value) {
                    final email = value?.trim() ?? '';
                    if (email.isEmpty) return 'Escribe tu correo institucional.';
                    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(email)) {
                      return 'Revisa el formato del correo.';
                    }
                    return null;
                  },
                ),
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  _MessageBanner(message: _error!, isError: true),
                ],
                const SizedBox(height: 18),
                FilledButton.icon(
                  onPressed: _loading ? null : _loadStudent,
                  icon: _loading
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.arrow_forward_rounded),
                  label: Text(_loading ? 'Buscando perfil…' : 'Mostrar mi código'),
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(54),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const _MessageBanner(
            message: 'Este código es fijo y está asociado a tu correo. Muéstralo solo para registrar asistencia.',
            isError: false,
          ),
        ],
      ),
    );
  }

  Widget _buildQrCard(Student student) {
    return SingleChildScrollView(
      key: const ValueKey('qr'),
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Código de estudiante',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF172B4D),
                ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Presenta este código frente al lector de asistencia.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Color(0xFF667085)),
          ),
          const SizedBox(height: 22),
          Card(
            elevation: 0,
            color: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(24),
              side: const BorderSide(color: Color(0xFFE4E9F1)),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
              child: Column(
                children: [
                  CircleAvatar(
                    radius: 31,
                    backgroundColor: const Color(0xFFEAF0FF),
                    child: Text(
                      student.fullName.isEmpty ? '?' : student.fullName[0].toUpperCase(),
                      style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Color(0xFF3867E8)),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    student.fullName,
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: Color(0xFF172B4D)),
                  ),
                  const SizedBox(height: 4),
                  Text(student.email, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF667085))),
                  const SizedBox(height: 20),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: const Color(0xFFE9EDF4)),
                    ),
                    child: QrImageView(
                      data: student.email,
                      version: QrVersions.auto,
                      size: 238,
                      gapless: true,
                      errorCorrectionLevel: QrErrorCorrectLevel.M,
                      semanticsLabel: 'Código QR personal de ${student.fullName}',
                    ),
                  ),
                  const SizedBox(height: 18),
                  OutlinedButton.icon(
                    onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: student.email));
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Identificador copiado.')),
                      );
                    },
                    icon: const Icon(Icons.copy_rounded),
                    label: const Text('Copiar identificador'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          TextButton.icon(
            onPressed: _changeStudent,
            icon: const Icon(Icons.person_outline_rounded),
            label: const Text('Cambiar estudiante'),
          ),
        ],
      ),
    );
  }
}

class _MessageBanner extends StatelessWidget {
  const _MessageBanner({required this.message, required this.isError});

  final String message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final color = isError ? const Color(0xFF9A3412) : const Color(0xFF315BD0);
    final background = isError ? const Color(0xFFFFF4E5) : const Color(0xFFEAF0FF);
    final icon = isError ? Icons.info_outline_rounded : Icons.qr_code_rounded;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(14)),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(message, style: TextStyle(color: color, height: 1.35))),
        ],
      ),
    );
  }
}
