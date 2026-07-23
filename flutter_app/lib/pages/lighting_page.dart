import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/floor_plan_canvas.dart';

class LightingPage extends StatefulWidget {
  final String projectId;
  const LightingPage({super.key, required this.projectId});

  @override
  State<LightingPage> createState() => _LightingPageState();
}

class _LightingPageState extends State<LightingPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  // 方案
  List<dynamic> _schemes = [];
  bool _schemesLoading = false;
  String? _error;
  String? _selectedSchemeId;
  Map<String, dynamic>? _selectedScheme;

  // 灯具
  List<dynamic> _fixtures = [];
  bool _fixturesLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadSchemes();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadSchemes() async {
    setState(() {
      _schemesLoading = true;
      _error = null;
    });
    final result = await _api.lightingListSchemes(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _schemes = _extractList(result.data, 'schemes');
      });
    } else {
      setState(() => _error = '加载失败，请检查网络后重试');
    }
    setState(() => _schemesLoading = false);
  }

  Future<void> _loadFixtures(String schemeId) async {
    setState(() => _fixturesLoading = true);
    final result = await _api.lightingListFixtures(schemeId);
    if (result.isSuccess) {
      setState(() {
        _fixtures = _extractList(result.data, 'fixtures');
      });
    } else {
      _showError('加载灯具失败：${result.error}');
    }
    setState(() => _fixturesLoading = false);
  }

  List<dynamic> _extractList(dynamic data, String key) {
    if (data is List) return data;
    if (data is Map) return (data[key] as List?) ?? [];
    return [];
  }

  // ── 方案操作 ──

  Future<void> _createScheme(
    String roomName,
    String schemeType,
    double roomArea,
    double ceilingHeight,
  ) async {
    final result = await _api.lightingCreateScheme({
      'project_id': widget.projectId,
      'room_name': roomName,
      'scheme_type': schemeType,
      'room_area': roomArea,
      'ceiling_height': ceilingHeight,
    });
    if (result.isSuccess) {
      _showSuccess('方案已创建');
      _loadSchemes();
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deleteScheme(String schemeId) async {
    final result = await _api.lightingDeleteScheme(schemeId);
    if (result.isSuccess) {
      _showSuccess('方案已删除');
      if (_selectedSchemeId == schemeId) {
        setState(() {
          _selectedSchemeId = null;
          _selectedScheme = null;
          _fixtures = [];
        });
      }
      _loadSchemes();
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  void _selectScheme(Map<String, dynamic> scheme) {
    final id = (scheme['id'] ?? '').toString();
    setState(() {
      _selectedSchemeId = id;
      _selectedScheme = scheme;
    });
    _loadFixtures(id);
    _tabController.animateTo(1);
    _showSuccess('已选择方案：${scheme['room_name'] ?? ''}');
  }

  // ── 灯具操作 ──

  Future<void> _addFixture(
    String fixtureType,
    String brand,
    String model,
    double wattage,
    double lumens,
  ) async {
    if (_selectedSchemeId == null) return;
    final result = await _api.lightingAddFixture(_selectedSchemeId!, {
      'fixture_type': fixtureType,
      'brand': brand,
      'model': model,
      'wattage_w': wattage,
      'lumens': lumens,
    });
    if (result.isSuccess) {
      _showSuccess('灯具已添加');
      _loadFixtures(_selectedSchemeId!);
    } else {
      _showError('添加失败：${result.error}');
    }
  }

  Future<void> _deleteFixture(String fixtureId) async {
    final result = await _api.lightingDeleteFixture(fixtureId);
    if (result.isSuccess) {
      _showSuccess('灯具已删除');
      if (_selectedSchemeId != null) {
        _loadFixtures(_selectedSchemeId!);
      }
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  // ── 工具方法 ──

  void _showSuccess(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  void _showError(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'draft':
        return '草稿';
      case 'active':
        return '已启用';
      case 'archived':
        return '已归档';
      default:
        return status ?? '草稿';
    }
  }

  String _schemeTypeLabel(String? type) {
    switch (type) {
      case 'main_light':
        return '主灯';
      case 'ambient':
        return '氛围灯';
      case 'task':
        return '任务灯';
      case 'accent':
        return '重点灯';
      default:
        return type ?? '主灯';
    }
  }

  String _positionText(Map<String, dynamic> fixture) {
    final x = fixture['position_x'];
    final y = fixture['position_y'];
    final z = fixture['position_z'];
    if (x == null && y == null && z == null) return '未指定';
    final parts = <String>[];
    if (x != null) parts.add('X:$x');
    if (y != null) parts.add('Y:$y');
    if (z != null) parts.add('Z:$z');
    return parts.isEmpty ? '未指定' : parts.join('，');
  }

  String _fixtureName(Map<String, dynamic> fixture) {
    final type = _schemeTypeLabel(fixture['fixture_type']);
    final brand = fixture['brand'] as String?;
    final model = fixture['model'] as String?;
    if (brand != null && brand.isNotEmpty) {
      return model != null && model.isNotEmpty ? '$brand $model' : brand;
    }
    return type;
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bgDeep,
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.cardBg,
        foregroundColor: SuokeDesignTokens.textPrimary,
        title: const Text('灯光设计'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSecondary,
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '照明方案'),
            Tab(text: '灯具列表'),
            Tab(text: '布局图'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSchemesTab(),
          _buildFixturesTab(),
          _buildLayoutTab(),
        ],
      ),
    );
  }

  // ── Tab1: 照明方案 ──

  Widget _buildSchemesTab() {
    if (_schemesLoading) {
      return const Center(child: CircularProgressIndicator(color: SuokeDesignTokens.accent));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!, style: const TextStyle(color: SuokeDesignTokens.textSecondary)),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: SuokeDesignTokens.accent,
                side: const BorderSide(color: SuokeDesignTokens.border),
              ),
              onPressed: _loadSchemes,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
            ),
          ],
        ),
      );
    }
    if (_schemes.isEmpty) {
      return _buildEmptyState(
        icon: Icons.lightbulb_outline,
        message: '暂无照明方案',
        actionLabel: '创建方案',
        onAction: _showCreateSchemeDialog,
      );
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bgDeep,
                  ),
                  onPressed: _showCreateSchemeDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建方案'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.textPrimary,
                  side: const BorderSide(color: SuokeDesignTokens.border),
                ),
                onPressed: _loadSchemes,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            color: SuokeDesignTokens.accent,
            onRefresh: _loadSchemes,
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _schemes.length,
              itemBuilder: (context, index) {
                final scheme = _schemes[index] as Map<String, dynamic>;
                return _buildSchemeCard(scheme);
              },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSchemeCard(Map<String, dynamic> scheme) {
    final id = (scheme['id'] ?? '').toString();
    final isSelected = _selectedSchemeId == id;
    final status = scheme['status']?.toString() ?? 'draft';
    final isActive = status == 'active';
    return Card(
      color: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
            color: isSelected ? SuokeDesignTokens.accent : SuokeDesignTokens.border, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.lightbulb,
                    color: isSelected ? SuokeDesignTokens.accent : SuokeDesignTokens.textPrimary, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    scheme['room_name'] ?? '未命名方案',
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isActive
                        ? SuokeDesignTokens.accent.withValues(alpha: 0.15)
                        : Colors.grey.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _statusLabel(scheme['status']),
                    style: TextStyle(
                      color: isActive ? SuokeDesignTokens.accent : SuokeDesignTokens.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '风格', _schemeTypeLabel(scheme['scheme_type'])),
                _buildInfoChip(
                    '色温', '${scheme['color_temp_k'] ?? '-'} K'),
                _buildInfoChip(
                    '亮度', '${scheme['total_lumens'] ?? '-'} lm'),
                _buildInfoChip(
                    '面积', '${scheme['room_area'] ?? 0} ㎡'),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildActionButton(
                  '选为当前',
                  Icons.check,
                  () => _selectScheme(scheme),
                ),
                _buildActionButton(
                  '删除',
                  Icons.delete_outline,
                  () => _confirmDeleteScheme(id),
                  isDanger: true,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab2: 灯具列表 ──

  Widget _buildFixturesTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.light_mode_outlined,
        message: '请先在"照明方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          child: Card(
            color: SuokeDesignTokens.cardBg,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.lightbulb, color: SuokeDesignTokens.accent, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '当前方案：${_selectedScheme?['room_name'] ?? _selectedSchemeId}',
                      style: const TextStyle(
                          color: SuokeDesignTokens.textPrimary, fontWeight: FontWeight.w600),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bgDeep,
                  ),
                  onPressed: _showAddFixtureDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加灯具'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.textPrimary,
                  side: const BorderSide(color: SuokeDesignTokens.border),
                ),
                onPressed: () => _loadFixtures(_selectedSchemeId!),
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _fixturesLoading
              ? const Center(
                  child: CircularProgressIndicator(color: SuokeDesignTokens.accent))
              : _fixtures.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.light_mode_outlined,
                      message: '暂无灯具',
                      actionLabel: '添加灯具',
                      onAction: _showAddFixtureDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _fixtures.length,
                      itemBuilder: (context, index) {
                        final fixture =
                            _fixtures[index] as Map<String, dynamic>;
                        return _buildFixtureCard(fixture);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildFixtureCard(Map<String, dynamic> fixture) {
    final id = (fixture['id'] ?? '').toString();
    final dimmable = fixture['dimmable'] == true;
    final smartControl = fixture['smart_control'] == true;
    return Card(
      color: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: SuokeDesignTokens.border, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.light_mode, color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _fixtureName(fixture),
                    style: const TextStyle(
                        color: SuokeDesignTokens.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline,
                      color: Colors.redAccent, size: 20),
                  onPressed: () => _confirmDeleteFixture(id),
                  tooltip: '删除',
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '类型', _schemeTypeLabel(fixture['fixture_type'])),
                _buildInfoChip(
                    '功率', '${fixture['wattage_w'] ?? 0} W'),
                _buildInfoChip(
                    '位置', _positionText(fixture)),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildStatusTag('可调光', dimmable),
                _buildStatusTag('智能控制', smartControl),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab3: 布局图 ──

  Widget _buildLayoutTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.map_outlined,
        message: '请先在"照明方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }

    final area = (_selectedScheme!['room_area'] as num?)?.toDouble() ?? 0;
    final sideM = area > 0 ? math.sqrt(area) : 3.0;
    final sideMm = sideM * 1000;

    final colorTempK =
        (_selectedScheme!['color_temp_k'] as num?)?.toDouble();

    final components = _fixtures.map((f) {
      final fMap = f as Map<String, dynamic>;
      final id = (fMap['id'] ?? '').toString();
      final type = (fMap['fixture_type'] ?? '').toString();
      final label = _fixtureName(fMap);
      final px = (fMap['position_x'] as num?)?.toDouble() ?? 100;
      final py = (fMap['position_y'] as num?)?.toDouble() ?? 100;
      return FloorPlanComponent(
        id: id,
        label: label,
        type: 'light',
        x: px,
        y: py,
        width: 300,
        height: 300,
        color: _fixtureColor(type),
      );
    }).toList();

    return Column(
      children: [
        // 信息栏：色温范围提示
        if (colorTempK != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            color: SuokeDesignTokens.cardBg,
            child: Row(
              children: [
                const Icon(Icons.thermostat_outlined,
                    color: SuokeDesignTokens.accent, size: 16),
                const SizedBox(width: 8),
                Text(
                  '色温：${colorTempK.toStringAsFixed(0)} K',
                  style: const TextStyle(
                      color: SuokeDesignTokens.textSecondary, fontSize: 13),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _buildColorTempBar(colorTempK),
                ),
              ],
            ),
          ),
        Expanded(
          child: FloorPlanCanvas(
            roomWidth: sideMm,
            roomHeight: sideMm,
            roomLabel: _selectedScheme!['room_name']?.toString() ?? '房间',
            components: components,
            onComponentTap: (componentId) {
              final fixture = _fixtures.firstWhere(
                (f) => (f['id'] ?? '').toString() == componentId,
                orElse: () => <String, dynamic>{},
              );
              if (fixture.isNotEmpty) {
                _showLightDetailSheet(fixture as Map<String, dynamic>);
              }
            },
          ),
        ),
      ],
    );
  }

  Widget _buildColorTempBar(double k) {
    // 色温范围：2700K（暖黄）→ 6500K（冷白）
    final ratio = ((k - 2700) / (6500 - 2700)).clamp(0.0, 1.0);
    return Container(
      height: 8,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(4),
        gradient: const LinearGradient(
          colors: [
            Color(0xFFFFB74D), // 暖黄 2700K
            Color(0xFFFFF9C4), // 中性
            Color(0xFFE3F2FD), // 冷白 6500K
          ],
        ),
      ),
      child: Align(
        alignment: Alignment(ratio * 2 - 1, 0),
        child: Container(
          width: 4,
          height: 14,
          decoration: BoxDecoration(
            color: SuokeDesignTokens.accent,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
      ),
    );
  }

  Color _fixtureColor(String fixtureType) {
    switch (fixtureType) {
      case 'main_light':
        return const Color(0xFFFFF9C4); // 柔黄
      case 'ambient':
        return const Color(0xFF00BCD4); // 青色
      case 'accent':
        return const Color(0xFFE040FB); // 品红
      case 'task':
        return const Color(0xFFFFFFFF); // 白色
      default:
        return const Color(0xFFFFF9C4);
    }
  }

  void _showLightDetailSheet(Map<String, dynamic> fixture) {
    final type = _schemeTypeLabel(fixture['fixture_type']?.toString());
    final brand = fixture['brand']?.toString() ?? '-';
    final model = fixture['model']?.toString() ?? '-';
    final wattage = (fixture['wattage_w'] as num?)?.toDouble() ?? 0;
    final lumens = (fixture['lumens'] as num?)?.toDouble() ?? 0;
    final colorTemp = (fixture['color_temp_k'] as num?)?.toDouble();

    showModalBottomSheet(
      context: context,
      backgroundColor: SuokeDesignTokens.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: SuokeDesignTokens.textSecondary.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text('${brand.isNotEmpty ? '$brand ' : ''}$model',
                style: const TextStyle(
                    color: SuokeDesignTokens.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            _buildInfoChip('类型', type),
            const SizedBox(height: 4),
            _buildInfoChip('品牌', brand),
            const SizedBox(height: 4),
            _buildInfoChip('型号', model),
            const SizedBox(height: 4),
            _buildInfoChip('功率', '${wattage.toStringAsFixed(0)} W'),
            const SizedBox(height: 4),
            _buildInfoChip('光通量', '${lumens.toStringAsFixed(0)} lm'),
            if (colorTemp != null) ...[
              const SizedBox(height: 4),
              _buildInfoChip('色温', '${colorTemp.toStringAsFixed(0)} K'),
            ],
          ],
        ),
      ),
    );
  }

  // ── 通用组件 ──

  Widget _buildEmptyState({
    required IconData icon,
    required String message,
    required String actionLabel,
    required VoidCallback onAction,
  }) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: SuokeDesignTokens.textSecondary),
          const SizedBox(height: 16),
          Text(message,
              style: const TextStyle(fontSize: 16, color: SuokeDesignTokens.textSecondary)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              foregroundColor: SuokeDesignTokens.bgDeep,
            ),
            onPressed: onAction,
            icon: const Icon(Icons.add),
            label: Text(actionLabel),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoChip(String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label：',
            style: const TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
        Text(value,
            style: const TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 13)),
      ],
    );
  }

  Widget _buildStatusTag(String label, bool enabled) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: enabled
            ? SuokeDesignTokens.accent.withValues(alpha: 0.15)
            : Colors.grey.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        enabled ? '$label：开' : '$label：关',
        style: TextStyle(
          color: enabled ? SuokeDesignTokens.accent : SuokeDesignTokens.textSecondary,
          fontSize: 12,
        ),
      ),
    );
  }

  Widget _buildActionButton(
    String label,
    IconData icon,
    VoidCallback onPressed, {
    bool isDanger = false,
  }) {
    return SizedBox(
      height: 48, // WCAG 2.2 minimum touch target
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
          foregroundColor: isDanger ? Colors.redAccent : SuokeDesignTokens.accent,
          side: BorderSide(
              color: isDanger ? Colors.redAccent : SuokeDesignTokens.border),
          padding: const EdgeInsets.symmetric(horizontal: 10),
        ),
        onPressed: onPressed,
        icon: Icon(icon, size: 16),
        label: Text(label, style: const TextStyle(fontSize: 13)),
      ),
    );
  }

  // ── 对话框 ──

  void _showCreateSchemeDialog() {
    final nameCtrl = TextEditingController();
    final areaCtrl = TextEditingController(text: '0');
    final heightCtrl = TextEditingController(text: '2.8');
    String schemeType = 'main_light';
    const types = [
      ('main_light', '主灯'),
      ('ambient', '氛围灯'),
      ('task', '任务灯'),
      ('accent', '重点灯'),
    ];
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.cardBg,
          title: const Text('创建照明方案',
              style: TextStyle(color: SuokeDesignTokens.textPrimary)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: _inputDecoration('房间名称'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: schemeType,
                  dropdownColor: SuokeDesignTokens.cardBg,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: _inputDecoration('方案风格'),
                  items: types
                      .map((t) => DropdownMenuItem(
                            value: t.$1,
                            child: Text(t.$2,
                                style: const TextStyle(color: SuokeDesignTokens.textPrimary)),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => schemeType = v);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: areaCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: _inputDecoration('房间面积（㎡）'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: heightCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                  decoration: _inputDecoration('层高（m）'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消',
                  style: TextStyle(color: SuokeDesignTokens.textSecondary)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: SuokeDesignTokens.accent, foregroundColor: SuokeDesignTokens.bgDeep),
              onPressed: () {
                final name = nameCtrl.text.trim();
                if (name.isEmpty) {
                  _showError('请输入房间名称');
                  return;
                }
                final area = double.tryParse(areaCtrl.text.trim()) ?? 0.0;
                final height = double.tryParse(heightCtrl.text.trim()) ?? 2.8;
                Navigator.pop(ctx);
                _createScheme(name, schemeType, area, height);
              },
              child: const Text('创建'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddFixtureDialog() {
    final typeCtrl = TextEditingController();
    final brandCtrl = TextEditingController();
    final modelCtrl = TextEditingController();
    final wattageCtrl = TextEditingController(text: '0');
    final lumensCtrl = TextEditingController(text: '0');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('添加灯具',
            style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: typeCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('灯具类型（如：筒灯、射灯、吊灯）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: brandCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('品牌'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: modelCtrl,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('型号'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: wattageCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('功率（W）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: lumensCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: SuokeDesignTokens.textPrimary),
                decoration: _inputDecoration('光通量（lm）'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: SuokeDesignTokens.accent, foregroundColor: SuokeDesignTokens.bgDeep),
            onPressed: () {
              final type = typeCtrl.text.trim();
              if (type.isEmpty) {
                _showError('请输入灯具类型');
                return;
              }
              final wattage = double.tryParse(wattageCtrl.text.trim()) ?? 0.0;
              final lumens = double.tryParse(lumensCtrl.text.trim()) ?? 0.0;
              Navigator.pop(ctx);
              _addFixture(
                type,
                brandCtrl.text.trim(),
                modelCtrl.text.trim(),
                wattage,
                lumens,
              );
            },
            child: const Text('添加'),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteScheme(String schemeId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('确认删除',
            style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: const Text('确定要删除此方案吗？此操作不可撤销。',
            style: TextStyle(color: SuokeDesignTokens.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.redAccent,
                foregroundColor: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              _deleteScheme(schemeId);
            },
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteFixture(String fixtureId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.cardBg,
        title: const Text('确认删除',
            style: TextStyle(color: SuokeDesignTokens.textPrimary)),
        content: const Text('确定要删除此灯具吗？',
            style: TextStyle(color: SuokeDesignTokens.textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: SuokeDesignTokens.textSecondary)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.redAccent,
                foregroundColor: Colors.white),
            onPressed: () {
              Navigator.pop(ctx);
              _deleteFixture(fixtureId);
            },
            child: const Text('删除'),
          ),
        ],
      ),
    );
  }

  InputDecoration _inputDecoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: SuokeDesignTokens.textSecondary),
      filled: true,
      fillColor: SuokeDesignTokens.bgDeep,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.accent),
      ),
    );
  }
}
