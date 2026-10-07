import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/scroll_fill.dart';
import '../../models/contact.dart';
import '../../services/contact_service.dart';
import '../../services/journey_service.dart';
import '../../services/notification_service.dart';

class FeelUnsafeScreen extends StatefulWidget {
  const FeelUnsafeScreen({super.key});

  @override
  State<FeelUnsafeScreen> createState() => _FeelUnsafeScreenState();
}

class _FeelUnsafeScreenState extends State<FeelUnsafeScreen> {
  List<Contact> _contacts = [];
  final Set<int> _selected = {};
  bool _checkInArmed = false;

  @override
  void initState() {
    super.initState();
    _load();
    NotificationService.isCheckInPending().then((v) {
      if (mounted) setState(() => _checkInArmed = v);
    });
  }

  void _toast(String msg) {
    if (!mounted) return; // screen may be closed by the time a slow request fails
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _load() async {
    try {
      final all = (await ContactService().getContacts()).where((c) => c.isConfirmed).toList();
      if (!mounted) return;
      setState(() {
        _contacts = all;
        _selected.addAll(all.map((c) => c.id));
      });
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _notify() async {
    if (_selected.isEmpty) return _toast('No confirmed contacts to notify.');
    try {
      final results = await JourneyService().feelUnsafe(_selected.toList());
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          scrollable: true,
          title: Text(results.any((r) => r.ok) ? 'Your contacts were told' : 'No one could be reached'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: results.map((r) => Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(r.describe()))).toList(),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
        ),
      );
    } on ApiException catch (e) {
      _toast('Not sent: ${e.message}');
    }
  }

  Future<void> _toggleCheckIn() async {
    if (_checkInArmed) {
      await NotificationService.cancelCheckInReminder();
    } else {
      await NotificationService.scheduleCheckInReminder();
      _toast('We will check in with you in 15 minutes.');
    }
    if (mounted) setState(() => _checkInArmed = !_checkInArmed);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('I Feel Unsafe')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: ScrollFill(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Get support quietly', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text(
                'Not a full emergency. Your chosen contacts get an SMS that you feel unsafe, with your location.',
                style: TextStyle(fontSize: 15),
              ),
              const SizedBox(height: 24),
              const Text('Who should know?', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                children: _contacts
                    .map((c) => FilterChip(
                          label: Text(c.name),
                          selected: _selected.contains(c.id),
                          onSelected: (on) => setState(() => on ? _selected.add(c.id) : _selected.remove(c.id)),
                        ))
                    .toList(),
              ),
              const Spacer(),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: ElevatedButton.icon(
                  onPressed: _notify,
                  icon: const Icon(Icons.sms_outlined),
                  label: const Text('TELL MY CONTACTS', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: OutlinedButton.icon(
                  onPressed: _toggleCheckIn,
                  icon: Icon(_checkInArmed ? Icons.timer_off_outlined : Icons.timer_outlined),
                  label: Text(_checkInArmed ? 'CANCEL 15-MIN CHECK-IN' : 'START 15-MIN CHECK-IN',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          )),
        ),
      ),
    );
  }
}
