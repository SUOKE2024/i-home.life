import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'config.dart';
import 'http_overrides_stub.dart'
    if (dart.library.io) 'http_overrides_native.dart';
import 'theme/suoke_theme.dart';
import 'services/api.dart';
import 'services/avatar_controller.dart';
import 'services/feature_flags_service.dart';
import 'services/notification_service.dart';
import 'services/performance_service.dart';
import 'services/project_context.dart';
import 'pages/home_page.dart';
import 'pages/login_page.dart';
import 'pages/ai_chat_page.dart';
import 'pages/ai_image_page.dart';
import 'pages/ai_qa_page.dart';
import 'pages/appliance_page.dart';
import 'pages/ar_scan_page.dart';
import 'pages/b2b_delivery_page.dart';
import 'pages/bathroom_page.dart';
import 'pages/budget_page.dart';
import 'pages/cad_page.dart';
import 'pages/camera_scan_page.dart';
import 'pages/change_orders_page.dart';
import 'pages/chat_page.dart';
import 'pages/construction_page.dart';
import 'pages/crew_page.dart';
import 'pages/custom_furniture_page.dart';
import 'pages/dashboard_page.dart';
import 'pages/design_deepening_page.dart';
import 'pages/design_proposal_page.dart';
import 'pages/door_window_waterproof_page.dart';
import 'pages/eco_materials_page.dart';
import 'pages/ecosystem_page.dart';
import 'pages/elderly_adaptation_page.dart';
import 'pages/escrow_trustee_page.dart';
import 'pages/furniture_catalog_page.dart';
import 'pages/hard_decoration_page.dart';
import 'pages/identity_page.dart';
import 'pages/ifc_export_page.dart';
import 'pages/kitchen_bath_mep_page.dart';
import 'pages/kitchen_page.dart';
import 'pages/lighting_page.dart';
import 'pages/location_page.dart';
import 'pages/materials_page.dart';
import 'pages/mep_page.dart';
import 'pages/partial_renovation_page.dart';
import 'pages/points_page.dart';
import 'pages/procurement_enhanced_page.dart';
import 'pages/product_batch_page.dart';
import 'pages/products_page.dart';
import 'pages/project_detail_page.dart';
import 'pages/projects_page.dart';
import 'pages/quality_report_page.dart';
import 'pages/scene_automation_page.dart';
import 'pages/settings_page.dart';
import 'pages/settlement_page.dart';
import 'pages/sketch_to_3d_page.dart';
import 'pages/smart_home_page.dart';
import 'pages/soft_furnishing_page.dart';
import 'pages/solution_first_page.dart';
import 'pages/structural_page.dart';
import 'pages/stylus_adapter.dart';
import 'pages/takeoff_page.dart';
import 'pages/tasks_page.dart';
import 'pages/timeline_page.dart';
import 'pages/voice_realtime_page.dart';
import 'pages/vr_panorama_page.dart';
import 'pages/worker_page.dart';
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
/// C 端默认浅色暖底（DESIGN.md「C 端浅色暖底」：业主端默认浅色；用户可切回深色/跟随系统）
class ThemeState extends ChangeNotifier {
  ThemeMode _mode = ThemeMode.light;
  static const _themeKey = 'settings_theme_mode';

  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  ThemeState() {
    _load();
  }

