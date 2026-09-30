import 'package:flutter/material.dart';

import 'app/app.dart';
import 'services/notification_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await NotificationService.initialize(
    onNotificationTap: (payload) {
      if (payload == 'active_journey' || payload == 'arrival_reminder') {
        openActiveJourney();
      }
    },
  );

  runApp(const SafeSphereApp());
}
