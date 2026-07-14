import 'package:flutter/material.dart';
import '../services/api.dart';

class HardDecorationPage extends StatefulWidget {
  final String projectId;
  const HardDecorationPage({super.key, required this.projectId});

  @override
  State<HardDecorationPage> createState() => _HardDecorationPageState();
}

class _HardDecorationPageState extends State<HardDecorationPage>
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

  // 地面 / 墙面 / 天花
  List<dynamic> _floors = [];
  List<dynamic> _walls = [];
  List<dynamic> _ceilings = [];
  bool _detailsLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
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
    final result = await _api.hardDecoListSchemes(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _schemes = _extractList(result.data, 'schemes');
      });
    } else {
      setState(() => _error = '加载失败，请检查网络后重试');
    }
    setState(() => _schemesLoading = false);
  }

  Future<void> _loadDetails(String schemeId) async {
    setState(() => _detailsLoading = true);
    final results = await Future.wait([
      _safeList(_api.hardDecoListFloors(schemeId), 'floors'),
      _safeList(_api.hardDecoListWalls(schemeId), 'walls'),
      _safeList(_api.hardDecoListCeilings(schemeId), 'ceilings'),
    ]);
    if (!mounted) return;
    setState(() {
      _floors = results[0];
      _walls = results[1];
      _ceilings = results[2];
      _detailsLoading = false;
    });
  }

  Future<List<dynamic>> _safeList(
      Future<Result<dynamic>> future, String key) async {
    final result = await future;
    if (result.isSuccess) {
      return _extractList(result.data, key);
    }
    return [];
  }

  List<dynamic> _extractList(dynamic data, String key) {
    if (data is List) return data;
    if (data is Map) return (data[key] as List?) ?? [];
    return [];
  }

  // ── 方案操作 ──

  Future<void> _createScheme(String name, String style) async {
    final result = await _api.hardDecoCreateScheme({
      'project_id': widget.projectId,
      'name': name,
      'style': style,
    });
    if (result.isSuccess) {
      _showSuccess('方案已创建');
      _loadSchemes();
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deleteScheme(String schemeId) async {
    final result = await _api.hardDecoDeleteScheme(schemeId);
    if (result.isSuccess) {
      _showSuccess('方案已删除');
      if (_selectedSchemeId == schemeId) {
        setState(() {
          _selectedSchemeId = null;
          _selectedScheme = null;
          _floors = [];
          _walls = [];
          _ceilings = [];
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
      _floors = [];
      _walls = [];
      _ceilings = [];
    });
    _loadDetails(id);
    _showSuccess('已选择方案：${scheme['name'] ?? ''}');
  }

  // ── 地面/墙面操作 ──

  Future<void> _addFloor(
    String room,
    String material,
    String spec,
    double area,
  ) async {
    if (_selectedSchemeId == null) return;
    final result = await _api.hardDecoAddFloor(_selectedSchemeId!, {
      'room_name': room,
      'material': material,
      'specification': spec,
      'area': area,
    });
    if (result.isSuccess) {
      _showSuccess('地面已添加');
      _loadDetails(_selectedSchemeId!);
    } else {
      _showError('添加失败：${result.error}');
    }
  }

  Future<void> _addWall(String room, String material, double area) async {
    if (_selectedSchemeId == null) return;
    final result = await _api.hardDecoAddWall(_selectedSchemeId!, {
      'room_name': room,
      'material': material,
      'area': area,
    });
    if (result.isSuccess) {
      _showSuccess('墙面已添加');
      _loadDetails(_selectedSchemeId!);
    } else {
      _showError('添加失败：${result.error}');
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

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _cardColor,
        foregroundColor: _primaryText,
        title: const Text('硬装设计'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '方案列表'),
            Tab(text: '地面'),
            Tab(text: '墙面'),
            Tab(text: '天花'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSchemesTab(),
          _buildFloorsTab(),
          _buildWallsTab(),
          _buildCeilingsTab(),
        ],
      ),
    );
  }

  // ── Tab1: 方案列表 ──

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
        icon: Icons.layers_outlined,
        message: '暂无硬装方案',
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
                Icon(Icons.layers,
                    color: isSelected ? _brandColor : _primaryText, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    scheme['name']?.toString() ?? '未命名方案',
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
                    _statusLabel(scheme['status']?.toString()),
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
                _buildInfoChip('风格', scheme['style']?.toString() ?? '未指定'),
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

  // ── Tab2: 地面 ──

  Widget _buildFloorsTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.grid_on_outlined,
        message: '请先在"方案列表"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return Column(
      children: [
        _buildCurrentSchemeBar(),
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
                  onPressed: _showAddFloorDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加地面'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: () => _loadDetails(_selectedSchemeId!),
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _detailsLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _floors.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.grid_on_outlined,
                      message: '暂无地面记录',
                      actionLabel: '添加地面',
                      onAction: _showAddFloorDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _floors.length,
                      itemBuilder: (context, index) {
                        final floor = _floors[index] as Map<String, dynamic>;
                        return _buildFloorCard(floor);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildFloorCard(Map<String, dynamic> floor) {
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
                const Icon(Icons.grid_on, color: _brandColor, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    floor['room_name']?.toString() ?? '未指定房间',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('材质', floor['material']?.toString() ?? '未指定'),
                _buildInfoChip(
                    '规格', floor['specification']?.toString() ?? '未指定'),
                _buildInfoChip(
                    '面积', '${floor['area'] ?? 0} ㎡'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab3: 墙面 ──

  Widget _buildWallsTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.view_quilt_outlined,
        message: '请先在"方案列表"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return Column(
      children: [
        _buildCurrentSchemeBar(),
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
                  onPressed: _showAddWallDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加墙面'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: () => _loadDetails(_selectedSchemeId!),
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _detailsLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _walls.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.view_quilt_outlined,
                      message: '暂无墙面记录',
                      actionLabel: '添加墙面',
                      onAction: _showAddWallDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _walls.length,
                      itemBuilder: (context, index) {
                        final wall = _walls[index] as Map<String, dynamic>;
                        return _buildWallCard(wall);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildWallCard(Map<String, dynamic> wall) {
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
                const Icon(Icons.view_quilt, color: _brandColor, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    wall['room_name']?.toString() ?? '未指定房间',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('材质', wall['material']?.toString() ?? '未指定'),
                _buildInfoChip('面积', '${wall['area'] ?? 0} ㎡'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab4: 天花 ──

  Widget _buildCeilingsTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.calendar_view_day_outlined,
        message: '请先在"方案列表"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return Column(
      children: [
        _buildCurrentSchemeBar(),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              style: OutlinedButton.styleFrom(
                foregroundColor: _primaryText,
                side: const BorderSide(color: _borderColor),
              ),
              onPressed: () => _loadDetails(_selectedSchemeId!),
              icon: const Icon(Icons.refresh),
              label: const Text('刷新'),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _detailsLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _ceilings.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.calendar_view_day_outlined,
                      message: '暂无天花记录',
                      actionLabel: '刷新',
                      onAction: () => _loadDetails(_selectedSchemeId!),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _ceilings.length,
                      itemBuilder: (context, index) {
                        final ceiling =
                            _ceilings[index] as Map<String, dynamic>;
                        return _buildCeilingCard(ceiling);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildCeilingCard(Map<String, dynamic> ceiling) {
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
                const Icon(Icons.calendar_view_day,
                    color: _brandColor, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    ceiling['room_name']?.toString() ?? '未指定房间',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
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
                    '造型', ceiling['shape']?.toString() ?? '未指定'),
                _buildInfoChip(
                    '材质', ceiling['material']?.toString() ?? '未指定'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── 通用组件 ──

  Widget _buildCurrentSchemeBar() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      child: Card(
        color: _cardColor,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              const Icon(Icons.layers, color: _brandColor, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '当前方案：${_selectedScheme?['name'] ?? _selectedSchemeId}',
                  style: const TextStyle(
                      color: _primaryText, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

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
    final styleCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('创建硬装方案',
            style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('方案名称'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: styleCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('风格（如：现代、北欧、新中式）'),
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
                _showError('请输入方案名称');
                return;
              }
              final style = styleCtrl.text.trim();
              Navigator.pop(ctx);
              _createScheme(name, style);
            },
            child: const Text('创建'),
          ),
        ],
      ),
    );
  }

  void _showAddFloorDialog() {
    final roomCtrl = TextEditingController();
    final materialCtrl = TextEditingController();
    final specCtrl = TextEditingController();
    final areaCtrl = TextEditingController(text: '0');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('添加地面',
            style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: roomCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('房间名称'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: materialCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('材质（如：实木、瓷砖、强化地板）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: specCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('规格（如：800×800mm）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: areaCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('面积（㎡）'),
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
              final room = roomCtrl.text.trim();
              if (room.isEmpty) {
                _showError('请输入房间名称');
                return;
              }
              final material = materialCtrl.text.trim();
              if (material.isEmpty) {
                _showError('请输入材质');
                return;
              }
              final spec = specCtrl.text.trim();
              final area = double.tryParse(areaCtrl.text.trim()) ?? 0.0;
              Navigator.pop(ctx);
              _addFloor(room, material, spec, area);
            },
            child: const Text('添加'),
          ),
        ],
      ),
    );
  }

  void _showAddWallDialog() {
    final roomCtrl = TextEditingController();
    final materialCtrl = TextEditingController();
    final areaCtrl = TextEditingController(text: '0');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title:
            const Text('添加墙面', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: roomCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('房间名称'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: materialCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('材质（如：乳胶漆、壁纸、瓷砖）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: areaCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('面积（㎡）'),
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
              final room = roomCtrl.text.trim();
              if (room.isEmpty) {
                _showError('请输入房间名称');
                return;
              }
              final material = materialCtrl.text.trim();
              if (material.isEmpty) {
                _showError('请输入材质');
                return;
              }
              final area = double.tryParse(areaCtrl.text.trim()) ?? 0.0;
              Navigator.pop(ctx);
              _addWall(room, material, area);
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