  Future<void> _load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final v = prefs.getString(_themeKey) ?? 'light';
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

/// 具名路由生成器：把 lib/pages/ 下全部页面注册为 Navigator.pushNamed 可达（含此前孤儿页）。
///
/// - 无参页面直接 const 构造；
/// - 需要 projectId 的页面经 `settings.arguments`（String）传入；
/// - 可选 projectId 页面（AIChatPage / TimelinePage 等）传 null 也安全。
Route<dynamic>? onGenerateAppRoute(RouteSettings settings) {
  final name = settings.name;
  final args = settings.arguments;
  final pid = args is String ? args : '';
  final pidOpt = args is String ? args : null;

  switch (name) {
    // ── 无参页面 ──
    case '/home':
      return MaterialPageRoute(builder: (_) => const HomePage(), settings: settings);
    case '/login':
      return MaterialPageRoute(builder: (_) => const LoginPage(), settings: settings);
    case '/dashboard':
      return MaterialPageRoute(builder: (_) => const DashboardPage(), settings: settings);
    case '/projects':
      return MaterialPageRoute(builder: (_) => const ProjectsPage(), settings: settings);
    case '/settings':
      return MaterialPageRoute(builder: (_) => const SettingsPage(), settings: settings);
    case '/materials':
      return MaterialPageRoute(builder: (_) => const MaterialsPage(), settings: settings);
    case '/cad':
      return MaterialPageRoute(builder: (_) => const CADPage(), settings: settings);
    case '/products':
      return MaterialPageRoute(builder: (_) => const ProductsPage(), settings: settings);
    case '/product-batch':
      return MaterialPageRoute(builder: (_) => const ProductBatchPage(), settings: settings);
    case '/points':
      return MaterialPageRoute(builder: (_) => const PointsPage(), settings: settings);
    case '/location':
      return MaterialPageRoute(builder: (_) => const LocationPage(), settings: settings);
    case '/identity':
      return MaterialPageRoute(builder: (_) => const IdentityPage(), settings: settings);
    case '/furniture-catalog':
      return MaterialPageRoute(builder: (_) => const FurnitureCatalogPage(), settings: settings);
    case '/camera-scan':
      return MaterialPageRoute(builder: (_) => const CameraScanPage(), settings: settings);
    case '/voice-realtime':
      return MaterialPageRoute(builder: (_) => const VoiceRealtimePage(), settings: settings);
    case '/sketch-to-3d':
      return MaterialPageRoute(builder: (_) => const SketchTo3DPage(), settings: settings);
    case '/stylus-adapter':
      return MaterialPageRoute(builder: (_) => const StylusAdapterPage(), settings: settings);

    // ── 需要 projectId 的页面（arguments: String projectId） ──
    case '/project-detail':
      return MaterialPageRoute(builder: (_) => ProjectDetailPage(projectId: pid), settings: settings);
    case '/budget':
      return MaterialPageRoute(builder: (_) => BudgetPage(projectId: pid), settings: settings);
    case '/construction':
      return MaterialPageRoute(builder: (_) => ConstructionPage(projectId: pid), settings: settings);
    case '/settlement':
      return MaterialPageRoute(builder: (_) => SettlementPage(projectId: pid), settings: settings);
    case '/design-deepening':
      return MaterialPageRoute(builder: (_) => DesignDeepeningPage(projectId: pid), settings: settings);
    case '/tasks':
      return MaterialPageRoute(builder: (_) => TasksPage(projectId: pid), settings: settings);
    case '/worker':
      return MaterialPageRoute(builder: (_) => WorkerPage(projectId: pid), settings: settings);
    case '/mep':
      return MaterialPageRoute(builder: (_) => MepPage(projectId: pid), settings: settings);
    case '/smart-home':
      return MaterialPageRoute(builder: (_) => SmartHomePage(projectId: pid), settings: settings);
    case '/ai-image':
      return MaterialPageRoute(builder: (_) => AIImagePage(projectId: pid), settings: settings);
    case '/ai-qa':
      return MaterialPageRoute(builder: (_) => AIQAPage(projectId: pid), settings: settings);
    case '/appliance':
      return MaterialPageRoute(builder: (_) => AppliancePage(projectId: pid), settings: settings);
    case '/ar-scan':
      return MaterialPageRoute(builder: (_) => ARScanPage(projectId: pid), settings: settings);
    case '/bathroom':
      return MaterialPageRoute(builder: (_) => BathroomPage(projectId: pid), settings: settings);
    case '/change-orders':
      return MaterialPageRoute(builder: (_) => ChangeOrdersPage(projectId: pid), settings: settings);
    case '/chat':
      return MaterialPageRoute(builder: (_) => ChatPage(projectId: pid), settings: settings);
    case '/crew':
      return MaterialPageRoute(builder: (_) => CrewPage(projectId: pid), settings: settings);
    case '/custom-furniture':
      return MaterialPageRoute(builder: (_) => CustomFurniturePage(projectId: pid), settings: settings);
    case '/door-window-waterproof':
      return MaterialPageRoute(builder: (_) => DoorWindowWaterproofPage(projectId: pid), settings: settings);
    case '/eco-materials':
      return MaterialPageRoute(builder: (_) => EcoMaterialsPage(projectId: pid), settings: settings);
    case '/ecosystem':
      return MaterialPageRoute(builder: (_) => EcosystemPage(projectId: pid), settings: settings);
    case '/elderly-adaptation':
      return MaterialPageRoute(builder: (_) => ElderlyAdaptationPage(projectId: pid), settings: settings);
    case '/escrow-trustee':
      return MaterialPageRoute(builder: (_) => EscrowTrusteePage(projectId: pid), settings: settings);
    case '/hard-decoration':
      return MaterialPageRoute(builder: (_) => HardDecorationPage(projectId: pid), settings: settings);
    case '/kitchen-bath-mep':
      return MaterialPageRoute(builder: (_) => KitchenBathMepPage(projectId: pid), settings: settings);
    case '/kitchen':
      return MaterialPageRoute(builder: (_) => KitchenPage(projectId: pid), settings: settings);
    case '/lighting':
      return MaterialPageRoute(builder: (_) => LightingPage(projectId: pid), settings: settings);
    case '/partial-renovation':
      return MaterialPageRoute(builder: (_) => PartialRenovationPage(projectId: pid), settings: settings);
    case '/procurement-enhanced':
      return MaterialPageRoute(builder: (_) => ProcurementEnhancedPage(projectId: pid), settings: settings);
    case '/scene-automation':
      return MaterialPageRoute(builder: (_) => SceneAutomationPage(projectId: pid), settings: settings);
    case '/soft-furnishing':
      return MaterialPageRoute(builder: (_) => SoftFurnishingPage(projectId: pid), settings: settings);
    case '/solution-first':
      return MaterialPageRoute(builder: (_) => SolutionFirstPage(projectId: pid), settings: settings);
    case '/structural':
      return MaterialPageRoute(builder: (_) => StructuralPage(projectId: pid), settings: settings);
    case '/takeoff':
      return MaterialPageRoute(builder: (_) => TakeoffPage(projectId: pid), settings: settings);
    case '/vr-panorama':
      return MaterialPageRoute(builder: (_) => VRPanoramaPage(projectId: pid), settings: settings);

    // ── 可选 projectId 页面 ──
    case '/b2b-delivery':
      return MaterialPageRoute(builder: (_) => B2BDeliveryPage(projectId: pidOpt), settings: settings);
    case '/ifc-export':
      return MaterialPageRoute(builder: (_) => IFCExportPage(projectId: pidOpt), settings: settings);
    case '/quality-report':
      return MaterialPageRoute(builder: (_) => QualityReportPage(initialProjectId: pidOpt), settings: settings);
    case '/timeline':
      return MaterialPageRoute(builder: (_) => TimelinePage(initialProjectId: pidOpt), settings: settings);
    case '/ai-chat':
      return MaterialPageRoute(builder: (_) => AIChatPage(projectId: pidOpt), settings: settings);

    // ── 复杂参数页面（arguments: {proposals: List, sessionId: String}） ──
    case '/design-proposal':
      final proposals = args is Map && args['proposals'] is List
          ? List<Map<String, dynamic>>.from(args['proposals'] as List)
          : <Map<String, dynamic>>[];
      final sessionId = args is Map && args['sessionId'] is String
          ? args['sessionId'] as String
          : '';
      return MaterialPageRoute(
        builder: (_) => DesignProposalPage(proposals: proposals, sessionId: sessionId),
        settings: settings,
      );
  }
  return null;
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
            child: ChangeNotifierProvider(
              // 2026 头像体系：启动随机载入手绘头像；用户可宫格选择 / 相册自定义
              create: (_) => AvatarController()..initialize(),
              child: MaterialApp(
                title: '索克家居',
                debugShowCheckedModeBanner: false,
                navigatorKey: globalNavigatorKey,
                theme: SuokeTheme.light(),
                darkTheme: SuokeTheme.dark(),
                themeMode: themeState.mode,
                onGenerateRoute: onGenerateAppRoute,
                home: const AuthGate(),
              ),
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
