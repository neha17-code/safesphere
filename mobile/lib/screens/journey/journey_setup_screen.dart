import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../models/contact.dart';
import '../../services/contact_service.dart';
import '../../services/journey_service.dart';
import '../../services/location_service.dart';
import '../../services/notification_service.dart';
import 'active_journey_screen.dart';

class JourneySetupScreen extends StatefulWidget {
  const JourneySetupScreen({super.key});

  @override
  State<JourneySetupScreen> createState() => _JourneySetupScreenState();
}

class _JourneySetupScreenState extends State<JourneySetupScreen> {
  final _destination = TextEditingController();
  List<Contact> _contacts = [];
  final Set<int> _selected = {};
  TimeOfDay? _time;
  bool _share = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _loadContacts();
  }

  @override
  void dispose() {
    _destination.dispose();
    super.dispose();
  }

  void _toast(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _loadContacts() async {
    try {
      final all = await ContactService().getContacts();
      if (!mounted) return;
      setState(() => _contacts = all.where((c) => c.isConfirmed).toList());
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _pickTime() async {
    final t = await showTimePicker(context: context, initialTime: TimeOfDay.now());
    if (t != null) setState(() => _time = t);
  }

  DateTime _arrivalDateTime() {
    final now = DateTime.now();
    var arrival = DateTime(now.year, now.month, now.day, _time!.hour, _time!.minute);
    if (!arrival.isAfter(now)) arrival = arrival.add(const Duration(days: 1));
    return arrival;
  }

  Future<void> _start() async {
    if (_destination.text.trim().isEmpty) return _toast('Please enter your destination.');
    if (_selected.isEmpty) return _toast('Select at least one confirmed contact.');
    if (_time == null) return _toast('Please select your expected arrival time.');

    setState(() => _busy = true);
    try {
      if (_share && await LocationService.current() == null) {
        _toast('Location unavailable, so sharing is off for this journey.');
        _share = false;
      }
      final arrival = _arrivalDateTime();
      final journey = await JourneyService().start(
        destination: _destination.text.trim(),
        expectedArrival: arrival,
        contactIds: _selected.toList(),
        shareLocation: _share,
      );
      await NotificationService.showJourneyActive();
      await NotificationService.scheduleArrivalReminder(journey.expectedArrival);

      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          settings: const RouteSettings(name: '/active-journey'),
          builder: (_) => ActiveJourneyScreen(journey: journey),
        ),
      );
    } on ApiException catch (e) {
      _toast(e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Safety Journey')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Plan your journey', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text(
                'If you do not confirm arrival, SafeSphere alerts your contacts automatically, '
                'even if your phone is off.',
                style: TextStyle(fontSize: 15),
              ),
              const SizedBox(height: 24),
              const Text('Where are you going?', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              TextField(
                controller: _destination,
                decoration: const InputDecoration(
                    hintText: 'Enter your destination',
                    prefixIcon: Icon(Icons.location_on_outlined),
                    border: OutlineInputBorder()),
              ),
              const SizedBox(height: 24),
              const Text('Who should follow along?', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              if (_contacts.isEmpty)
                const Text('No confirmed contacts yet. Add one under Trusted Contacts and ask them to accept.',
                    style: TextStyle(color: Colors.black54))
              else
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
              const SizedBox(height: 24),
              const Text('When should you arrive?', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _pickTime,
                  icon: const Icon(Icons.access_time),
                  label: Text(_time == null ? 'Select expected arrival time' : _time!.format(context)),
                ),
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Share live location'),
                subtitle: const Text('Only during this journey. Deleted when you arrive safely.'),
                value: _share,
                onChanged: (v) => setState(() => _share = v),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                height: 54,
                child: ElevatedButton(
                  onPressed: _busy ? null : _start,
                  child: _busy
                      ? const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('START JOURNEY', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
