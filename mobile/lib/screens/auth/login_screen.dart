import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../services/auth_service.dart';
import '../home/home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  bool _registerMode = false;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final auth = AuthService();
      if (_registerMode) {
        await auth.register(_name.text.trim(), _email.text.trim(), _password.text, _phone.text.trim());
      } else {
        await auth.login(_email.text.trim(), _password.text);
      }
      if (!mounted) return;
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const HomeScreen()));
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 40),
              const Text('SafeSphere', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text(_registerMode ? 'Create your account' : 'Welcome back',
                  style: const TextStyle(fontSize: 17, color: Colors.black54)),
              const SizedBox(height: 28),
              if (_registerMode) ...[
                _field(_name, 'Your name', Icons.person_outline),
                _field(_phone, 'Your phone (+91...)', Icons.phone_outlined, type: TextInputType.phone),
              ],
              _field(_email, 'Email', Icons.email_outlined, type: TextInputType.emailAddress),
              _field(_password, 'Password (min 8 characters)', Icons.lock_outline, obscure: true),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_error!, style: const TextStyle(color: Colors.red)),
                ),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: ElevatedButton(
                  onPressed: _busy ? null : _submit,
                  child: _busy
                      ? const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2))
                      : Text(_registerMode ? 'CREATE ACCOUNT' : 'LOG IN',
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
              TextButton(
                onPressed: () => setState(() {
                  _registerMode = !_registerMode;
                  _error = null;
                }),
                child: Text(_registerMode ? 'I already have an account' : 'Create a new account'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController c, String hint, IconData icon,
      {bool obscure = false, TextInputType? type}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: TextField(
        controller: c,
        obscureText: obscure,
        keyboardType: type,
        decoration: InputDecoration(hintText: hint, prefixIcon: Icon(icon), border: const OutlineInputBorder()),
      ),
    );
  }
}
