import '../core/api_client.dart';
import '../models/contact.dart';

/// Contacts now live on the server (real phone numbers + consent status).
class ContactService {
  final _api = ApiClient.instance;

  Future<List<Contact>> getContacts() async {
    final list = await _api.get('/contacts') as List;
    return list.map((e) => Contact.fromJson(e as Map<String, dynamic>)).toList();
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
  Future<void> removeContact(int id) => _api.delete('/contacts/$id');
}
