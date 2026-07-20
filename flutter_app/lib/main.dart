import 'dart:io';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'theme/suoke_theme.dart';
import 'services/api.dart';
import 'services/feature_flags_service.dart';
import 'services/notification_service.dart';
import 'services/project_context.dart';
import 'pages/home_page.dart';
import 'pages/login_page.dart';

/// 仅用于本地开发：跳过 TLS 证书校验，便于对接使用自签名证书的后端。
/// 生产环境必须启用完整 SSL 校验。
class _DevelopmentHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    return super.createHttpClient(context)
      ..badCertificateCallback = (X509Certificate cert, String host, int port) => true;
  }
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  if (AppConfig.debugMode) {
    HttpOverrides.global = _DevelopmentHttpOverrides();
  }
  // 初始化通知服务（失败不影响应用启动）
  // HarmonyOS 等不支持的平台会自动跳过原生初始化
  NotificationService().initialize().catchError((e) {
    debugPrint('NotificationService 初始化失败（不影响应用启动）: $e');
  });
  // 预加载功能开关（异步，失败不影响应用启动）
  FeatureFlagsService().initialize().catchError((e) {
    debugPrint('FeatureFlagsService 初始化失败（不影响应用启动）: $e');
  });
  runApp(const IHomeApp());
}

/// 主题状态管理
class ThemeState extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.dark;

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  ThemeState() {
    _loadPref();
  }

  Future<void> _loadPref() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString('theme_mode');
    if (stored == 'light') {
      _mode = ThemeMode.light;
    }
    notifyListeners();
  }

  Future<void> toggle() async {
    _mode = _mode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('theme_mode', _mode == ThemeMode.dark ? 'dark' : 'light');
  }
}

class IHomeApp extends StatelessWidget {
  const IHomeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => ThemeState(),
      child: Consumer<ThemeState>(
        builder: (context, themeState, _) {
          return ChangeNotifierProvider(
            create: (_) => ProjectContext(),
            child: MaterialApp(
              title: '索克家居',
              debugShowCheckedModeBanner: false,
              theme: SuokeTheme.light(),
              darkTheme: SuokeTheme.dark(),
              themeMode: themeState.isDark ? ThemeMode.dark : ThemeMode.light,
              home: const AuthGate(),
            ),
          );
        },
      ),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  bool _loading = true;
  bool _loggedIn = false;

  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final api = ApiClient();
    await api.loadToken();
    if (mounted) {
      setState(() {
        _loggedIn = api.isLoggedIn;
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    return _loggedIn ? const HomePage() : const LoginPage();
  }
}
