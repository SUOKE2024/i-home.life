import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'config.dart';
import 'http_overrides_stub.dart'
    if (dart.library.io) 'http_overrides_native.dart';
import 'theme/suoke_theme.dart';
import 'services/api.dart';
import 'services/feature_flags_service.dart';
import 'services/notification_service.dart';
import 'services/performance_service.dart';
import 'services/project_context.dart';
import 'pages/home_page.dart';
import 'pages/login_page.dart';
import 'widgets/voice_overlay.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // v1.1.26: 初始化性能监控
  PerformanceService.instance.initialize();
  setupHttpOverrides(AppConfig.debugMode);
  // 初始化通知服务（失败不影响应用启动）
  // HarmonyOS 等不支持的平台会自动跳过原生初始化
  NotificationService().initialize().catchError((e) {
    debugPrint('NotificationService 初始化失败（不影响应用启动）: $e');
  });
  // 预加载功能开关（异步，失败不影响应用启动）
  FeatureFlagsService().initialize().then((_) {
    PerformanceService.instance.startupMark('feature_flags_loaded');
  }).catchError((e) {
    debugPrint('FeatureFlagsService 初始化失败（不影响应用启动）: $e');
  });
  runApp(const IHomeApp());
}

/// 主题状态管理 — 支持手动切换暗/亮/自动主题
class ThemeState extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.system;
  static const _themeKey = 'settings_theme_mode';

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  ThemeState() {
    _load();
  }

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getString(_themeKey) ?? 'system';
      _mode = v == 'light'
          ? ThemeMode.light
          : v == 'dark'
              ? ThemeMode.dark
              : ThemeMode.system;
      notifyListeners();
    } catch (_) {}
  }

  Future<void> setMode(ThemeMode mode) async {
    _mode = mode;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _themeKey,
        mode == ThemeMode.light
            ? 'light'
            : mode == ThemeMode.dark
                ? 'dark'
                : 'system',
      );
    } catch (_) {}
  }
}

/// 全局 Navigator Key，用于未登录时的导航跳转
final GlobalKey<NavigatorState> globalNavigatorKey = GlobalKey<NavigatorState>();

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
              navigatorKey: globalNavigatorKey,
              theme: SuokeTheme.light(),
              darkTheme: SuokeTheme.dark(),
              themeMode: themeState.mode,
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
    _setupGlobalAuthGuard();
    _checkAuth();
  }

  /// 设置全局 401 回调：任何地方收到 401 自动跳转登录页
  void _setupGlobalAuthGuard() {
    ApiClient().onUnauthorized = () {
      debugPrint('AuthGate: 全局 401 回调触发，跳转登录页');
      globalNavigatorKey.currentState?.pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const LoginPage()),
        (route) => false,
      );
    };
  }

  Future<void> _checkAuth() async {
    final api = ApiClient();
    await api.loadToken();
    if (!api.isLoggedIn) {
      if (mounted) setState(() => _loading = false);
      return;
    }

    // 验证 token 有效性，避免残留过期 token 导致 HomePage 显示 "Not authenticated"
    // 注意：暂存 onUnauthorized 回调，避免 AuthGate 初始化时双重导航
    final savedUnauthorized = api.onUnauthorized;
    api.onUnauthorized = null;
    try {
      final result = await api.get('/auth/me');
      _loggedIn = result.isSuccess;
      if (!result.isSuccess) {
        debugPrint('AuthGate: token 验证失败，token 已清除');
        // _handleResponse 的 401 处理已调用 _onUnauthorized() → clearToken()
      }
    } catch (_) {
      debugPrint('AuthGate: /auth/me 请求异常，清除 token');
      await api.clearToken();
    } finally {
      api.onUnauthorized = savedUnauthorized;
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (!_loggedIn) return const LoginPage();

    // v1.2.8 登录成功：注入悬浮窗常驻语音交互
    // 受 voice_floating_widget_enabled feature flag 控制（后端 /config/feature-flags）
    // flag 关闭时不注入，保持原有体验
    return Builder(
      builder: (context) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          final enabled = FeatureFlagsService()
              .isEnabled('voice_floating_widget_enabled');
          if (!enabled || VoiceOverlayController().isShown) return;
          VoiceOverlayController().show(context);
        });
        return const HomePage();
      },
    );
  }
}
