import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/config.dart';
import '../../services/auth_service.dart';
import '../../services/notification_service.dart';
import '../../services/status_service.dart';
import '../activity/activity_screen.dart';
import '../auth/login_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _auth = AuthService();
  Map<String, dynamic>? _me;
  Map<String, dynamic>? _channels;

  @override
  void initState() {
    super.initState();
    _auth.me().then((u) {
      if (mounted) setState(() => _me = u);
    }).catchError((_) {});
    StatusService().channels().then((c) {
      if (mounted) setState(() => _channels = c);
    }).catchError((_) {});
  }

  String _channelsText() {
    final c = _channels;
    if (c == null) return 'Checking...';
    String f(String label, bool on) => '$label: ${on ? "ready" : "not set up"}';
    return '${f("Phone notifications", c["push"] == true)}\n${f("Email", c["email"] == true)}\n${f("SMS", c["sms"] == true)}';
  }

  void _toast(String m) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _setPins() async {
    final safe = TextEditingController();
    final duress = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Set safety PINs'),
        // Scrollable so the keyboard / large fonts can never overflow the dialog.
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Safe PIN: confirms arrival normally.\n'
                'Duress PIN: looks identical on screen but silently alerts your contacts. '
                'Use it if someone forces you to confirm.',
                style: TextStyle(fontSize: 13),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: safe,
                obscureText: true,
                keyboardType: TextInputType.number,
                maxLength: 6,
                decoration: const InputDecoration(labelText: 'Safe PIN (4-6 digits)', counterText: ''),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: duress,
                obscureText: true,
                keyboardType: TextInputType.number,
                maxLength: 6,
                decoration: const InputDecoration(labelText: 'Duress PIN (different)', counterText: ''),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('CANCEL')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('SAVE')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _auth.setPins(safe.text, duress.text);
      _toast('PINs saved.');
      final u = await _auth.me();
      if (mounted) setState(() => _me = u);
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _logout() async {
    await _auth.logout();
    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
        context, MaterialPageRoute(builder: (_) => const LoginScreen()), (_) => false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            if (_me != null)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.account_circle_outlined),
                title: Text(_me!['name'] as String),
                subtitle: Text(_me!['email'] as String),
              ),
            const Divider(),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.notifications_outlined),
              title: const Text('Notification permissions'),
              subtitle: const Text('Needed for arrival reminders and check-ins.'),
              onTap: () async {
                await NotificationService.requestPermissions();
                _toast('Permissions requested.');
              },
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.pin_outlined),
              title: const Text('Safety PIN & duress PIN'),
              subtitle: Text(_me?['has_pins'] == true ? 'Configured. Tap to change.' : 'Not set. Tap to set up.'),
              onTap: _setPins,
            ),
            const ListTile(
              contentPadding: EdgeInsets.zero,
              leading: Icon(Icons.cloud_outlined),
              title: Text('Server'),
              subtitle: Text(apiBaseUrl),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.notifications_active_outlined),
              title: const Text('Alert channels on the server'),
              subtitle: Text(_channelsText()),
              isThreeLine: true,
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.history),
              title: const Text('Activity'),
              subtitle: const Text('What was sent, to whom, and whether it worked'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ActivityScreen())),
            ),
            const Divider(),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.logout),
              title: const Text('Log out'),
              onTap: _logout,
            ),
          ],
        ),
      ),
    );
  }
}
