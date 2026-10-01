import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../models/journey.dart';
import '../../services/auth_service.dart';
import '../../services/journey_service.dart';
import '../../services/notification_service.dart';
import '../emergency/emergency_screen.dart';

class ActiveJourneyScreen extends StatefulWidget {
  final Journey journey;
  const ActiveJourneyScreen({super.key, required this.journey});

  @override
  State<ActiveJourneyScreen> createState() => _ActiveJourneyScreenState();
}

class _ActiveJourneyScreenState extends State<ActiveJourneyScreen> {
  final _service = JourneyService();
  late Journey _journey = widget.journey;
  bool _completed = false;
  bool _hasPins = false;
  Timer? _refreshTimer;
  Timer? _locationTimer;

  @override
  void initState() {
    super.initState();
    AuthService().me().then((u) {
      if (mounted) setState(() => _hasPins = u['has_pins'] == true);
    }).catchError((_) {});

    // Re-sync with the server every minute (countdown + escalation status).
    _refreshTimer = Timer.periodic(const Duration(minutes: 1), (_) => _sync());

    // NOTE: location is sent while the app is open. Continuous background tracking
    // needs an Android foreground service, which is listed as future work.
    if (_journey.shareLocation) {
      _service.pushLocation(_journey.id).catchError((_) {});
      _locationTimer = Timer.periodic(
        const Duration(minutes: 2),
        (_) => _service.pushLocation(_journey.id).catchError((_) {}),
      );
    }
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _locationTimer?.cancel();
    super.dispose();
  }

