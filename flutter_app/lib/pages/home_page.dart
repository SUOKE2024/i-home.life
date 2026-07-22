import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../main.dart' show ThemeState;
import '../theme/suoke_theme.dart';
import '../services/offline_cache_service.dart';
import '../services/project_context.dart';
import '../widgets/loading_skeleton.dart';
import 'dashboard_page.dart';
import 'projects_page.dart';
import 'ai_chat_page.dart';
import 'materials_page.dart';
import 'cad_page.dart';

// 更多页二级功能模块
import 'budget_page.dart';
import 'construction_page.dart';
import 'ar_scan_page.dart';
import 'design_deepening_page.dart';
import 'procurement_enhanced_page.dart';
import 'project_detail_page.dart';
import 'settlement_page.dart';
import 'smart_home_page.dart';
import 'vr_panorama_page.dart';
import 'ai_image_page.dart';
import 'points_page.dart';
import 'identity_page.dart';
import 'lighting_page.dart';
import 'kitchen_page.dart';
import 'bathroom_page.dart';
import 'soft_furnishing_page.dart';
import 'appliance_page.dart';
import 'hard_decoration_page.dart';
import 'door_window_waterproof_page.dart';
import 'furniture_catalog_page.dart';
import 'mep_page.dart';
import 'structural_page.dart';
import 'change_orders_page.dart';
import 'takeoff_page.dart';
import 'tasks_page.dart';
import 'products_page.dart';
import 'custom_furniture_page.dart';
import 'kitchen_bath_mep_page.dart';
import 'crew_page.dart';
import 'scene_automation_page.dart';
import 'worker_page.dart';
import 'chat_page.dart';
import 'timeline_page.dart';
import 'quality_report_page.dart';
import 'settings_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _currentIndex = 0;
  bool _isOffline = false;
  StreamSubscription<bool>? _connectivitySub;

  /// 主导航：聊天工作台作为首页（对齐 Web 端 workbench.html）
  late final List<Widget> _pages = [
    const AIChatPage(),
    const DashboardPage(),
    const ProjectsPage(),
    const CADPage(),
    const MaterialsPage(),
  ];

  /// Tab 标签名（与 Web 端导航概念对齐）
  static const _tabLabels = ['工作台', '概览', '项目', '设计台', '物料'];
  static const _tabIcons = [
    Icons.chat_bubble_outline,
    Icons.dashboard_outlined,
    Icons.home_work_outlined,
    Icons.design_services_outlined,
    Icons.inventory_2_outlined,
  ];
  static const _tabIconsSelected = [
    Icons.chat_bubble,
    Icons.dashboard,
    Icons.home_work,
    Icons.design_services,
    Icons.inventory_2,
  ];

  @override
  void initState() {
    super.initState();
    _initConnectivity();
  }

  Future<void> _initConnectivity() async {
    final online = await OfflineCacheService().isConnected();
    if (mounted) setState(() => _isOffline = !online);
    _connectivitySub = OfflineCacheService().onConnectivityChanged.listen((online) {
      if (mounted) setState(() => _isOffline = !online);
    });
  }

  @override
  void dispose() {
    _connectivitySub?.cancel();
    super.dispose();
  }

  /// 离线时移除子页面顶部 padding
  Widget _wrapPage(Widget child) {
    if (!_isOffline) return child;
    return MediaQuery.removeViewPadding(
      context: context,
      removeTop: true,
      child: child,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isMore = _currentIndex == _pages.length;
    final body = isMore ? _MorePage(isDark: isDark) : _pages[_currentIndex];

    return Scaffold(
      body: Column(
        children: [
          if (_isOffline) _buildOfflineBanner(),
          Expanded(child: _wrapPage(body)),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (i) => setState(() => _currentIndex = i),
        destinations: List.generate(6, (i) {
          if (i < 5) {
            return NavigationDestination(
              icon: Icon(_tabIcons[i]),
              selectedIcon: Icon(_tabIconsSelected[i]),
              label: _tabLabels[i],
            );
          }
          return const NavigationDestination(
            icon: Icon(Icons.apps_outlined),
            selectedIcon: Icon(Icons.apps),
            label: '更多',
          );
        }),
      ),
      // 主题切换按钮
      floatingActionButton: _currentIndex == 0
          ? null
          : FloatingActionButton.small(
              onPressed: () {
                context.read<ThemeState>().toggle();
              },
              backgroundColor: SuokeDesignTokens.cardBg,
              foregroundColor: SuokeDesignTokens.accent,
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
                side: const BorderSide(color: SuokeDesignTokens.border),
              ),
              child: Icon(
                isDark ? Icons.light_mode : Icons.dark_mode,
                size: 20,
              ),
            ),
    );
  }

  Widget _buildOfflineBanner() {
    return Container(
      color: const Color(0xFFE65100),
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top,
        bottom: 8,
        left: 16,
        right: 16,
      ),
      child: const Row(
        children: [
          Icon(Icons.cloud_off, color: Colors.white, size: 16),
          SizedBox(width: 8),
          Text('离线模式 · 显示缓存数据',
              style: TextStyle(color: Colors.white, fontSize: 13)),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 「更多」页面
// ═══════════════════════════════════════════

class _MoreItem {
  final IconData icon;
  final String title;
  final String subtitle;
  final Widget Function(String projectId) builder;
  const _MoreItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.builder,
  });
}

class _MorePage extends StatefulWidget {
  final bool isDark;
  const _MorePage({required this.isDark});

  @override
  State<_MorePage> createState() => _MorePageState();
}

class _MorePageState extends State<_MorePage> {
  late final List<_MoreItem> _items = [
    _MoreItem(icon: Icons.folder_open_outlined, title: '项目详情', subtitle: 'Project Detail',
        builder: (id) => ProjectDetailPage(projectId: id)),
    _MoreItem(icon: Icons.account_balance_wallet_outlined, title: '预算', subtitle: 'Budget',
        builder: (id) => BudgetPage(projectId: id)),
    _MoreItem(icon: Icons.engineering_outlined, title: '施工', subtitle: 'Construction',
        builder: (id) => ConstructionPage(projectId: id)),
    _MoreItem(icon: Icons.view_in_ar_outlined, title: 'AR扫描', subtitle: 'AR Scan',
        builder: (id) => ARScanPage(projectId: id)),
    _MoreItem(icon: Icons.architecture_outlined, title: '深化设计', subtitle: 'Design Deepening',
        builder: (id) => DesignDeepeningPage(projectId: id)),
    _MoreItem(icon: Icons.shopping_cart_checkout_outlined, title: '采购增强', subtitle: 'Procurement Enhanced',
        builder: (id) => ProcurementEnhancedPage(projectId: id)),
    _MoreItem(icon: Icons.receipt_long_outlined, title: '结算', subtitle: 'Settlement',
        builder: (id) => SettlementPage(projectId: id)),
    _MoreItem(icon: Icons.home_filled, title: '智能家居', subtitle: 'Smart Home',
        builder: (id) => SmartHomePage(projectId: id)),
    _MoreItem(icon: Icons.panorama_photosphere_outlined, title: 'VR全景', subtitle: 'VR Panorama',
        builder: (id) => VRPanoramaPage(projectId: id)),
    _MoreItem(icon: Icons.image_outlined, title: 'AI图片', subtitle: 'AI Image',
        builder: (id) => AIImagePage(projectId: id)),
    _MoreItem(icon: Icons.stars_outlined, title: '积分商城', subtitle: 'Points Mall',
        builder: (id) => PointsPage()),
    _MoreItem(icon: Icons.verified_user_outlined, title: '身份认证', subtitle: 'Identity',
        builder: (id) => IdentityPage()),
    _MoreItem(icon: Icons.lightbulb_outlined, title: '照明设计', subtitle: 'Lighting',
        builder: (id) => LightingPage(projectId: id)),
    _MoreItem(icon: Icons.kitchen_outlined, title: '厨房设计', subtitle: 'Kitchen',
        builder: (id) => KitchenPage(projectId: id)),
    _MoreItem(icon: Icons.bathtub_outlined, title: '卫浴设计', subtitle: 'Bathroom',
        builder: (id) => BathroomPage(projectId: id)),
    _MoreItem(icon: Icons.chair_outlined, title: '软装设计', subtitle: 'Soft Furnishing',
        builder: (id) => SoftFurnishingPage(projectId: id)),
    _MoreItem(icon: Icons.electrical_services_outlined, title: '电器规划', subtitle: 'Appliance',
        builder: (id) => AppliancePage(projectId: id)),
    _MoreItem(icon: Icons.format_paint_outlined, title: '硬装设计', subtitle: 'Hard Decoration',
        builder: (id) => HardDecorationPage(projectId: id)),
    _MoreItem(icon: Icons.window_outlined, title: '门窗防水', subtitle: 'Door & Waterproof',
        builder: (id) => DoorWindowWaterproofPage(projectId: id)),
    _MoreItem(icon: Icons.inventory_2_outlined, title: '家具品类库', subtitle: 'Furniture Catalog',
        builder: (id) => FurnitureCatalogPage()),
    _MoreItem(icon: Icons.water_drop_outlined, title: '水电规划', subtitle: 'MEP',
        builder: (id) => MepPage(projectId: id)),
    _MoreItem(icon: Icons.foundation_outlined, title: '土建结构', subtitle: 'Structural',
        builder: (id) => StructuralPage(projectId: id)),
    _MoreItem(icon: Icons.change_circle_outlined, title: '变更订单', subtitle: 'Change Orders',
        builder: (id) => ChangeOrdersPage(projectId: id)),
    _MoreItem(icon: Icons.calculate_outlined, title: '工程量', subtitle: 'Takeoff',
        builder: (id) => TakeoffPage(projectId: id)),
    _MoreItem(icon: Icons.task_alt_outlined, title: '任务管理', subtitle: 'Tasks',
        builder: (id) => TasksPage(projectId: id)),
    _MoreItem(icon: Icons.shopping_bag_outlined, title: '产品库', subtitle: 'Products',
        builder: (id) => ProductsPage()),
    _MoreItem(icon: Icons.carpenter_outlined, title: '定制家具', subtitle: 'Custom Furniture (F27)',
        builder: (id) => CustomFurniturePage(projectId: id)),
    _MoreItem(icon: Icons.plumbing_outlined, title: '厨卫水电', subtitle: 'Kitchen/Bath MEP (F18)',
        builder: (id) => KitchenBathMepPage(projectId: id)),
    _MoreItem(icon: Icons.groups_outlined, title: '工程队匹配', subtitle: 'Crew (F36)',
        builder: (id) => CrewPage(projectId: id)),
    _MoreItem(icon: Icons.person_search_outlined, title: '服务者匹配', subtitle: 'Worker (F35)',
        builder: (id) => WorkerPage(projectId: id)),
    _MoreItem(icon: Icons.auto_awesome_outlined, title: '场景编辑', subtitle: 'Scene Automation (F32)',
        builder: (id) => SceneAutomationPage(projectId: id)),
    _MoreItem(icon: Icons.chat_outlined, title: '协作聊天', subtitle: 'Chat (F40)',
        builder: (id) => ChatPage(projectId: id)),
    _MoreItem(icon: Icons.timeline_outlined, title: '装修进度', subtitle: 'Timeline',
        builder: (id) => TimelinePage(initialProjectId: id)),
    _MoreItem(icon: Icons.verified_outlined, title: '质检报告', subtitle: 'Quality Report',
        builder: (id) => QualityReportPage(initialProjectId: id)),
    _MoreItem(icon: Icons.settings_outlined, title: '设置', subtitle: 'Settings',
        builder: (id) => const SettingsPage()),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final pc = context.read<ProjectContext>();
      if (pc.projects.isEmpty) {
        pc.loadProjects();
      }
    });
  }

  void _openItem(_MoreItem item) {
    final pc = context.read<ProjectContext>();
    final pid = pc.currentProjectId;
    if (pid == null || pid.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请先创建或选择项目')),
      );
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => item.builder(pid)),
    );
  }

  Color get _bg => SuokeDesignTokens.bgDeep;
  Color get _card => SuokeDesignTokens.cardBg;
  Color get _border => SuokeDesignTokens.border;
  Color get _textPrimary => SuokeDesignTokens.textPrimary;
  Color get _textSecondary => SuokeDesignTokens.textSecondary;
  Color get _brand => SuokeDesignTokens.accent;

  @override
  Widget build(BuildContext context) {
    final pc = context.watch<ProjectContext>();
    final projects = pc.projects;

    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        top: true,
        bottom: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 4),
              child: Text('更多功能',
                  style: TextStyle(
                      color: _textPrimary,
                      fontSize: 22,
                      fontWeight: FontWeight.bold)),
            ),
            _buildProjectSelector(pc, projects),
            const SizedBox(height: 4),
            Expanded(
              child: pc.loading && projects.isEmpty
                  ? const LoadingSkeleton(itemCount: 4, itemHeight: 120)
                  : projects.isEmpty
                      ? _buildEmpty(() => pc.loadProjects())
                      : GridView.count(
                          padding: const EdgeInsets.all(16),
                          crossAxisCount: 2,
                          mainAxisSpacing: 12,
                          crossAxisSpacing: 12,
                          childAspectRatio: 1.5,
                          children: _items
                              .map((item) => _MoreCard(
                                    item: item,
                                    onTap: () => _openItem(item),
                                  ))
                              .toList(),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProjectSelector(ProjectContext pc, List<Map<String, dynamic>> projects) {
    final currentId = pc.currentProjectId;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          color: const Color(0xFF0D0D18),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: _border),
        ),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            value: projects.any((p) => (p['id'] ?? '').toString() == currentId) ? currentId : null,
            dropdownColor: _card,
            hint: Text('选择项目', style: TextStyle(color: _textSecondary)),
            isExpanded: true,
            icon: Icon(Icons.unfold_more, color: _textSecondary, size: 20),
            items: projects.map((p) {
              final id = (p['id'] ?? '').toString();
              return DropdownMenuItem<String>(
                value: id,
                child: Text(
                  (p['name'] ?? '未命名项目').toString(),
                  style: TextStyle(color: _textPrimary),
                  overflow: TextOverflow.ellipsis,
                ),
              );
            }).toList(),
            onChanged: (v) {
              if (v != null) pc.switchProject(v);
            },
          ),
        ),
      ),
    );
  }

  Widget _buildEmpty(VoidCallback onRefresh) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.home_work_outlined, size: 48, color: _textSecondary),
          const SizedBox(height: 12),
          Text('暂无项目，请先在「项目」页创建', style: TextStyle(color: _textSecondary)),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: onRefresh, child: const Text('刷新')),
        ],
      ),
    );
  }
}

class _MoreCard extends StatelessWidget {
  final _MoreItem item;
  final VoidCallback onTap;
  const _MoreCard({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      color: SuokeDesignTokens.cardBgSemi,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
        side: const BorderSide(color: SuokeDesignTokens.border),
      ),
      elevation: 0,
      child: InkWell(
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(item.icon, color: SuokeDesignTokens.accent, size: 28),
              const SizedBox(height: 8),
              Text(item.title,
                  style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurface,
                      fontSize: 15,
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text(item.subtitle,
                  style: TextStyle(color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5), fontSize: 11)),
            ],
          ),
        ),
      ),
    );
  }
}
