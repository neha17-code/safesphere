import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../core/api_client.dart';
import '../models/contact.dart';

/// Contacts live on the server (real phone numbers + consent status).
/// A copy of the last list is kept on the phone so an emergency SMS still works offline.
class ContactService {
  final _api = ApiClient.instance;
  static const _storage = FlutterSecureStorage();
  static const _cacheKey = 'contacts_cache';

  List<Contact> _parse(List raw) =>
      raw.map((e) => Contact.fromJson(e as Map<String, dynamic>)).toList();

  Future<List<Contact>> getContacts() async {
    try {
      final raw = await _api.get('/contacts') as List;
      await _storage.write(key: _cacheKey, value: jsonEncode(raw));
      return _parse(raw);
    } on ApiException catch (e) {
      if (!e.isNetwork) rethrow;
      return cachedContacts(); // offline: use the last known list
    }
  }

  Future<List<Contact>> cachedContacts() async {
    final saved = await _storage.read(key: _cacheKey);
    if (saved == null) return [];
    return _parse(jsonDecode(saved) as List);
  }

  Future<Contact> addContact({
    required String name,
    required String phone,
    String? relationship,
    int priority = 1,
  }) async {
    final res = await _api.post('/contacts', {
      'name': name,
      'phone': phone,
      'relationship_label': relationship,
      'priority': priority,
    });
    return Contact.fromJson(res as Map<String, dynamic>);
  }

  Future<void> resend(int id) => _api.post('/contacts/$id/resend');

  /// {message, link, whatsapp_url} for sharing the invitation yourself.
  Future<Map<String, dynamic>> getInvite(int id) async =>
      (await _api.get('/contacts/$id/invite')) as Map<String, dynamic>;

  Future<void> removeContact(int id) => _api.delete('/contacts/$id');
}
