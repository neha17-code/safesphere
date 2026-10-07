class Contact {
  final int id;
  final String name;
  final String phone;
  final String? relationship;
  final int priority;
  final String consent; // PENDING | CONFIRMED | DECLINED
  final String? email;
  final String inviteStatus; // NOT_SENT | SENT | ACCEPTED | DECLINED
  final String? inviteChannel; // email | sms | sms+email | none
  final DateTime? inviteSentAt;

  Contact({
    required this.id,
    required this.name,
    required this.phone,
    required this.priority,
    required this.consent,
    this.email,
    this.inviteStatus = 'NOT_SENT',
    this.inviteChannel,
    this.inviteSentAt,
    this.relationship,
  });

  bool get isConfirmed => consent == 'CONFIRMED';

  factory Contact.fromJson(Map<String, dynamic> j) => Contact(
        id: j['id'] as int,
        name: j['name'] as String,
        phone: j['phone'] as String,
        relationship: j['relationship_label'] as String?,
        priority: j['priority'] as int,
        consent: j['consent'] as String,
        email: j['email'] as String?,
        inviteStatus: (j['invite_status'] as String?) ?? 'NOT_SENT',
        inviteChannel: j['invite_channel'] as String?,
        inviteSentAt: j['invite_sent_at'] == null ? null : DateTime.parse(j['invite_sent_at'] as String).toLocal(),
      );
}
