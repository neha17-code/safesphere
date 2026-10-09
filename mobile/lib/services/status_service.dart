import '../core/api_client.dart';

class StatusService {
  final _api = ApiClient.instance;

  /// Which alert channels the server really has set up: {email, sms, push}.
  Future<Map<String, dynamic>> channels() async => (await _api.get('/status/channels')) as Map<String, dynamic>;

  /// Sends a test email to the logged-in user and returns {ok, to, detail, hint}.
  Future<Map<String, dynamic>> testEmail() async =>
      (await _api.post('/status/test-email')) as Map<String, dynamic>;

  /// The owner's audit trail: what was sent, to whom, and whether it worked.
  Future<List<Map<String, dynamic>>> events() async =>
      ((await _api.get('/alerts/events')) as List).cast<Map<String, dynamic>>();
}
