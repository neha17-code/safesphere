import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

/// LOCAL reminders only. Anything that must reach another person goes through the server.
///
/// Fixes vs. the prototype:
///  * every notification has its own ID (unsafe-alert no longer collides with check-in)
///  * lock-screen text is private (no destination shown to onlookers)
///  * scheduled in UTC instants, so it works in any time zone (was hard-coded Asia/Kolkata)
///  * the misleading "alert is ready for X" notifications were removed
class NotificationService {
  static final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();

  static const AndroidNotificationChannel _channel = AndroidNotificationChannel(
    'safesphere_journey',
    'SafeSphere Journey',
    description: 'Journey reminders and check-ins.',
    importance: Importance.high,
  );

  static const int activeJourneyId = 101;
  static const int arrivalReminderId = 102;
  static const int checkInId = 103;

  static const _details = NotificationDetails(
    android: AndroidNotificationDetails(
      'safesphere_journey',
      'SafeSphere Journey',
      channelDescription: 'Journey reminders and check-ins.',
      importance: Importance.high,
      priority: Priority.high,
      visibility: NotificationVisibility.private, // hide content on lock screen
    ),
  );

  static AndroidFlutterLocalNotificationsPlugin? get _android =>
      _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();

  static Future<void> initialize({void Function(String? payload)? onNotificationTap}) async {
    tz.initializeTimeZones();
    await _plugin.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
      ),
      onDidReceiveNotificationResponse: (r) => onNotificationTap?.call(r.payload),
    );
    await _android?.createNotificationChannel(_channel);
    await requestPermissions();
  }

  static Future<void> requestPermissions() async {
    await _android?.requestNotificationsPermission();
    await _android?.requestExactAlarmsPermission();
  }

  static Future<void> showJourneyActive() => _plugin.show(
        id: activeJourneyId,
        title: 'SafeSphere journey active',
        body: 'Tap to open. Confirm when you arrive.',
        notificationDetails: const NotificationDetails(
          android: AndroidNotificationDetails(
            'safesphere_journey',
            'SafeSphere Journey',
            importance: Importance.low,
            priority: Priority.low,
            ongoing: true,
            autoCancel: false,
            visibility: NotificationVisibility.private,
          ),
        ),
        payload: 'active_journey',
      );

  static Future<AndroidScheduleMode> _mode() async {
    final exact = await _android?.canScheduleExactNotifications() ?? false;
    return exact ? AndroidScheduleMode.exactAllowWhileIdle : AndroidScheduleMode.inexactAllowWhileIdle;
  }

  /// Local "are you safe?" nudge at the expected arrival time. The server independently
  /// escalates to contacts if the user never answers (this phone may be dead or offline).
  static Future<void> scheduleArrivalReminder(DateTime arrival) async {
    await _plugin.cancel(id: arrivalReminderId);
    final when = tz.TZDateTime.from(arrival, tz.UTC);
    if (!when.isAfter(tz.TZDateTime.now(tz.UTC))) return;
    await _plugin.zonedSchedule(
      id: arrivalReminderId,
      title: 'SafeSphere: are you safe?',
      body: 'Your expected arrival time has passed. Please confirm.',
      scheduledDate: when,
      notificationDetails: _details,
      androidScheduleMode: await _mode(),
      payload: 'arrival_reminder',
    );
  }

  static Future<void> cancelJourneyNotifications() async {
    await _plugin.cancel(id: activeJourneyId);
    await _plugin.cancel(id: arrivalReminderId);
  }

  static Future<void> scheduleCheckInReminder() async {
    await _plugin.cancel(id: checkInId);
    await _plugin.zonedSchedule(
      id: checkInId,
      title: 'SafeSphere check-in',
      body: 'It has been 15 minutes. Are you still safe?',
      scheduledDate: tz.TZDateTime.now(tz.UTC).add(const Duration(minutes: 15)),
      notificationDetails: _details,
      androidScheduleMode: await _mode(),
      payload: 'check_in',
    );
  }

  static Future<void> cancelCheckInReminder() => _plugin.cancel(id: checkInId);

  /// Survives leaving the screen (the prototype forgot this state).
  static Future<bool> isCheckInPending() async =>
      (await _plugin.pendingNotificationRequests()).any((n) => n.id == checkInId);
}
