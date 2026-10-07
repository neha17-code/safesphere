/// What happened for ONE contact when SafeSphere tried to reach them. Shown to the user so progress is never a guess.
class DeliveryResult {
  final String name;
  final bool ok;
  final String channel; // push | sms | email | combinations like "push+email" | none | skipped
  final String reason; // "" | NOT_ACCEPTED | NO_CONTACT_EMAIL | EMAIL_NOT_CONFIGURED | PROVIDER_REJECTED

  DeliveryResult({required this.name, required this.ok, required this.channel, required this.reason});

  factory DeliveryResult.fromJson(Map<String, dynamic> j) => DeliveryResult(
        name: j['name'] as String,
        ok: j['ok'] as bool,
        channel: j['channel'] as String,
        reason: (j['reason'] as String?) ?? '',
      );

  static List<DeliveryResult> listFrom(dynamic raw) =>
      ((raw as List?) ?? []).map((e) => DeliveryResult.fromJson(e as Map<String, dynamic>)).toList();

  String get channelText => channel
      .split('+')
      .map((c) => switch (c) {
            'push' => 'phone notification',
            'sms' => 'SMS',
            'email' => 'email',
            _ => c,
          })
      .join(' + ');

  String get reasonText => switch (reason) {
        'NOT_ACCEPTED' => "they haven't accepted the invitation yet",
        'NO_CONTACT_EMAIL' => 'no email saved for them and no SMS service is set up',
        'EMAIL_NOT_CONFIGURED' => 'the server has no email or SMS service set up',
        'PROVIDER_REJECTED' => 'the email service refused it (see the server log)',
        _ => 'they could not be reached',
      };

  String describe() => ok ? '$name: reached by $channelText' : '$name: not reached, $reasonText';
}
