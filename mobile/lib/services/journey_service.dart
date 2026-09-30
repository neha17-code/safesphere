import '../core/api_client.dart';
import '../models/journey.dart';
import 'location_service.dart';

/// The server is the source of truth. Nothing about a journey is kept only on the phone.
class JourneyService {
  final _api = ApiClient.instance;

  Future<Journey> start({
    required String destination,
    required DateTime expectedArrival,
    required List<int> contactIds,
    required bool shareLocation,
  }) async {
    final res = await _api.post('/journeys', {
      'destination': destination,
      'expected_arrival_at': expectedArrival.toUtc().toIso8601String(),
      'contact_ids': contactIds,
      'share_location': shareLocation,
    });
    return Journey.fromJson(res as Map<String, dynamic>);
  }

  Future<Journey?> getActive() async {
    final res = await _api.get('/journeys/active');
    return res == null ? null : Journey.fromJson(res as Map<String, dynamic>);
  }

  /// Returns normally for BOTH a safe and a duress PIN (by design).
  Future<void> arrive(int id, {String? pin}) =>
      _api.post('/journeys/$id/arrive', {'pin': pin});

  Future<Journey> extend(int id, int minutes) async {
    final res = await _api.post('/journeys/$id/extend', {'minutes': minutes});
    return Journey.fromJson(res as Map<String, dynamic>);
  }

  Future<void> pushLocation(int id) async {
    final pos = await LocationService.current();
    if (pos == null) return;
    await _api.post('/journeys/$id/location', {
      'lat': pos.latitude,
      'lng': pos.longitude,
      'accuracy': pos.accuracy,
    });
  }

  /// Returns how many contacts were actually reached.
  Future<int> emergency({int? journeyId}) async {
    final pos = await LocationService.current();
    final body = {'lat': pos?.latitude, 'lng': pos?.longitude};
    final path = journeyId == null ? '/alerts/emergency' : '/journeys/$journeyId/emergency';
    final res = await _api.post(path, body);
    return res['delivered_to'] as int;
  }

  Future<int> feelUnsafe(List<int> contactIds) async {
    final pos = await LocationService.current();
    final res = await _api.post('/alerts/unsafe', {
      'contact_ids': contactIds,
      'lat': pos?.latitude,
      'lng': pos?.longitude,
    });
    return res['delivered_to'] as int;
  }
}
