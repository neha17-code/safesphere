import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api_client.dart';
import '../../services/contact_service.dart';
import '../../services/journey_service.dart';
import '../../services/location_service.dart';

class EmergencyScreen extends StatefulWidget {
  final int? journeyId; // set when opened from an active journey
  const EmergencyScreen({super.key, this.journeyId});

  @override
  State<EmergencyScreen> createState() => _EmergencyScreenState();
}

class _EmergencyScreenState extends State<EmergencyScreen> {
  bool _busy = false;
  int? _delivered; // null = not sent yet

  void _toast(String m) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));
  }

  Future<void> _send() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        scrollable: true,
        title: const Text('Send emergency alert?'),
        content: const Text('Your trusted contacts who accepted will be alerted with your location.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('CANCEL')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('SEND ALERT')),
        ],
      ),
    );
    if (ok != true) return;

    setState(() => _busy = true);
    try {
      final n = await JourneyService().emergency(journeyId: widget.journeyId);
      if (mounted) setState(() => _delivered = n);
    } on ApiException catch (e) {
      _toast('Alert NOT sent: ${e.message}. Use "SMS from my phone" below.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Works with no internet and no SMS provider: opens the phone's own SMS app,
  /// addressed to every saved contact, with the location link filled in. One tap to send.
  Future<void> _smsFromPhone() async {
    try {
      final contacts = await ContactService().getContacts(); // saved copy when offline
      if (contacts.isEmpty) return _toast('Add a trusted contact first.');

      final pos = await LocationService.current();
      final loc = pos == null ? '' : ' My location: https://maps.google.com/?q=${pos.latitude},${pos.longitude}';
      final body = 'EMERGENCY: I need help right now.$loc';
      final numbers = contacts.map((c) => c.phone).join(',');

      var opened = false;
      try {
        opened = await launchUrl(Uri.parse('sms:$numbers?body=${Uri.encodeComponent(body)}'));
      } catch (_) {
        opened = false;
      }
      if (!opened) _toast('Could not open the SMS app.');
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _call112() => launchUrl(Uri.parse('tel:112'));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Emergency')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          // scroll-safe: large system fonts / small screens can never overflow
          child: LayoutBuilder(
            builder: (context, c) => SingleChildScrollView(
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: c.maxHeight),
                child: IntrinsicHeight(child: _delivered == null ? _ready() : _result()),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _callButton() => SizedBox(
        width: double.infinity,
        height: 54,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
          onPressed: _call112,
          icon: const Icon(Icons.call),
          label: const Text('CALL 112', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        ),
      );

  Widget _smsButton() => SizedBox(
        width: double.infinity,
        height: 52,
        child: OutlinedButton.icon(
          onPressed: _smsFromPhone,
          icon: const Icon(Icons.sms_outlined),
          label: const Text('SMS FROM MY PHONE', style: TextStyle(fontWeight: FontWeight.bold)),
        ),
      );

  Widget _ready() => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 10),
          const Text('I need help right now', style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text(
            'SafeSphere alerts your trusted contacts who accepted, with your live location. '
            'It does not contact the police, so call 112 if you are in danger. '
            '"SMS from my phone" works even without internet.',
            style: TextStyle(fontSize: 15),
          ),
          const Spacer(),
          _callButton(),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton.icon(
              onPressed: _busy ? null : _send,
              icon: const Icon(Icons.emergency_outlined),
              label: _busy
                  ? const SizedBox(height: 22, width: 22, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('ALERT MY CONTACTS', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            ),
          ),
          const SizedBox(height: 12),
          _smsButton(),
        ],
      );

  Widget _result() {
    final reached = _delivered! > 0;
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(reached ? Icons.check_circle : Icons.error, size: 80, color: reached ? Colors.green : Colors.red),
        const SizedBox(height: 24),
        Text(
          reached ? 'Alert sent to $_delivered contact${_delivered == 1 ? "" : "s"}' : 'No one could be alerted',
          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 12),
        Text(
          reached
              ? 'Stay somewhere safe if you can. Call 112 if you are in immediate danger.'
              : 'SafeSphere could not deliver the alert. Send an SMS from your phone below and call 112 if you are in danger.',
          style: const TextStyle(fontSize: 16),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),
        _callButton(),
        const SizedBox(height: 12),
        _smsButton(),
        const SizedBox(height: 12),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('BACK')),
      ],
    );
  }
}
