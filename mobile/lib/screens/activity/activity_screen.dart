import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../services/status_service.dart';

/// The owner's record of every alert: what was sent, to whom, and whether it was really delivered.
class ActivityScreen extends StatefulWidget {
  const ActivityScreen({super.key});

  @override
  State<ActivityScreen> createState() => _ActivityScreenState();
}

class _ActivityScreenState extends State<ActivityScreen> {
  final _service = StatusService();
  List<Map<String, dynamic>> _events = [];
  bool _loading = true;
  String? _error;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load();
    _poll = Timer.periodic(const Duration(seconds: 15), (_) => _load());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final events = await _service.events();
      if (!mounted) return;
      setState(() {
        _events = events;
        _loading = false;
        _error = null;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.message;
      });
    }
  }

  static const _names = {
    'JOURNEY_STARTED': 'Journey started',
    'ARRIVED': 'Arrived safely',
    'EMERGENCY_ALERT': 'Emergency alert',
    'EMERGENCY_PRESSED': 'Emergency pressed',
    'UNSAFE_ALERT': 'Feel-unsafe alert',
    'CONSENT_REQUESTED': 'Invitation',
    'CONSENT_CONFIRMED': 'Contact accepted',
    'CONSENT_DECLINED': 'Contact declined',
    'NUDGED': 'Reminder sent to you',
    'CONTACTS_ALERTED': 'Contacts alerted (overdue)',
    'ESCALATED': 'Urgent alert (still overdue)',
    'EXTENDED': 'Running late',
    'DELAY_UPDATE': 'Delay update',
    'PUSH_ENABLED': 'Contact turned on notifications',
    'EMAIL_SAVED': 'Email saved',
  };

  bool _failed(String type) => type.endsWith('_FAILED');

  String _title(String type) {
    final base = _failed(type) ? type.substring(0, type.length - 7) : type;
    final name = _names[base] ?? base;
    return _failed(type) ? '$name: NOT delivered' : name;
  }

  String _when(String iso) {
    final t = DateTime.parse(iso).toLocal();
    return '${t.day}/${t.month} ${TimeOfDay.fromDateTime(t).format(context)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Activity')),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(child: Padding(padding: const EdgeInsets.all(20), child: Text(_error!)))
                : _events.isEmpty
                    ? const Center(child: Text('Nothing yet. Alerts and invitations will appear here.'))
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: ListView.separated(
                          padding: const EdgeInsets.all(16),
                          itemCount: _events.length,
                          separatorBuilder: (context, index) => const SizedBox(height: 8),
                          itemBuilder: (context, i) {
                            final e = _events[i];
                            final type = e['type'] as String;
                            final failed = _failed(type);
                            return ListTile(
                              tileColor: const Color(0xFFF3F3F6),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                              leading: Icon(failed ? Icons.error_outline : Icons.check_circle_outline,
                                  color: failed ? Colors.red : Colors.green),
                              title: Text(_title(type)),
                              subtitle: Text('${e['detail'] ?? ''}\n${_when(e['created_at'] as String)}'),
                              isThreeLine: true,
                            );
                          },
                        ),
                      ),
      ),
    );
  }
}
