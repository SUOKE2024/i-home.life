import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 场景编辑页面 (F32) — 联动触发/场景模拟/NL 解析/生态对接
class SceneAutomationPage extends StatefulWidget {
  final String projectId;
  const SceneAutomationPage({super.key, required this.projectId});

  @override
  State<SceneAutomationPage> createState() => _SceneAutomationPageState();
}

class _SceneAutomationPageState extends State<SceneAutomationPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _scenes = [];
  List<dynamic> _ecosystems = [];
  bool _loading = false;
  String? _error;
  String? _ecosystemError;

  // scene_type 合法语义（后端 app/schemas/scene_automation.py）：
  // manual / scheduled / triggered / geo —— 「起床/睡眠」等语义属于 scene_name，
  // 触发方式属于 scene_type，「何时触发」属于 trigger_condition.type。
  static const _sceneTypeIcons = {
    'manual': Icons.touch_app,
    'scheduled': Icons.schedule,
    'triggered': Icons.sensors,
    'geo': Icons.location_on,
  };

  static const _sceneTypeLabels = {
    'manual': '手动触发',
    'scheduled': '定时触发',
    'triggered': '条件触发',
    'geo': '位置触发',
  };

  static const _ecoAuthLabels = {
    'connected': '已连接',
    'disconnected': '未连接',
  };

  /// 快捷创建预设（对齐后端 LIFESTYLE_SCENE_PRESETS 口径：
  /// 起床/睡眠=定时，回家/离家=设备条件触发，观影=手动）
  static const _scenePresets = <Map<String, dynamic>>[
    {
      'scene_name': '起床模式',
      'scene_type': 'scheduled',
      'trigger_condition': {'type': 'time', 'cron': '0 7 * * *'},
    },
    {
      'scene_name': '睡眠模式',
      'scene_type': 'scheduled',
      'trigger_condition': {'type': 'time', 'cron': '0 23 * * *'},
    },
    {
      'scene_name': '离家模式',
      'scene_type': 'triggered',
      'trigger_condition': {'type': 'device', 'device_id': 'lock', 'state': 'lock'},
    },
    {
      'scene_name': '回家模式',
      'scene_type': 'triggered',
      'trigger_condition': {'type': 'device', 'device_id': 'lock', 'state': 'unlock'},
    },
    {
      'scene_name': '观影模式',
      'scene_type': 'manual',
    },
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _loading = true;
      _error = null;
      _ecosystemError = null;
    });
    // 契约：GET /scene-automation/scenes/project/{id}、/ecosystems/project/{id}
    final scenesResult = await _api.sceneListScenes(widget.projectId);
    final ecoResult = await _api.sceneListEcosystems(widget.projectId);
    if (!mounted) return;
    setState(() {
      if (scenesResult.isSuccess) {
        _scenes = _asList(scenesResult.data);
      } else {
        // 诚实错误态：失败不再伪装成「暂无场景」空列表
        _scenes = [];
        _error = '加载场景失败：${scenesResult.error}';
      }
      if (ecoResult.isSuccess) {
        _ecosystems = _asList(ecoResult.data);
      } else {
        _ecosystems = [];
        _ecosystemError = '加载生态对接失败：${ecoResult.error}';
      }
      _loading = false;
    });
  }

  List<dynamic> _asList(dynamic data) => data is List ? data : <dynamic>[];

  Future<void> _createScene() async {
    final preset = _scenePresets[DateTime.now().millisecond % _scenePresets.length];
    final result = await _api.sceneCreateScene({
      'project_id': widget.projectId,
      'scene_name': preset['scene_name'],
      'scene_type': preset['scene_type'],
      if (preset['trigger_condition'] != null)
        'trigger_condition': preset['trigger_condition'],
    });
    if (result.isSuccess) {
      await _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('场景已创建：${preset['scene_name']}')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('创建失败：${result.error}')),
        );
      }
    }
  }

  Future<void> _simulateScene(String sceneId) async {
    final result = await _api.sceneSimulate(sceneId);
    if (result.isSuccess && mounted) {
      unawaited(showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('场景模拟'),
          content: Text('模拟结果: ${result.data}'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭')),
          ],
        ),
      ));
    } else if (!result.isSuccess && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('模拟失败：${result.error}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('场景编辑'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '场景列表'),
            Tab(text: '触发联动'),
            Tab(text: '生态对接'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: _createScene, tooltip: '新建场景'),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData, tooltip: '刷新'),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 3, itemHeight: 140)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadData)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildSceneList(colors),
                    _buildTriggerPanel(colors),
                    _buildEcosystemPanel(colors),
                  ],
                ),
    );
  }

  Widget _buildSceneList(ColorScheme colors) {
    if (_scenes.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_awesome, size: 48, color: colors.onSurfaceVariant),
            const SizedBox(height: 12),
            Text('暂无场景', style: TextStyle(color: colors.onSurfaceVariant)),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _createScene,
              icon: const Icon(Icons.add),
              label: const Text('创建场景'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(12),
        itemCount: _scenes.length,
        itemBuilder: (_, i) {
          final scene = _scenes[i];
          final type = (scene is Map ? scene['scene_type'] : null)?.toString() ?? '';
          final name = (scene is Map ? scene['scene_name'] : null)?.toString();
          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: colors.primary.withValues(alpha: 0.1),
                child: Icon(
                  _sceneTypeIcons[type] ?? Icons.auto_awesome,
                  color: colors.primary,
                  size: 22,
                ),
              ),
              title: Text(
                (name == null || name.isEmpty) ? '未命名场景' : name,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              subtitle: Text(_sceneTypeLabels[type] ?? type),
              trailing: IconButton(
                icon: Icon(Icons.play_circle_outline, color: colors.primary),
                onPressed: () => _simulateScene((scene['id'] ?? '').toString()),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildTriggerPanel(ColorScheme colors) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.link, size: 48, color: Color(0xFF7C5CFC)),
          const SizedBox(height: 16),
          Text('触发联动配置', textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colors.primary)),
          const SizedBox(height: 8),
          Text('配置场景的触发条件和联动动作，支持时间触发、传感器触发和手动触发',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.onSurfaceVariant, fontSize: 14)),
          const SizedBox(height: 20),
          _triggerCard('时间触发', Icons.schedule, '按时间表自动执行场景', colors),
          _triggerCard('传感器触发', Icons.sensors, '根据光照/温度/人体感应触发', colors),
          _triggerCard('语音触发', Icons.mic, '通过语音助手触发场景', colors),
          _triggerCard('位置触发', Icons.location_on, '基于地理围栏自动触发', colors),
        ],
      ),
    );
  }

  Widget _triggerCard(String title, IconData icon, String desc, ColorScheme colors) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: SwitchListTile(
        secondary: Icon(icon, color: colors.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(desc, style: TextStyle(color: colors.onSurfaceVariant, fontSize: 12)),
        value: false,
        onChanged: (_) {},
      ),
    );
  }

  Widget _buildEcosystemPanel(ColorScheme colors) {
    // 加载失败：诚实错误态 + 重试，而非伪装「暂无生态对接」
    if (_ecosystemError != null) {
      return ErrorRetryWidget(message: _ecosystemError!, onRetry: _loadData);
    }
    if (_ecosystems.isEmpty) {
      return Center(child: Text('暂无生态对接', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(12),
        itemCount: _ecosystems.length,
        itemBuilder: (_, i) {
          final eco = _ecosystems[i];
          if (eco is! Map) return const SizedBox.shrink();
          // 契约字段（EcosystemIntegrationResponse）：
          // ecosystem / auth_status / device_count，无 name / type / status
          final ecosystem = (eco['ecosystem'] ?? '').toString();
          final authStatus = (eco['auth_status'] ?? '').toString();
          final deviceCount = eco['device_count'] ?? 0;
          final authLabel = _ecoAuthLabels[authStatus] ?? authStatus;
          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: Icon(Icons.link, color: colors.primary),
              title: Text(
                ecosystem.isEmpty ? '未命名生态' : ecosystem,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              subtitle: Text('授权状态：${authLabel.isEmpty ? '未知' : authLabel} · 已接入 $deviceCount 台设备'),
              trailing: Chip(
                label: Text(
                  (authStatus.isEmpty ? 'unknown' : authStatus),
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
