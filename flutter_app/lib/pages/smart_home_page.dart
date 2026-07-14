import 'dart:convert';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

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

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
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

  Future<void> _loadScenes(String schemeId) async {
    setState(() => _scenesLoading = true);
    final result = await _api.sceneListScenes(schemeId);
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
    final result = await _api.sceneListEcosystems();
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
    _loadScenes(id);
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
    final result = await _api.sceneCreateScene({
      'scheme_id': _selectedSchemeId,
      'name': name,
      'trigger_condition': trigger,
      'actions': actions,
    });
    if (result.isSuccess) {
      _showSuccess('场景已创建');
      _loadScenes(_selectedSchemeId!);
    } else {
      _showError('创建失败：${result.error}');
    }
  }

  Future<void> _deleteScene(String sceneId) async {
    final result = await _api.sceneDeleteScene(sceneId);
    if (result.isSuccess) {
      _showSuccess('场景已删除');
      if (_selectedSchemeId != null) {
        _loadScenes(_selectedSchemeId!);
      }
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
      final reason = (data is Map) ? (data['reason'] ?? '') : '';
      _showSuccess(valid ? '场景验证通过' : '验证未通过：$reason');
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
    body['scheme_id'] = _selectedSchemeId;
    final result = await _api.sceneCreateScene(body);
    if (result.isSuccess) {
      _showSuccess('场景已保存');
      setState(() => _parsedScene = null);
      _loadScenes(_selectedSchemeId!);
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
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSchemesTab(),
          _buildDevicesTab(),
          _buildScenesTab(),
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
                onPressed: () => _loadScenes(_selectedSchemeId!),
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
}
