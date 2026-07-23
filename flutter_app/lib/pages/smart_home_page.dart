import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../widgets/floor_plan_canvas.dart';

class SmartHomePage extends StatefulWidget {
  final String projectId;
  const SmartHomePage({super.key, required this.projectId});

  @override
  State<SmartHomePage> createState() => _SmartHomePageState();
}

class _SmartHomePageState extends State<SmartHomePage>
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

  // 设备
  List<dynamic> _devices = [];
  bool _devicesLoading = false;

  // 场景
  List<dynamic> _scenes = [];
  bool _scenesLoading = false;

  // 生态系统
  List<dynamic> _ecosystems = [];

  // NL 解析结果
  Map<String, dynamic>? _parsedScene;
  bool _parsing = false;
  late final TextEditingController _nlController;

  // 户型部署
  String? _selectedFloorArea;
  bool _showAreaDeviceList = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
    _nlController = TextEditingController();
    _loadSchemes();
    _loadEcosystems();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _nlController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadSchemes() async {
    setState(() {
      _schemesLoading = true;
      _error = null;
    });
    final result = await _api.smartHomeListSchemes(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _schemes = _extractList(result.data, 'schemes');
      });
    } else {
      setState(() => _error = '加载失败，请检查网络后重试');
    }
    setState(() => _schemesLoading = false);
  }

  Future<void> _loadDevices(String schemeId) async {
    setState(() => _devicesLoading = true);
    final result = await _api.smartHomeListDevices(schemeId);
    if (result.isSuccess) {
      setState(() {
        _devices = _extractList(result.data, 'devices');
      });
    } else {
      _showError('加载设备失败：${result.error}');
    }
    setState(() => _devicesLoading = false);
  }

  Future<void> _loadScenes() async {
    setState(() => _scenesLoading = true);
    final result = await _api.sceneListScenes(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _scenes = _extractList(result.data, 'scenes');
      });
    } else {
      _showError('加载场景失败：${result.error}');
    }
    setState(() => _scenesLoading = false);
  }

  Future<void> _loadEcosystems() async {
    final result = await _api.sceneListEcosystems(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _ecosystems = _extractList(result.data, 'ecosystems');
      });
    }
  }

  List<dynamic> _extractList(dynamic data, String key) {
    if (data is List) return data;
    if (data is Map) return (data[key] as List?) ?? [];
    return [];
  }

  // ── 方案操作 ──

  Future<void> _createScheme(
      String name, String protocolType, String description) async {
    final result = await _api.smartHomeCreateScheme({
      'project_id': widget.projectId,
      'name': name,
      'protocol_type': protocolType,
      'description': description,
    });
    if (result.isSuccess) {
      _showSuccess('方案已创建');
      _loadSchemes();
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deleteScheme(String schemeId) async {
    final result = await _api.smartHomeDeleteScheme(schemeId);
    if (result.isSuccess) {
      _showSuccess('方案已删除');
      if (_selectedSchemeId == schemeId) {
        setState(() {
          _selectedSchemeId = null;
          _selectedScheme = null;
          _devices = [];
          _scenes = [];
        });
      }
      _loadSchemes();
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  Future<void> _autoRecommend(String schemeId) async {
    final result = await _api.smartHomeAutoRecommend(schemeId);
    if (result.isSuccess) {
      final data = result.data;
      final count = data is Map
          ? (data['recommended_count'] as int?) ?? 0
          : 0;
      _showSuccess('已推荐 $count 个设备');
      if (_selectedSchemeId == schemeId) {
        _loadDevices(schemeId);
      }
    } else {
      _showError('推荐失败：${result.error}');
    }
  }

  Future<void> _viewWiring(String schemeId) async {
    final result = await _api.smartHomeWiring(schemeId);
    if (result.isSuccess) {
      _showInfoDialog('接线图', _formatJson(result.data));
    } else {
      _showError('获取接线图失败：${result.error}');
    }
  }

  Future<void> _viewProtocol(String schemeId) async {
    final result = await _api.smartHomeProtocol(schemeId);
    if (result.isSuccess) {
      _showInfoDialog('协议信息', _formatJson(result.data));
    } else {
      _showError('获取协议失败：${result.error}');
    }
  }

  Future<void> _viewSchemeDetail(String schemeId) async {
    final result = await _api.smartHomeGetScheme(schemeId);
    if (result.isSuccess) {
      _showInfoDialog('方案详情', _formatJson(result.data));
    } else {
      _showError('获取详情失败：${result.error}');
    }
  }

  void _selectScheme(Map<String, dynamic> scheme) {
    final id = (scheme['id'] ?? '').toString();
    setState(() {
      _selectedSchemeId = id;
      _selectedScheme = scheme;
    });
    _loadDevices(id);
    _loadScenes();
    _tabController.animateTo(1);
    _showSuccess('已选择方案：${scheme['name'] ?? ''}');
  }

  // ── 设备操作 ──

  Future<void> _addDevice(
      String name, String type, String location) async {
    if (_selectedSchemeId == null) return;
    final result = await _api.smartHomeAddDevice(_selectedSchemeId!, {
      'name': name,
      'type': type,
      'location': location,
    });
    if (result.isSuccess) {
      _showSuccess('设备已添加');
      _loadDevices(_selectedSchemeId!);
    } else {
      _showError('添加失败：${result.error}');
    }
  }

  // ── 场景操作 ──

  Future<void> _createScene(
      String name, String trigger, String actions) async {
    if (_selectedSchemeId == null) return;
    dynamic triggerCond;
    dynamic actionsList;
    try {
      triggerCond = trigger.isEmpty ? null : jsonDecode(trigger);
    } catch (_) {
      _showError('触发条件 JSON 格式无效');
      return;
    }
    try {
      actionsList = actions.isEmpty ? null : jsonDecode(actions);
    } catch (_) {
      _showError('动作列表 JSON 格式无效');
      return;
    }
    final result = await _api.sceneCreateScene({
      'project_id': widget.projectId,
      'scheme_id': _selectedSchemeId,
      'scene_name': name,
      'trigger_condition': triggerCond,
      'actions': actionsList,
    });
    if (result.isSuccess) {
      _showSuccess('场景已创建');
      _loadScenes();
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deleteScene(String sceneId) async {
    final result = await _api.sceneDeleteScene(sceneId);
    if (result.isSuccess) {
      _showSuccess('场景已删除');
      _loadScenes();
    } else {
      _showError('删除失败：${result.error}');
    }
  }

  Future<void> _simulateScene(String sceneId) async {
    final result = await _api.sceneSimulate(sceneId);
    if (result.isSuccess) {
      _showInfoDialog('模拟结果', _formatJson(result.data));
    } else {
      _showError('模拟失败：${result.error}');
    }
  }

  Future<void> _validateScene(String sceneId) async {
    final result = await _api.sceneValidate(sceneId);
    if (result.isSuccess) {
      final data = result.data;
      final valid = (data is Map) ? data['valid'] : false;
      final errors = (data is Map) ? (data['errors'] as List?) ?? [] : [];
      final msg = valid ? '场景验证通过' : '验证未通过：${errors.join('; ')}';
      _showSuccess(msg);
    } else {
      _showError('验证失败：${result.error}');
    }
  }

  Future<void> _parseNl(String text) async {
    setState(() => _parsing = true);
    final result = await _api.sceneParseNl(text);
    if (result.isSuccess) {
      final data = result.data;
      setState(() {
        _parsedScene =
            data is Map ? Map<String, dynamic>.from(data) : null;
      });
      _showSuccess('解析成功，请确认后保存');
    } else {
      _showError('解析失败：${result.error}');
    }
    setState(() => _parsing = false);
  }

  Future<void> _saveParsedScene() async {
    if (_parsedScene == null || _selectedSchemeId == null) return;
    final body = Map<String, dynamic>.from(_parsedScene!);
    body['project_id'] = widget.projectId;
    body['scheme_id'] = _selectedSchemeId;
    final result = await _api.sceneCreateScene(body);
    if (result.isSuccess) {
      _showSuccess('场景已保存');
      setState(() => _parsedScene = null);
      _loadScenes();
    } else {
      _showError('保存失败：${result.error}');
    }
  }

  // ── 工具方法 ──

  String _formatJson(dynamic data) {
    try {
      return const JsonEncoder.withIndent('  ').convert(data);
    } catch (_) {
      return data.toString();
    }
  }

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

  void _showInfoDialog(String title, String content) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: Text(title, style: const TextStyle(color: _primaryText)),
        content: SizedBox(
          width: double.maxFinite,
          child: SingleChildScrollView(
            child: SelectableText(
              content,
              style: const TextStyle(
                  color: _secondaryText, fontFamily: 'monospace', fontSize: 13),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('关闭', style: TextStyle(color: _brandColor)),
          ),
        ],
      ),
    );
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _cardColor,
        foregroundColor: _primaryText,
        title: const Text('智能家居管理'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brandColor,
          unselectedLabelColor: _secondaryText,
          indicatorColor: _brandColor,
          tabs: const [
            Tab(text: '智能方案'),
            Tab(text: '设备管理'),
            Tab(text: '场景自动化'),
            Tab(text: '户型部署'),
            Tab(text: '设备布局图'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSchemesTab(),
          _buildDevicesTab(),
          _buildScenesTab(),
          _buildFloorPlanTab(),
          _buildDeviceCanvasTab(),
        ],
      ),
    );
  }

  // ── Tab1: 智能方案 ──

  Widget _buildSchemesTab() {
    if (_schemesLoading) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 90);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadSchemes);
    }
    if (_schemes.isEmpty) {
      return _buildEmptyState(
        icon: Icons.home_outlined,
        message: '暂无智能方案',
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
                Icon(Icons.home,
                    color: isSelected ? _brandColor : _primaryText, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    scheme['name'] ?? '未命名方案',
                    style: const TextStyle(
                        color: _primaryText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                if (isSelected)
                  const Icon(Icons.check_circle,
                      color: _brandColor, size: 18),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip(
                    '协议', scheme['protocol_type'] ?? '-'),
                _buildInfoChip(
                    '设备数', '${scheme['device_count'] ?? 0}'),
                _buildInfoChip(
                    '创建时间', _formatTime(scheme['created_at'])),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildActionButton(
                  '详情',
                  Icons.info_outline,
                  () => _viewSchemeDetail(id),
                ),
                _buildActionButton(
                  '选为当前',
                  Icons.check,
                  () => _selectScheme(scheme),
                ),
                _buildActionButton(
                  '自动推荐',
                  Icons.auto_awesome,
                  () => _autoRecommend(id),
                ),
                _buildActionButton(
                  '接线图',
                  Icons.electrical_services,
                  () => _viewWiring(id),
                ),
                _buildActionButton(
                  '协议',
                  Icons.settings_ethernet,
                  () => _viewProtocol(id),
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

  // ── Tab2: 设备管理 ──

  Widget _buildDevicesTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.devices_other,
        message: '请先在"智能方案"中选择一个方案',
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
                  const Icon(Icons.home, color: _brandColor, size: 20),
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
                  onPressed: _showAddDeviceDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('添加设备'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: () => _loadDevices(_selectedSchemeId!),
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: _devicesLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _devices.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.devices,
                      message: '暂无设备',
                      actionLabel: '添加设备',
                      onAction: _showAddDeviceDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _devices.length,
                      itemBuilder: (context, index) {
                        final device =
                            _devices[index] as Map<String, dynamic>;
                        return _buildDeviceCard(device);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildDeviceCard(Map<String, dynamic> device) {
    final status = device['status'] ?? 'offline';
    final isOnline = status == 'online' || status == true;
    return Card(
      color: _cardColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: _borderColor, width: 1),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding: const EdgeInsets.all(14),
        leading: CircleAvatar(
          backgroundColor: _bgColor,
          child: Icon(Icons.devices_other, color: _brandColor, size: 22),
        ),
        title: Text(
          device['name'] ?? '未命名设备',
          style: const TextStyle(
              color: _primaryText, fontWeight: FontWeight.w600),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('类型：${device['type'] ?? '-'}',
                  style: const TextStyle(color: _secondaryText, fontSize: 13)),
              const SizedBox(height: 2),
              Text('位置：${device['location'] ?? '-'}',
                  style: const TextStyle(color: _secondaryText, fontSize: 13)),
            ],
          ),
        ),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: isOnline
                ? Colors.green.withValues(alpha: 0.15)
                : Colors.grey.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            isOnline ? '在线' : '离线',
            style: TextStyle(
              color: isOnline ? Colors.green : _secondaryText,
              fontSize: 12,
            ),
          ),
        ),
      ),
    );
  }

  // ── Tab3: 场景自动化 ──

  Widget _buildScenesTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.dashboard_customize,
        message: '请先在"智能方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }
    return DefaultTabController(
      length: 2,
      child: Column(
        children: [
          TabBar(
            labelColor: _brandColor,
            unselectedLabelColor: _secondaryText,
            indicatorColor: _brandColor,
            tabs: const [
              Tab(text: '场景列表'),
              Tab(text: '自然语言解析'),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                _buildSceneList(),
                _buildNlParseView(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSceneList() {
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
                  onPressed: _showCreateSceneDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建场景'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: _primaryText,
                  side: const BorderSide(color: _borderColor),
                ),
                onPressed: () => _loadScenes(),
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: _scenesLoading
              ? const Center(
                  child: CircularProgressIndicator(color: _brandColor))
              : _scenes.isEmpty
                  ? _buildEmptyState(
                      icon: Icons.movie_filter_outlined,
                      message: '暂无场景',
                      actionLabel: '创建场景',
                      onAction: _showCreateSceneDialog,
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: _scenes.length,
                      itemBuilder: (context, index) {
                        final scene =
                            _scenes[index] as Map<String, dynamic>;
                        return _buildSceneCard(scene);
                      },
                    ),
        ),
      ],
    );
  }

  Widget _buildSceneCard(Map<String, dynamic> scene) {
    final id = (scene['id'] ?? '').toString();
    final enabled = scene['enabled'] ?? scene['is_enabled'] ?? false;
    final actions = scene['actions'];
    String actionsText;
    if (actions is List) {
      actionsText = actions.map((a) {
        if (a is Map) return a['name'] ?? a.toString();
        return a.toString();
      }).join('、');
    } else {
      actionsText = actions?.toString() ?? '-';
    }
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
                Icon(Icons.movie_filter,
                    color: enabled ? _brandColor : _secondaryText, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    scene['name'] ?? '未命名场景',
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
                    color: enabled
                        ? _brandColor.withValues(alpha: 0.15)
                        : Colors.grey.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    enabled ? '已启用' : '已禁用',
                    style: TextStyle(
                      color: enabled ? _brandColor : _secondaryText,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text('触发条件：${scene['trigger_condition'] ?? '-'}',
                style: const TextStyle(color: _secondaryText, fontSize: 13)),
            const SizedBox(height: 4),
            Text('动作：$actionsText',
                style: const TextStyle(color: _secondaryText, fontSize: 13)),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildActionButton(
                  '模拟',
                  Icons.play_arrow,
                  () => _simulateScene(id),
                ),
                _buildActionButton(
                  '验证',
                  Icons.check_circle_outline,
                  () => _validateScene(id),
                ),
                _buildActionButton(
                  '删除',
                  Icons.delete_outline,
                  () => _confirmDeleteScene(id),
                  isDanger: true,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNlParseView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '自然语言解析场景',
            style: TextStyle(
                color: _primaryText,
                fontSize: 18,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          const Text(
            '输入一段自然语言描述，系统将自动解析为场景配置。',
            style: TextStyle(color: _secondaryText, fontSize: 13),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _nlController,
            maxLines: 4,
            style: const TextStyle(color: _primaryText),
            decoration: InputDecoration(
              hintText: '例如：每天早上7点打开客厅灯光，关闭卧室窗帘',
              hintStyle: const TextStyle(color: _secondaryText),
              filled: true,
              fillColor: _cardColor,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: _borderColor),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: _borderColor),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: _brandColor),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: _brandColor,
                foregroundColor: _bgColor,
              ),
              onPressed: _parsing
                  ? null
                  : () {
                      final text = _nlController.text.trim();
                      if (text.isEmpty) {
                        _showError('请输入描述文本');
                        return;
                      }
                      _parseNl(text);
                    },
              icon: _parsing
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: _bgColor),
                    )
                  : const Icon(Icons.auto_fix_high),
              label: Text(_parsing ? '解析中...' : '解析'),
            ),
          ),
          if (_parsedScene != null) ...[
            const SizedBox(height: 24),
            const Text(
              '解析结果预览',
              style: TextStyle(
                  color: _brandColor,
                  fontSize: 16,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Card(
              color: _cardColor,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: const BorderSide(color: _borderColor),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: SelectableText(
                  _formatJson(_parsedScene),
                  style: const TextStyle(
                      color: _secondaryText,
                      fontFamily: 'monospace',
                      fontSize: 13),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _brandColor,
                      foregroundColor: _bgColor,
                    ),
                    onPressed: _saveParsedScene,
                    icon: const Icon(Icons.save),
                    label: const Text('保存为场景'),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _primaryText,
                    side: const BorderSide(color: _borderColor),
                  ),
                  onPressed: () =>
                      setState(() => _parsedScene = null),
                  icon: const Icon(Icons.close),
                  label: const Text('取消'),
                ),
              ],
            ),
          ],
          if (_ecosystems.isNotEmpty) ...[
            const SizedBox(height: 24),
            const Text(
              '支持的生态系统',
              style: TextStyle(
                  color: _primaryText,
                  fontSize: 16,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _ecosystems.map((e) {
                final name = (e is Map) ? (e['name'] ?? e.toString()) : e.toString();
                return Chip(
                  label: Text(name,
                      style: const TextStyle(color: _primaryText)),
                  backgroundColor: _cardColor,
                  side: const BorderSide(color: _borderColor),
                );
              }).toList(),
            ),
          ],
        ],
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

  String _formatTime(dynamic value) {
    if (value == null) return '-';
    final str = value.toString();
    if (str.length >= 10) return str.substring(0, 10);
    return str;
  }

  // ── 对话框 ──

  void _showCreateSchemeDialog() {
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    String protocol = 'Zigbee';
    const protocols = [
      'Zigbee',
      'Z-Wave',
      'Wi-Fi',
      'Bluetooth',
      'Matter',
      'Thread',
      'RF'
    ];
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          backgroundColor: _cardColor,
          title: const Text('创建智能方案',
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
                DropdownButtonFormField<String>(
                  initialValue: protocol,
                  dropdownColor: _cardColor,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('协议类型'),
                  items: protocols
                      .map((p) => DropdownMenuItem(
                          value: p,
                          child: Text(p,
                              style:
                                  const TextStyle(color: _primaryText))))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setState(() => protocol = v);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descCtrl,
                  maxLines: 3,
                  style: const TextStyle(color: _primaryText),
                  decoration: _inputDecoration('方案描述'),
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
                Navigator.pop(ctx);
                _createScheme(name, protocol, descCtrl.text.trim());
              },
              child: const Text('创建'),
            ),
          ],
        ),
      ),
    );
  }

  void _showAddDeviceDialog() {
    final nameCtrl = TextEditingController();
    final typeCtrl = TextEditingController();
    final locationCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title:
            const Text('添加设备', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('设备名称'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: typeCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration(
                    '设备类型（如：灯、窗帘、传感器）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: locationCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('安装位置（如：客厅、卧室）'),
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
                _showError('请输入设备名称');
                return;
              }
              Navigator.pop(ctx);
              _addDevice(name, typeCtrl.text.trim(),
                  locationCtrl.text.trim());
            },
            child: const Text('添加'),
          ),
        ],
      ),
    );
  }

  void _showCreateSceneDialog() {
    final nameCtrl = TextEditingController();
    final triggerCtrl = TextEditingController();
    final actionsCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title:
            const Text('创建场景', style: TextStyle(color: _primaryText)),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration('场景名称'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: triggerCtrl,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration(
                    '触发条件（如：每天 07:00）'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: actionsCtrl,
                maxLines: 3,
                style: const TextStyle(color: _primaryText),
                decoration: _inputDecoration(
                    '动作列表（每行一个动作）'),
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
                _showError('请输入场景名称');
                return;
              }
              Navigator.pop(ctx);
              _createScene(name, triggerCtrl.text.trim(),
                  actionsCtrl.text.trim());
            },
            child: const Text('创建'),
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

  void _confirmDeleteScene(String sceneId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: const Text('确认删除',
            style: TextStyle(color: _primaryText)),
        content: const Text('确定要删除此场景吗？',
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
              _deleteScene(sceneId);
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

  // ═══════════════════════════════════════════
  // Tab4: 户型部署
  // ═══════════════════════════════════════════

  static const Map<String, _FloorAreaDef> _floorAreas = {
    'entry': _FloorAreaDef('玄关', Icons.door_front_door, Rect.fromLTWH(20, 280, 100, 60)),
    'living': _FloorAreaDef('客厅', Icons.weekend, Rect.fromLTWH(140, 140, 180, 200)),
    'bedroom': _FloorAreaDef('卧室', Icons.bed, Rect.fromLTWH(20, 20, 160, 240)),
    'kitchen': _FloorAreaDef('厨房', Icons.countertops, Rect.fromLTWH(200, 20, 120, 100)),
    'bathroom': _FloorAreaDef('卫生间', Icons.bathtub, Rect.fromLTWH(260, 140, 60, 120)),
  };

  Widget _buildFloorPlanTab() {
    if (_selectedSchemeId == null || _devices.isEmpty) {
      return _buildEmptyState(
        icon: Icons.architecture,
        message: '请先选择方案并加载设备',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }

    final areaDevices = _groupDevicesByArea();

    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          child: Card(
            color: _cardColor,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.architecture, color: _brandColor, size: 20),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      '户型设备部署图',
                      style: TextStyle(color: _primaryText, fontWeight: FontWeight.w600, fontSize: 16),
                    ),
                  ),
                  Text(
                    '${_devices.length} 个设备',
                    style: const TextStyle(color: _secondaryText, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
        ),
        Expanded(
          child: _showAreaDeviceList && _selectedFloorArea != null
              ? _buildAreaDeviceList(areaDevices, _selectedFloorArea!)
              : _buildFloorPlanCanvas(areaDevices),
        ),
      ],
    );
  }

  Widget _buildFloorPlanCanvas(Map<String, List<Map<String, dynamic>>> areaDevices) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Center(
        child: RepaintBoundary(
          child: GestureDetector(
            onTapUp: (details) => _handleFloorTap(details.localPosition, areaDevices),
            child: CustomPaint(
              size: const Size(340, 380),
              painter: _FloorPlanPainter(
                areas: _floorAreas,
                brandColor: _brandColor,
                cardColor: _cardColor,
                bgColor: _bgColor,
                borderColor: _borderColor,
                primaryText: _primaryText,
                secondaryText: _secondaryText,
                areaDevices: areaDevices,
                selectedArea: _selectedFloorArea,
              ),
              child: SizedBox(
                width: 340,
                height: 380,
                child: CustomMultiChildLayout(
                  delegate: _FloorLabelDelegate(_floorAreas),
                  children: _buildFloorLabels(areaDevices),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAreaDeviceList(
      Map<String, List<Map<String, dynamic>>> areaDevices, String areaKey) {
    final def = _floorAreas[areaKey]!;
    final devices = areaDevices[areaKey] ?? [];
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          color: _bgColor,
          child: Row(
            children: [
              GestureDetector(
                onTap: () => setState(() {
                  _showAreaDeviceList = false;
                  _selectedFloorArea = null;
                }),
                child: const Icon(Icons.arrow_back, color: _brandColor, size: 22),
              ),
              const SizedBox(width: 8),
              Icon(def.icon, color: _brandColor, size: 20),
              const SizedBox(width: 6),
              Text(
                '${def.name} · ${devices.length} 个设备',
                style: const TextStyle(color: _primaryText, fontSize: 16, fontWeight: FontWeight.w600),
              ),
            ],
          ),
        ),
        const Divider(color: _borderColor, height: 1),
        Expanded(
          child: devices.isEmpty
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.devices_other, size: 48, color: _secondaryText),
                      const SizedBox(height: 12),
                      const Text('该区域暂无设备', style: TextStyle(color: _secondaryText, fontSize: 15)),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _brandColor,
                          foregroundColor: _bgColor,
                        ),
                        onPressed: () {
                          setState(() {
                            _showAreaDeviceList = false;
                            _selectedFloorArea = null;
                          });
                          _showAddDeviceDialog();
                        },
                        icon: const Icon(Icons.add, size: 18),
                        label: const Text('添加设备'),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: devices.length,
                  itemBuilder: (context, index) {
                    final device = devices[index];
                    return _buildFloorDeviceCard(device);
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildFloorDeviceCard(Map<String, dynamic> device) {
    final status = device['status'] ?? 'offline';
    final isOnline = status == 'online' || status == true;
    final type = (device['type'] ?? '').toString();
    final IconData icon = _deviceIcon(type);

    return GestureDetector(
      onLongPress: () => _showDeviceDetail(device),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: _cardColor,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: _borderColor),
        ),
        child: Row(
          children: [
            Container(
              width: 40, height: 40,
              decoration: BoxDecoration(
                color: _bgColor,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(icon, color: _brandColor, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    device['name'] ?? '未命名设备',
                    style: const TextStyle(color: _primaryText, fontWeight: FontWeight.w600, fontSize: 14),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '类型：$type',
                    style: const TextStyle(color: _secondaryText, fontSize: 12),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: isOnline ? Colors.green.withValues(alpha: 0.15) : Colors.grey.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                isOnline ? '在线' : '离线',
                style: TextStyle(color: isOnline ? Colors.green : _secondaryText, fontSize: 12),
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right, color: _secondaryText, size: 18),
          ],
        ),
      ),
    );
  }

  void _showDeviceDetail(Map<String, dynamic> device) {
    final status = device['status'] ?? 'offline';
    final isOnline = status == 'online' || status == true;
    final type = (device['type'] ?? '-').toString();
    final name = (device['name'] ?? '未命名设备').toString();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: Row(
          children: [
            Icon(_deviceIcon(type), color: _brandColor, size: 24),
            const SizedBox(width: 8),
            Expanded(
              child: Text(name, style: const TextStyle(color: _primaryText, fontSize: 16)),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _detailRow('类型', type),
            _detailRow('位置', (device['location'] ?? '-').toString()),
            _detailRow('状态', isOnline ? '在线' : '离线'),
            _detailRow('协议', (device['protocol'] ?? '-').toString()),
            if (device['model'] != null) _detailRow('型号', device['model'].toString()),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('关闭', style: TextStyle(color: _secondaryText)),
          ),
        ],
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 60,
            child: Text(label, style: const TextStyle(color: _secondaryText, fontSize: 13)),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(color: _primaryText, fontSize: 13)),
          ),
        ],
      ),
    );
  }

  Map<String, List<Map<String, dynamic>>> _groupDevicesByArea() {
    final Map<String, List<Map<String, dynamic>>> grouped = {};
    for (final key in _floorAreas.keys) {
      grouped[key] = <Map<String, dynamic>>[];
    }
    for (final device in _devices) {
      if (device is! Map<String, dynamic>) continue;
      final location = (device['location'] ?? '').toString();
      final areaKey = _matchArea(location);
      grouped[areaKey]?.add(device);
    }
    return grouped;
  }

  String _matchArea(String location) {
    final lower = location.toLowerCase();
    if (lower.contains('玄关') || lower.contains('entry')) return 'entry';
    if (lower.contains('客厅') || lower.contains('living')) return 'living';
    if (lower.contains('卧室') || lower.contains('bed')) return 'bedroom';
    if (lower.contains('厨房') || lower.contains('kitchen')) return 'kitchen';
    if (lower.contains('卫生') || lower.contains('浴') || lower.contains('bath')) return 'bathroom';
    return 'living'; // default to living room
  }

  void _handleFloorTap(Offset pos, Map<String, List<Map<String, dynamic>>> areaDevices) {
    for (final entry in _floorAreas.entries) {
      if (entry.value.rect.contains(pos)) {
        setState(() {
          _selectedFloorArea = entry.key;
          _showAreaDeviceList = true;
        });
        return;
      }
    }
  }

  List<Widget> _buildFloorLabels(Map<String, List<Map<String, dynamic>>> areaDevices) {
    return _floorAreas.entries.map((entry) {
      final key = entry.key;
      final def = entry.value;
      final count = (areaDevices[key]?.length ?? 0);
      return LayoutId(
        id: key,
        child: IgnorePointer(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(def.icon, size: 14, color: _primaryText.withValues(alpha: 0.7)),
              const SizedBox(width: 2),
              Text(def.name, style: const TextStyle(color: _primaryText, fontSize: 10)),
              if (count > 0) ...[
                const SizedBox(width: 4),
                Container(
                  width: 18, height: 18,
                  decoration: BoxDecoration(
                    color: _brandColor,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: Text(
                      '$count',
                      style: const TextStyle(color: Colors.black, fontSize: 10, fontWeight: FontWeight.w700),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      );
    }).toList();
  }

  IconData _deviceIcon(String type) {
    switch (type) {
      case '灯':
      case '灯光':
      case 'light':
        return Icons.lightbulb_outline;
      case '窗帘':
      case 'curtain':
        return Icons.vertical_shades;
      case '门锁':
      case 'lock':
        return Icons.lock_outline;
      case '传感器':
      case 'sensor':
        return Icons.sensors;
      case '空调':
      case 'ac':
        return Icons.ac_unit;
      case '电视':
      case 'tv':
        return Icons.tv;
      case '音响':
      case 'speaker':
        return Icons.speaker;
      default:
        return Icons.devices_other;
    }
  }

  // ═══════════════════════════════════════════
  // Tab5: 设备布局图 (FloorPlanCanvas)
  // ═══════════════════════════════════════════

  /// 设备类型 -> 分类颜色
  Color _deviceCategoryColor(String type) {
    final t = type.toLowerCase();
    if (t.contains('灯') || t.contains('light') || t.contains('照明')) {
      return Colors.amber;
    }
    if (t.contains('锁') || t.contains('lock') ||
        t.contains('传感器') || t.contains('sensor') ||
        t.contains('报警') || t.contains('alarm') ||
        t.contains('摄像头') || t.contains('camera')) {
      return Colors.red;
    }
    if (t.contains('空调') || t.contains('ac') ||
        t.contains('窗帘') || t.contains('curtain') ||
        t.contains('温控') || t.contains('thermostat') ||
        t.contains('风扇') || t.contains('fan')) {
      return Colors.blue;
    }
    if (t.contains('电视') || t.contains('tv') ||
        t.contains('音响') || t.contains('speaker') ||
        t.contains('投影') || t.contains('projector')) {
      return Colors.purple;
    }
    return Colors.green;
  }

  String _deviceCategoryLabel(String type) {
    final t = type.toLowerCase();
    if (t.contains('灯') || t.contains('light') || t.contains('照明')) return '照明';
    if (t.contains('锁') || t.contains('lock') ||
        t.contains('传感器') || t.contains('sensor') ||
        t.contains('报警') || t.contains('alarm') ||
        t.contains('摄像头') || t.contains('camera')) return '安防';
    if (t.contains('空调') || t.contains('ac') ||
        t.contains('窗帘') || t.contains('curtain') ||
        t.contains('温控') || t.contains('thermostat') ||
        t.contains('风扇') || t.contains('fan')) return '气候';
    if (t.contains('电视') || t.contains('tv') ||
        t.contains('音响') || t.contains('speaker') ||
        t.contains('投影') || t.contains('projector')) return '娱乐';
    return '家电';
  }

  Widget _buildDeviceCanvasTab() {
    if (_selectedSchemeId == null) {
      return _buildEmptyState(
        icon: Icons.dashboard_customize,
        message: '请先在"智能方案"中选择一个方案',
        actionLabel: '去选择方案',
        onAction: () => _tabController.animateTo(0),
      );
    }

    if (_devicesLoading) {
      return const Center(
          child: CircularProgressIndicator(color: _brandColor));
    }

    if (_devices.isEmpty) {
      return _buildEmptyState(
        icon: Icons.devices_other,
        message: '暂无设备，请先添加设备',
        actionLabel: '去添加设备',
        onAction: () => _tabController.animateTo(1),
      );
    }

    const double roomW = 8000;
    const double roomH = 6000;

    final areaPositions = {
      'entry': Offset(roomW * 0.70, roomH * 0.80),
      'living': Offset(roomW * 0.40, roomH * 0.40),
      'bedroom': Offset(roomW * 0.08, roomH * 0.20),
      'kitchen': Offset(roomW * 0.55, roomH * 0.12),
      'bathroom': Offset(roomW * 0.75, roomH * 0.20),
    };

    final List<FloorPlanComponent> components = [];
    final areaCounts = <String, int>{};

    for (int i = 0; i < _devices.length; i++) {
      final device = _devices[i] as Map<String, dynamic>;
      final location = (device['location'] ?? '').toString();
      final areaKey = _matchArea(location);
      final deviceType = (device['type'] ?? '').toString();
      final deviceName = (device['name'] ?? '').toString();
      final color = _deviceCategoryColor(deviceType);

      final basePos = areaPositions[areaKey]!;
      final count = areaCounts[areaKey] ?? 0;
      areaCounts[areaKey] = count + 1;

      final offsetX = (count % 3) * 250.0;
      final offsetY = (count ~/ 3) * 250.0;
      final px = basePos.dx + offsetX;
      final py = basePos.dy + offsetY;

      components.add(FloorPlanComponent(
        id: (device['id'] ?? 'device_$i').toString(),
        label: deviceName.isNotEmpty ? deviceName : deviceType,
        type: deviceType,
        x: px,
        y: py,
        width: 300,
        height: 200,
        color: color,
      ));
    }

    final Map<String, int> categoryCounts = {};
    for (final device in _devices) {
      final dt = (device as Map<String, dynamic>)['type']?.toString() ?? '';
      final label = _deviceCategoryLabel(dt);
      categoryCounts[label] = (categoryCounts[label] ?? 0) + 1;
    }

    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Card(
            color: _cardColor,
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10)),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.dashboard_customize,
                          color: _brandColor, size: 20),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '方案：${_selectedScheme?['name'] ?? _selectedSchemeId}',
                          style: const TextStyle(
                              color: _primaryText,
                              fontWeight: FontWeight.w600),
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: _brandColor,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          '${_devices.length} 台设备',
                          style: const TextStyle(
                              color: Colors.black,
                              fontSize: 12,
                              fontWeight: FontWeight.w700),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 12,
                    runSpacing: 4,
                    children: categoryCounts.entries.map((e) {
                      return _buildCategoryBadge(
                          e.key, e.value, _categoryLegendColor(e.key));
                    }).toList(),
                  ),
                  const SizedBox(height: 8),
                  const Divider(height: 1, color: _borderColor),
                  const SizedBox(height: 6),
                  Wrap(
                    spacing: 12,
                    runSpacing: 4,
                    children: [
                      _buildDeviceLegend(Colors.amber, '照明'),
                      _buildDeviceLegend(Colors.red, '安防'),
                      _buildDeviceLegend(Colors.blue, '气候'),
                      _buildDeviceLegend(Colors.purple, '娱乐'),
                      _buildDeviceLegend(Colors.green, '家电'),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: FloorPlanCanvas(
              roomWidth: roomW,
              roomHeight: roomH,
              roomLabel:
                  '${_selectedScheme?['name'] ?? '智能方案'} · 设备布局',
              showDimensions: true,
              showGrid: true,
              showMEPLayer: false,
              components: components,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCategoryBadge(String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 4),
          Text(
            '$label ×$count',
            style: TextStyle(
                color: color, fontSize: 12, fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }

  Widget _buildDeviceLegend(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 14,
          height: 10,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(label,
            style: const TextStyle(color: _secondaryText, fontSize: 11)),
      ],
    );
  }

  Color _categoryLegendColor(String category) {
    switch (category) {
      case '照明':
        return Colors.amber;
      case '安防':
        return Colors.red;
      case '气候':
        return Colors.blue;
      case '娱乐':
        return Colors.purple;
      case '家电':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }
}

/// 户型区域定义
class _FloorAreaDef {
  final String name;
  final IconData icon;
  final Rect rect;
  const _FloorAreaDef(this.name, this.icon, this.rect);
}

/// 户型图绘制器
class _FloorPlanPainter extends CustomPainter {
  final Map<String, _FloorAreaDef> areas;
  final Color brandColor;
  final Color cardColor;
  final Color bgColor;
  final Color borderColor;
  final Color primaryText;
  final Color secondaryText;
  final Map<String, List<Map<String, dynamic>>> areaDevices;
  final String? selectedArea;

  _FloorPlanPainter({
    required this.areas,
    required this.brandColor,
    required this.cardColor,
    required this.bgColor,
    required this.borderColor,
    required this.primaryText,
    required this.secondaryText,
    required this.areaDevices,
    this.selectedArea,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final bgPaint = Paint()..color = bgColor;
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(0, 0, size.width, size.height), const Radius.circular(16)),
      bgPaint,
    );

    final borderPaint = Paint()
      ..color = borderColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(0, 0, size.width, size.height), const Radius.circular(16)),
      borderPaint,
    );

    for (final entry in areas.entries) {
      final key = entry.key;
      final def = entry.value;
      final r = def.rect;
      final isSelected = selectedArea == key;
      final hasDevices = (areaDevices[key]?.isNotEmpty ?? false);

      // Fill
      final fillPaint = Paint()
        ..color = isSelected
            ? brandColor.withValues(alpha: 0.12)
            : hasDevices
                ? cardColor
                : cardColor.withValues(alpha: 0.4);
      canvas.drawRRect(
        RRect.fromRectAndRadius(r, const Radius.circular(8)),
        fillPaint,
      );

      // Border
      final areaBorder = Paint()
        ..color = isSelected ? brandColor : borderColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = isSelected ? 2.0 : 1.0;
      canvas.drawRRect(
        RRect.fromRectAndRadius(r, const Radius.circular(8)),
        areaBorder,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _FloorPlanPainter oldDelegate) {
    return selectedArea != oldDelegate.selectedArea || areaDevices != oldDelegate.areaDevices;
  }
}

/// 户型图标签订位代理
class _FloorLabelDelegate extends MultiChildLayoutDelegate {
  final Map<String, _FloorAreaDef> areas;

  _FloorLabelDelegate(this.areas);

  @override
  void performLayout(Size size) {
    for (final entry in areas.entries) {
      final key = entry.key;
      final def = entry.value;
      if (hasChild(key)) {
        final childSize = layoutChild(
          key,
          BoxConstraints.loose(Size(def.rect.width - 8, def.rect.height - 8)),
        );
        final cx = def.rect.center.dx - childSize.width / 2;
        final cy = def.rect.center.dy - childSize.height / 2;
        positionChild(key, Offset(cx.clamp(0, size.width - childSize.width), cy.clamp(0, size.height - childSize.height)));
      }
    }
  }

  @override
  bool shouldRelayout(covariant _FloorLabelDelegate oldDelegate) => false;
}
