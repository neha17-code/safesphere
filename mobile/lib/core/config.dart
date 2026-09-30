/// Build with:  flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
/// 10.0.2.2 is the Android emulator's alias for your computer's localhost.
const String apiBaseUrl =
    String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
