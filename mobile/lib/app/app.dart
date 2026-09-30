import 'package:flutter/material.dart';

import '../screens/auth/login_screen.dart';
import '../screens/home/home_screen.dart';
import '../screens/journey/active_journey_screen.dart';
import '../services/auth_service.dart';
import '../services/journey_service.dart';

final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();

class SafeSphereApp extends StatelessWidget {
  const SafeSphereApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: appNavigatorKey,
      debugShowCheckedModeBanner: false,
      title: 'SafeSphere',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
      home: const _AuthGate(),
    );
  }
}

/// Decides between login and home based on a stored, server-verified session.
class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: AuthService().isLoggedIn(),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return snap.data == true ? const HomeScreen() : const LoginScreen();
      },
    );
  }
}

/// Opened from a notification tap: fetch the journey from the server (source of truth).
Future<void> openActiveJourney() async {
  final navigator = appNavigatorKey.currentState;
  final context = appNavigatorKey.currentContext;
  if (navigator == null || context == null) return;

  try {
    final journey = await JourneyService().getActive();
    if (journey == null) return;
    navigator.push(MaterialPageRoute(
      settings: const RouteSettings(name: '/active-journey'),
      builder: (_) => ActiveJourneyScreen(journey: journey),
    ));
  } catch (_) {
    // Not logged in / offline: the user can still resume from the home screen.
  }
}
