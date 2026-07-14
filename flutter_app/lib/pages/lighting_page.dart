import 'package:flutter/material.dart';
import '../services/api.dart';

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

  // 暗色主题色
  static const Color _bgColor = Color(0xFF08080F);
  static const Color _cardColor = Color(0xFF12121D);
  static const Color _brandColor = Color(0xFFC9973B);
  static const Color _borderColor = Color(0xFF1E1E32);
  static const Color _primaryText = Color(0xFFE8E6E1);
  static const Color _secondaryText = Color(0xFF8A8894);

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
    _tabController = TabController(length: 2, vsync: this);
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
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _cardColor,
        foregroundColor: _primaryText,
        title: const Text('灯光设计'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '照明方案'),
            Tab(text: '灯具列表'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSchemesTab(),
          _buildFixturesTab(),
        ],
      ),
    );
  }

  // ── Tab1: 照明方案 ──

  Widget _buildSchemesTab() {
    if (_schemesLoading) {
      return const Center(child: CircularProgressIndicator(color: _brandColor));
    }
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_error!, style: const TextStyle(color: _secondaryText)),
            const SizedBox(height: 16),
            OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: _brandColor,
                side: const BorderSide(color: _borderColor),
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
                    backgroundColor: _brandColor,
                    foregroundColor: _bgColor,
                  ),
                  onPressed: _showCreateSchemeDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建方案'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
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
            color: _brandColor,
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
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
            color: isSelected ? _brandColor : _borderColor, width: 1),
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
                    color: isSelected ? _brandColor : _primaryText, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    scheme['room_name'] ?? '未命名方案',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isActive
                        ? _brandColor.withValues(alpha: 0.15)
                        : Colors.grey.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _statusLabel(scheme['status']),
                    style: TextStyle(
                      color: isActive ? _brandColor : _secondaryText,
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
            color: _cardColor,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.lightbulb, color: _brandColor, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '当前方案：${_selectedScheme?['room_name'] ?? _selectedSchemeId}',
                      style: const TextStyle(
                          color: _primaryText, fontWeight: FontWeight.w600),
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
                    backgroundColor: _brandColor,
                    foregroundColor: _bgColor,
                  ),
                  onPressed: _showAddFixtureDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加灯具'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
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
                  child: CircularProgressIndicator(color: _brandColor))
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
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _borderColor, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.light_mode, color: _brandColor, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _fixtureName(fixture),
                    style: const TextStyle(
                        color: _primaryText,
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
          Icon(icon, size: 64, color: _secondaryText),
          const SizedBox(height: 16),
          Text(message,
              style: const TextStyle(fontSize: 16, color: _secondaryText)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: _brandColor,
              foregroundColor: _bgColor,
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
            style: const TextStyle(color: _secondaryText, fontSize: 13)),
        Text(value,
            style: const TextStyle(color: _primaryText, fontSize: 13)),
      ],
    );
  }

  Widget _buildStatusTag(String label, bool enabled) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: enabled
            ? _brandColor.withValues(alpha: 0.15)
            : Colors.grey.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        enabled ? '$label：开' : '$label：关',
        style: TextStyle(
          color: enabled ? _brandColor : _secondaryText,
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
      height: 32,
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
          foregroundColor: isDanger ? Colors.redAccent : _brandColor,
          side: BorderSide(
              color: isDanger ? Colors.redAccent : _borderColor),
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
          backgroundColor: _cardColor,
          title: const Text('创建照明方案',
              style: TextStyle(color: _primaryText)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('房间名称'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: schemeType,
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('方案风格'),
                  items: types
                      .map((t) => DropdownMenuItem(
                            value: t.$1,
                            child: Text(t.$2,
                                style: const TextStyle(color: _primaryText)),
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
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('房间面积（㎡）'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: heightCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('层高（m）'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消',
                  style: TextStyle(color: _secondaryText)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: _brandColor, foregroundColor: _bgColor),
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
        backgroundColor: _cardColor,
        title: const Text('添加灯具',
            style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: typeCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('灯具类型（如：筒灯、射灯、吊灯）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: brandCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('品牌'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: modelCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('型号'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: wattageCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('功率（W）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: lumensCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('光通量（lm）'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: _secondaryText)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: _brandColor, foregroundColor: _bgColor),
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
        backgroundColor: _cardColor,
        title: const Text('确认删除',
            style: TextStyle(color: _primaryText)),
        content: const Text('确定要删除此方案吗？此操作不可撤销。',
            style: TextStyle(color: _secondaryText)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: _secondaryText)),
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
        backgroundColor: _cardColor,
        title: const Text('确认删除',
            style: TextStyle(color: _primaryText)),
        content: const Text('确定要删除此灯具吗？',
            style: TextStyle(color: _secondaryText)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消',
                style: TextStyle(color: _secondaryText)),
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
      labelStyle: const TextStyle(color: _secondaryText),
      filled: true,
      fillColor: _bgColor,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _borderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: _brandColor),
      ),
    );
  }
}
