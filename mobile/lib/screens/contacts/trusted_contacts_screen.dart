import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

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
  final _email = TextEditingController();
  List<Contact> _contacts = [];
  int _priority = 1;
  bool _loading = true;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _load();
    // keeps the progress live: the dot turns green by itself when a contact accepts
    _poll = Timer.periodic(const Duration(seconds: 10), (_) => _load(quiet: true));
  }

  @override
  void dispose() {
    _poll?.cancel();
    _name.dispose();
    _phone.dispose();
    _email.dispose();
    super.dispose();
  }

  void _toast(String msg) {
    if (!mounted) return; // screen may be closed by the time a slow request fails
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _load({bool quiet = false}) async {
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
      if (!quiet) _toast(e.message);
    }
  }

  Future<void> _add() async {
    if (_name.text.trim().isEmpty || _phone.text.trim().isEmpty) {
      _toast('Enter a name and a phone number with country code, e.g. +91...');
      return;
    }
    try {
      final contact = await _service.addContact(
        name: _name.text.trim(),
        phone: _phone.text.trim(),
        email: _email.text.trim(),
        priority: _priority,
      );
      _name.clear();
      _phone.clear();
      _email.clear();
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(contact.inviteStatus == 'SENT'
            ? '${contact.name} added. Invitation sent. Waiting for them to accept.'
            : '${contact.name} added, but the invitation was NOT sent. Use WhatsApp, or add an email.'),
        duration: const Duration(seconds: 10),
        action: SnackBarAction(label: 'WHATSAPP', onPressed: () => _inviteViaWhatsApp(contact)),
      ));
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  /// Opens WhatsApp with the invitation pre-filled. Falls back to copying the text.
  Future<void> _inviteViaWhatsApp(Contact c) async {
    final Map<String, dynamic> invite;
    try {
      invite = await _service.getInvite(c.id);
    } on ApiException catch (e) {
      _toast(e.message);
      return;
    }

    var opened = false;
    try {
      opened = await launchUrl(
        Uri.parse(invite['whatsapp_url'] as String),
        mode: LaunchMode.externalApplication,
      );
    } catch (_) {
      opened = false;
    }

    if (!opened) {
      await Clipboard.setData(ClipboardData(text: invite['message'] as String));
      _toast('Could not open WhatsApp. The invitation was copied: paste it into any chat.');
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

  Future<void> _setEmail(Contact c) async {
    final controller = TextEditingController();
    final email = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        scrollable: true,
        title: Text('Email for ${c.name}'),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(hintText: 'name@example.com', border: OutlineInputBorder()),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('CANCEL')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('SAVE')),
        ],
      ),
    );
    if (email == null || email.isEmpty) return;
    try {
      await _service.setEmail(c.id, email);
      _toast('Email saved for ${c.name}.');
      await _load();
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
    // One scrollable surface: header, form and list move together, so the keyboard
    // can never cause a RenderFlex overflow (also safe with large system fonts).
    return Scaffold(
      appBar: AppBar(title: const Text('Trusted Contacts')),
      body: SafeArea(
        child: CustomScrollView(
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.all(20),
              sliver: SliverList(
                delegate: SliverChildListDelegate([
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
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                        hintText: 'Name',
                        prefixIcon: Icon(Icons.person_outline),
                        border: OutlineInputBorder()),
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
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                        hintText: 'Email for alerts (recommended)',
                        prefixIcon: Icon(Icons.mail_outline),
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
                      IconButton.filled(
                          onPressed: _add, icon: const Icon(Icons.add), tooltip: 'Add contact'),
                    ],
                  ),
                  const SizedBox(height: 16),
                ]),
              ),
            ),
            if (_loading)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_contacts.isEmpty)
              const SliverFillRemaining(
                hasScrollBody: false,
                child: Center(child: Text('No trusted contacts yet.')),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                sliver: SliverList.separated(
                  itemCount: _contacts.length,
                  separatorBuilder: (context, index) => const SizedBox(height: 10),
                  itemBuilder: (context, i) => _contactTile(_contacts[i]),
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _sentAt(Contact c) {
    final t = c.inviteSentAt;
    return t == null ? '' : ' at ${TimeOfDay.fromDateTime(t).format(context)}';
  }

  /// One plain sentence per stage: not sent -> sent -> accepted.
  String _progressText(Contact c) {
    final how = (c.inviteChannel ?? '')
        .split('+')
        .map((x) => x == 'email' ? 'emailed' : (x == 'sms' ? 'texted' : x))
        .join(' and ');
    switch (c.inviteStatus) {
      case 'ACCEPTED':
        return 'Accepted. Alerts go by ${c.email != null ? "email ${c.email}" : "SMS only (add an email)"} and phone notification if they turned it on.';
      case 'DECLINED':
        return 'Declined: they will not receive alerts.';
      case 'SENT':
        return 'Invitation $how${_sentAt(c)}. Waiting for them to accept.';
      default:
        return 'Invitation NOT sent yet. ${c.email == null ? "Add an email, or use WhatsApp." : "Tap the menu to send it."}';
    }
  }

  IconData _progressIcon(Contact c) => switch (c.inviteStatus) {
        'ACCEPTED' => Icons.check_circle,
        'DECLINED' => Icons.cancel,
        'SENT' => Icons.hourglass_top,
        _ => Icons.error_outline,
      };

  Color _progressColor(Contact c) => switch (c.inviteStatus) {
        'ACCEPTED' => Colors.green,
        'DECLINED' => Colors.red,
        'SENT' => Colors.orange,
        _ => Colors.red,
      };

  Future<void> _resend(Contact c) async {
    try {
      final r = await _service.resend(c.id);
      _toast(r.ok
          ? 'Invitation sent to ${c.name} by ${r.channelText}. Waiting for them to accept.'
          : 'Invitation NOT sent to ${c.name}: ${r.reasonText}.');
      await _load();
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Widget _contactTile(Contact c) {
    return ListTile(
      tileColor: const Color(0xFFF3F3F6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Text(c.name),
      isThreeLine: true,
      subtitle: Text('${c.phone} · ${c.priority == 1 ? "alerted first" : "escalation"}\n${_progressText(c)}'),
      leading: Icon(_progressIcon(c), color: _progressColor(c)),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!c.isConfirmed)
            IconButton(
              icon: const Icon(Icons.chat_outlined, color: Colors.green),
              tooltip: 'Send invitation on WhatsApp',
              onPressed: () => _inviteViaWhatsApp(c),
            ),
          PopupMenuButton<String>(
            onSelected: (v) {
              switch (v) {
                case 'resend':
                  _resend(c);
                  break;
                case 'email':
                  _setEmail(c);
                  break;
                case 'delete':
                  _remove(c);
                  break;
              }
            },
            itemBuilder: (_) => [
              if (!c.isConfirmed) const PopupMenuItem(value: 'resend', child: Text('Send invitation again')),
              PopupMenuItem(value: 'email', child: Text(c.email == null ? 'Add email' : 'Change email')),
              const PopupMenuItem(value: 'delete', child: Text('Remove contact')),
            ],
          ),
        ],
      ),
    );
  }
}
