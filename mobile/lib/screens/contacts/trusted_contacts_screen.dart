import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../models/contact.dart';
import '../../services/contact_service.dart';

class TrustedContactsScreen extends StatefulWidget {
  const TrustedContactsScreen({super.key});

  @override
  State<TrustedContactsScreen> createState() => _TrustedContactsScreenState();
}

class _TrustedContactsScreenState extends State<TrustedContactsScreen> {
  final _service = ContactService();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  List<Contact> _contacts = [];
  int _priority = 1;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    super.dispose();
  }

  void _toast(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _load() async {
    try {
      final list = await _service.getContacts();
      if (!mounted) return;
      setState(() {
        _contacts = list;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _loading = false);
      _toast(e.message);
    }
  }

  Future<void> _add() async {
    if (_name.text.trim().isEmpty || _phone.text.trim().isEmpty) {
      _toast('Enter a name and a phone number with country code, e.g. +91...');
      return;
    }
    try {
      await _service.addContact(
        name: _name.text.trim(),
        phone: _phone.text.trim(),
        priority: _priority,
      );
      _name.clear();
      _phone.clear();
      _toast('Invitation sent. They must accept before they can receive alerts.');
      await _load();
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _remove(Contact c) async {
    try {
      await _service.removeContact(c.id);
      await _load();
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _resend(Contact c) async {
    try {
      await _service.resend(c.id);
      _toast('Invitation re-sent to ${c.name}.');
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Color _chipColor(String consent) => switch (consent) {
        'CONFIRMED' => Colors.green,
        'DECLINED' => Colors.red,
        _ => Colors.orange,
      };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Trusted Contacts')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('People who look out for you',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text(
                'Each person gets an SMS invitation and must accept. They are alerted only after '
                'they accept, and they do not need to install the app.',
                style: TextStyle(fontSize: 15),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _name,
                decoration: const InputDecoration(
                    hintText: 'Name', prefixIcon: Icon(Icons.person_outline), border: OutlineInputBorder()),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                    hintText: 'Phone, e.g. +919876543210',
                    prefixIcon: Icon(Icons.phone_outlined),
                    border: OutlineInputBorder()),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: SegmentedButton<int>(
                      segments: const [
                        ButtonSegment(value: 1, label: Text('Alert first')),
                        ButtonSegment(value: 2, label: Text('Escalation')),
                      ],
                      selected: {_priority},
                      onSelectionChanged: (s) => setState(() => _priority = s.first),
                    ),
                  ),
                  const SizedBox(width: 10),
                  IconButton.filled(onPressed: _add, icon: const Icon(Icons.add), tooltip: 'Add contact'),
                ],
              ),
              const SizedBox(height: 16),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator())
                    : _contacts.isEmpty
                        ? const Center(child: Text('No trusted contacts yet.'))
                        : ListView.separated(
                            itemCount: _contacts.length,
                            separatorBuilder: (_, __) => const SizedBox(height: 10),
                            itemBuilder: (_, i) {
                              final c = _contacts[i];
                              return ListTile(
                                tileColor: const Color(0xFFF3F3F6),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                                title: Text(c.name),
                                subtitle: Text('${c.phone} · ${c.priority == 1 ? "alerted first" : "escalation"}'),
                                leading: Icon(Icons.circle, size: 14, color: _chipColor(c.consent)),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    if (!c.isConfirmed)
                                      IconButton(
                                        icon: const Icon(Icons.send_outlined),
                                        tooltip: 'Resend invitation (${c.consent.toLowerCase()})',
                                        onPressed: () => _resend(c),
                                      ),
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline),
                                      onPressed: () => _remove(c),
                                    ),
                                  ],
                                ),
                              );
                            },
                          ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
