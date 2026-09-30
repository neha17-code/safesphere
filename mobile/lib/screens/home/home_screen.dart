import 'package:flutter/material.dart';

import '../../models/journey.dart';
import '../../services/journey_service.dart';
import '../contacts/trusted_contacts_screen.dart';
import '../emergency/emergency_screen.dart';
import '../journey/active_journey_screen.dart';
import '../journey/journey_setup_screen.dart';
import '../settings/settings_screen.dart';
import '../unsafe/feel_unsafe_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Journey? _active;
  bool _autoResumed = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh(autoResume: true));
  }

  Future<void> _refresh({bool autoResume = false}) async {
    try {
      final journey = await JourneyService().getActive();
      if (!mounted) return;
      setState(() => _active = journey);
      if (autoResume && journey != null && !_autoResumed) {
        _autoResumed = true;
        _openActive(journey);
      }
    } catch (_) {
      // offline: home still works, the banner just won't show
    }
  }

  Future<void> _go(Widget screen) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => screen));
    _refresh(); // journey may have started/ended while we were away
  }

  void _openActive(Journey j) => Navigator.push(
        context,
        MaterialPageRoute(
          settings: const RouteSettings(name: '/active-journey'),
          builder: (_) => ActiveJourneyScreen(journey: j),
        ),
      ).then((_) => _refresh());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8F8FA),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 30),
              const Text('SafeSphere', style: TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
              const SizedBox(height: 6),
              const Text("You're in control.", style: TextStyle(fontSize: 17, color: Colors.black54)),
              const SizedBox(height: 30),
              if (_active != null) ...[
                _SafetyOption(
                  icon: Icons.route_outlined,
                  title: 'Journey in progress',
                  subtitle: 'Tap to return to your journey',
                  backgroundColor: const Color(0xFFE3F2FD),
                  iconColor: Colors.blue,
                  onTap: () => _openActive(_active!),
                ),
                const SizedBox(height: 16),
              ],
              const Text('How are you feeling right now?',
                  style: TextStyle(fontSize: 21, fontWeight: FontWeight.w600)),
              const SizedBox(height: 20),
              _SafetyOption(
                icon: Icons.check_circle_outline,
                title: "I'm Safe",
                subtitle: 'Plan a journey and stay connected',
                backgroundColor: const Color(0xFFE8F5E9),
                iconColor: Colors.green,
                onTap: () => _go(const JourneySetupScreen()),
              ),
              const SizedBox(height: 16),
              _SafetyOption(
                icon: Icons.warning_amber_rounded,
                title: 'I Feel Unsafe',
                subtitle: 'Quietly let your contacts know',
                backgroundColor: const Color(0xFFFFF4D6),
                iconColor: Colors.orange,
                onTap: () => _go(const FeelUnsafeScreen()),
              ),
              const SizedBox(height: 16),
              _SafetyOption(
                icon: Icons.emergency_outlined,
                title: 'Emergency',
                subtitle: 'I need help right now',
                backgroundColor: const Color(0xFFFFE8E8),
                iconColor: Colors.red,
                onTap: () => _go(const EmergencyScreen()),
              ),
              const SizedBox(height: 25),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _go(const TrustedContactsScreen()),
                      icon: const Icon(Icons.people_outline),
                      label: const Text('Trusted Contacts'),
                      style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 15)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  IconButton(
                    onPressed: () => _go(const SettingsScreen()),
                    icon: const Icon(Icons.settings_outlined),
                    tooltip: 'Settings',
                  ),
                ],
              ),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }
}

class _SafetyOption extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color backgroundColor;
  final Color iconColor;
  final VoidCallback onTap;

  const _SafetyOption({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.backgroundColor,
    required this.iconColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: backgroundColor,
      borderRadius: BorderRadius.circular(20),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icon, size: 34, color: iconColor),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 5),
                    Text(subtitle, style: const TextStyle(fontSize: 14, color: Colors.black54)),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_ios, size: 16, color: Colors.black45),
            ],
          ),
        ),
      ),
    );
  }
}