  void _toast(String msg) {
    if (!mounted) return; // screen may be closed by the time a slow request fails
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _sync() async {
    try {
      final j = await _service.getActive();
      if (!mounted) return;
      setState(() => j == null ? _completed = true : _journey = j);
    } catch (_) {/* offline: keep last known state */}
  }

  Future<String?> _askPin() {
    final c = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        scrollable: true,
        title: const Text('Enter your safety PIN'),
        content: TextField(
          controller: c,
          autofocus: true,
          obscureText: true,
          keyboardType: TextInputType.number,
          maxLength: 6,
          decoration: const InputDecoration(border: OutlineInputBorder(), counterText: ''),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('CANCEL')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, c.text), child: const Text('CONFIRM')),
        ],
      ),
    );
  }

  Future<void> _confirmArrival() async {
    String? pin;
    if (_hasPins) {
      pin = await _askPin();
      if (pin == null) return;
    } else {
      final yes = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Confirm arrival'),
          content: const Text('Are you safely at your destination?'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('NOT YET')),
            ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('YES, I AM SAFE')),
          ],
        ),
      );
      if (yes != true) return;
    }

    try {
      await _service.arrive(_journey.id, pin: pin);
      // Deliberately identical UI for safe PIN and duress PIN.
      await NotificationService.cancelJourneyNotifications();
      if (mounted) setState(() => _completed = true);
    } on ApiException catch (e) {
      _toast(e.message); // e.g. incorrect PIN, or no network -> journey stays active
    }
  }

  Future<void> _runningLate() async {
    final minutes = await showModalBottomSheet<int>(
      context: context,
      isScrollControlled: true, // lets the sheet rise above the keyboard
      builder: (_) => _LateSheet(currentEta: _journey.expectedArrival),
    );
    if (minutes != null) await _extendBy(minutes);
  }

  Future<void> _extendBy(int minutes) async {
    try {
      final j = await _service.extend(_journey.id, minutes);
      await NotificationService.scheduleArrivalReminder(j.expectedArrival);
      if (!mounted) return;
      setState(() => _journey = j);
      _toast('New expected arrival: ${TimeOfDay.fromDateTime(j.expectedArrival).format(context)}');
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  String _countdown() {
    final diff = _journey.expectedArrival.difference(DateTime.now());
    final mins = diff.inMinutes.abs();
    final text = mins >= 60 ? '${mins ~/ 60} h ${mins % 60} min' : '$mins min';
    return diff.isNegative ? '$text overdue' : '$text left';
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: _completed, // block Android back so an active journey is never "lost"
      child: Scaffold(
        appBar: AppBar(title: const Text('Active Journey'), automaticallyImplyLeading: false),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: _completed ? _completedView() : _activeView(),
          ),
        ),
      ),
    );
  }

  Widget _activeView() {
    final overdue = _journey.expectedArrival.isBefore(DateTime.now());
    final alerted = _journey.escalationStage >= 2;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 10),
        const Text('Your journey is active', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        Text(
          alerted
              ? 'Your contacts have been alerted. Confirm arrival so they know you are OK.'
              : overdue
                  ? 'You are past your expected arrival. Confirm you are safe or extend the time.'
                  : 'Your contacts are following along and will be alerted if you do not check in.',
          style: TextStyle(fontSize: 15, color: alerted ? Colors.red : null),
        ),
        const SizedBox(height: 24),
        _infoCard(Icons.location_on_outlined, 'Destination', _journey.destination),
        const SizedBox(height: 12),
        _infoCard(Icons.people_outline, 'Following you', _journey.contacts.map((c) => c.name).join(', ')),
        const SizedBox(height: 12),
        _infoCard(Icons.access_time, 'Expected arrival',
            '${TimeOfDay.fromDateTime(_journey.expectedArrival).format(context)}  ·  ${_countdown()}'),
        if (_journey.shareLocation) ...[
          const SizedBox(height: 12),
          _infoCard(Icons.my_location, 'Live location', 'Shared with your contacts'),
        ],
        const Spacer(),
        SizedBox(
          width: double.infinity,
          height: 54,
          child: ElevatedButton.icon(
            onPressed: _confirmArrival,
            icon: const Icon(Icons.check_circle_outline),
            label: const Text('I ARRIVED SAFELY', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          height: 48,
          child: OutlinedButton.icon(
            onPressed: _runningLate,
            icon: const Icon(Icons.more_time),
            label: const Text('RUNNING LATE'),
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          height: 52,
          child: OutlinedButton.icon(
            style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => EmergencyScreen(journeyId: _journey.id)),
            ).then((_) => _sync()),
            icon: const Icon(Icons.warning_amber_rounded),
            label: const Text('EMERGENCY', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
      ],
    );
  }

  Widget _completedView() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.check_circle, size: 80, color: Colors.green),
        const SizedBox(height: 24),
        const Text('Journey Completed',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
        const SizedBox(height: 12),
        const Text('Glad to know you arrived safely.', style: TextStyle(fontSize: 16), textAlign: TextAlign.center),
        const SizedBox(height: 40),
        SizedBox(
          width: double.infinity,
          height: 54,
          child: ElevatedButton(
            onPressed: () => Navigator.popUntil(context, (r) => r.isFirst),
            child: const Text('BACK TO HOME', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
      ],
    );
  }

  Widget _infoCard(IconData icon, String title, String value) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.black26)),
      child: Row(
        children: [
          Icon(icon, size: 28),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500)),
                const SizedBox(height: 4),
                Text(value, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


/// Bottom sheet: presets, custom minutes, or a new arrival time. Pops the extra minutes.
class _LateSheet extends StatefulWidget {
  final DateTime currentEta;
  const _LateSheet({required this.currentEta});

  @override
  State<_LateSheet> createState() => _LateSheetState();
}

class _LateSheetState extends State<_LateSheet> {
  static const _presets = [15, 30, 45, 60, 120, 180];
  static const _maxMinutes = 720; // 12 h per extension (server also caps at 48 h from now)

  final _custom = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _custom.dispose();
    super.dispose();
  }

  String _label(int m) {
    if (m < 60) return '+$m min';
    return m % 60 == 0 ? '+${m ~/ 60} h' : '+${m ~/ 60} h ${m % 60} min';
  }

  void _submitCustom() {
    final m = int.tryParse(_custom.text.trim());
    if (m == null || m < 5 || m > _maxMinutes) {
      setState(() => _error = 'Enter between 5 and $_maxMinutes minutes.');
      return;
    }
    Navigator.pop(context, m);
  }

  Future<void> _pickTime() async {
    final eta = widget.currentEta;
    final t = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(eta.add(const Duration(minutes: 30))),
    );
    if (t == null || !mounted) return;

    var candidate = DateTime(eta.year, eta.month, eta.day, t.hour, t.minute);
    if (!candidate.isAfter(eta)) candidate = candidate.add(const Duration(days: 1)); // past midnight
    final m = candidate.difference(eta).inMinutes;
    if (m < 5 || m > _maxMinutes) {
      setState(() => _error = 'Choose a time between 5 minutes and 12 hours after your current arrival time.');
      return;
    }
    Navigator.pop(context, m);
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 20, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('How much more time do you need?',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              Text('Current arrival: ${TimeOfDay.fromDateTime(widget.currentEta).format(context)}',
                  style: const TextStyle(color: Colors.black54)),
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _presets
                    .map((m) => ActionChip(label: Text(_label(m)), onPressed: () => Navigator.pop(context, m)))
                    .toList(),
              ),
              const SizedBox(height: 20),
              const Text('Or enter your own', style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _custom,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        hintText: 'Extra minutes, e.g. 25',
                        border: OutlineInputBorder(),
                      ),
                      onSubmitted: (_) => _submitCustom(),
                    ),
                  ),
                  const SizedBox(width: 10),
                  FilledButton(onPressed: _submitCustom, child: const Text('ADD')),
                ],
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _pickTime,
                  icon: const Icon(Icons.access_time),
                  label: const Text('PICK A NEW ARRIVAL TIME'),
                ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Text(_error!, style: const TextStyle(color: Colors.red)),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
