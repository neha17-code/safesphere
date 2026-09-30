import 'package:flutter_test/flutter_test.dart';
import 'package:safety_app/models/journey.dart';

void main() {
  test('Journey parses server JSON and converts the UTC time to local', () {
    final j = Journey.fromJson({
      'id': 7,
      'destination': 'Airport',
      'expected_arrival_at': '2026-09-30T14:30:00Z',
      'status': 'ACTIVE',
      'escalation_stage': 0,
      'share_location': true,
      'contacts': [
        {'id': 1, 'name': 'Mom', 'phone': '+919000000001', 'relationship_label': null, 'priority': 1, 'consent': 'CONFIRMED'}
      ],
    });
    expect(j.id, 7);
    expect(j.expectedArrival.isUtc, false);
    expect(j.expectedArrival.toUtc().hour, 14);
    expect(j.contacts.single.isConfirmed, true);
  });
}
