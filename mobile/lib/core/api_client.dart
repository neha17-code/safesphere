import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'config.dart';

class ApiException implements Exception {
  final int status;
  final String message;
  ApiException(this.status, this.message);

  bool get isNetwork => status == 0;
  @override
  String toString() => message;
}

/// Single place that talks HTTP: adds the JWT, parses errors, applies timeouts.
class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  static const _storage = FlutterSecureStorage();
  static const _tokenKey = 'auth_token';
  static const _timeout = Duration(seconds: 30); // tolerates a cold-starting free server

  String? _token;

  Future<String?> loadToken() async => _token ??= await _storage.read(key: _tokenKey);

  Future<void> saveToken(String token) async {
    _token = token;
    await _storage.write(key: _tokenKey, value: token);
  }

  Future<void> clearToken() async {
    _token = null;
    await _storage.delete(key: _tokenKey);
  }

  Future<dynamic> get(String path) => _send('GET', path);
  Future<dynamic> post(String path, [Object? body]) => _send('POST', path, body);
  Future<dynamic> put(String path, [Object? body]) => _send('PUT', path, body);
  Future<dynamic> delete(String path) => _send('DELETE', path);

  Future<dynamic> _send(String method, String path, [Object? body]) async {
    final token = await loadToken();
    final request = http.Request(method, Uri.parse('$apiBaseUrl$path'));
    request.headers['Content-Type'] = 'application/json';
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) request.body = jsonEncode(body);

    try {
      final streamed = await request.send().timeout(_timeout);
      final response = await http.Response.fromStream(streamed);

      if (response.statusCode == 401 && token != null) {
        await clearToken(); // expired token -> force re-login
      }
      if (response.statusCode >= 400) {
        throw ApiException(response.statusCode, _errorText(response));
      }
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    } on TimeoutException {
      throw ApiException(0, 'Server did not respond. Check your connection.');
    } on http.ClientException {
      throw ApiException(0, 'Cannot reach the server. Check your connection.');
    }
  }

  String _errorText(http.Response r) {
    try {
      final detail = jsonDecode(r.body)['detail'];
      if (detail is String) return detail;
      if (detail is List && detail.isNotEmpty) return detail.first['msg'].toString();
    } catch (_) {}
    return 'Something went wrong (${r.statusCode}).';
  }
}
