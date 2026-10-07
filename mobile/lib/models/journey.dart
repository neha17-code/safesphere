import 'contact.dart';
import 'delivery.dart';

class Journey {
  final int id;
  final String destination;
  final DateTime expectedArrival; // local time
  final String status;
  final int escalationStage;
  final bool shareLocation;
  final List<Contact> contacts;
  final List<DeliveryResult> notified; // who was told the journey started (only set when it starts)

  Journey({
    required this.id,
    required this.destination,
    required this.expectedArrival,
    required this.status,
    required this.escalationStage,
    required this.shareLocation,
    required this.contacts,
    this.notified = const [],
  });

  factory Journey.fromJson(Map<String, dynamic> j) => Journey(
        id: j['id'] as int,
        destination: j['destination'] as String,
        expectedArrival: DateTime.parse(j['expected_arrival_at'] as String).toLocal(),
        status: j['status'] as String,
        escalationStage: j['escalation_stage'] as int,
        shareLocation: j['share_location'] as bool,
        contacts: (j['contacts'] as List)
            .map((c) => Contact.fromJson(c as Map<String, dynamic>))
            .toList(),
        notified: DeliveryResult.listFrom(j['notified']),
      );
}
