import '../core/api_client.dart';

class AuthService {
  final _api = ApiClient.instance;

  Future<bool> isLoggedIn() async {
    if (await _api.loadToken() == null) return false;
    try {
      await _api.get('/auth/me');
      return true;
    } on ApiException catch (e) {
      return e.isNetwork; // offline: keep the session, retry later
    }
  }

  Future<void> register(String name, String email, String password, String? phone) async {
    final res = await _api.post('/auth/register', {
      'name': name,
      'email': email,
      'password': password,
      if (phone != null && phone.isNotEmpty) 'phone': phone,
    });
    await _api.saveToken(res['access_token'] as String);
  }

  Future<void> login(String email, String password) async {
    final res = await _api.post('/auth/login', {'email': email, 'password': password});
    await _api.saveToken(res['access_token'] as String);
  }

  Future<Map<String, dynamic>> me() async =>
      (await _api.get('/auth/me')) as Map<String, dynamic>;

  Future<void> setPins(String safePin, String duressPin) =>
      _api.put('/auth/pins', {'safe_pin': safePin, 'duress_pin': duressPin});

  Future<void> logout() => _api.clearToken();
}
