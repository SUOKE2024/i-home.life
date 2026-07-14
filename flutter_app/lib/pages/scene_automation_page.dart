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

  static const _sceneIcons = {
    'wake_up': Icons.wb_sunny,
    'leave_home': Icons.directions_walk,
    'go_home': Icons.home,
    'sleep': Icons.nightlight,
    'movie': Icons.movie,
    'dinner': Icons.restaurant,
    'cleaning': Icons.cleaning_services,
    'security': Icons.security,
  };

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
    });
    final scenesResult = await _api.getList('/scene-automation/scenes/${widget.projectId}');
    if (scenesResult.isSuccess) _scenes = scenesResult.data;

    final ecoResult = await _api.getList('/scene-automation/ecosystems');
    if (ecoResult.isSuccess) _ecosystems = ecoResult.data;

    if (!scenesResult.isSuccess && !ecoResult.isSuccess) {
      _error = '加载场景数据失败';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _createScene() async {
    final scenes = ['wake_up', 'leave_home', 'go_home', 'sleep', 'movie', 'dinner'];
    final randomIndex = DateTime.now().millisecond % scenes.length;
    final result = await _api.post('/scene-automation/scenes', {
      'project_id': widget.projectId,
      'name': '智能场景',
      'scene_type': scenes[randomIndex],
    });
    if (result.isSuccess) {
      await _loadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('场景已创建')),
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
    final result = await _api.post('/scene-automation/scenes/$sceneId/simulate', {});
    if (result.isSuccess && mounted) {
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('场景模拟'),
          content: Text('模拟结果: ${result.data}'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭')),
          ],
        ),
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
          IconButton(icon: const Icon(Icons.add), onPressed: _createScene),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadData),
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
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _scenes.length,
      itemBuilder: (_, i) {
        final scene = _scenes[i];
        final type = scene['scene_type'] ?? '';
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: colors.primary.withValues(alpha: 0.1),
              child: Icon(
                _sceneIcons[type] ?? Icons.auto_awesome,
                color: colors.primary,
                size: 22,
              ),
            ),
            title: Text(scene['name'] ?? '未命名场景', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(type),
            trailing: IconButton(
              icon: Icon(Icons.play_circle_outline, color: colors.primary),
              onPressed: () => _simulateScene(scene['id']),
            ),
          ),
        );
      },
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
    if (_ecosystems.isEmpty) {
      return Center(child: Text('暂无生态对接', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _ecosystems.length,
      itemBuilder: (_, i) {
        final eco = _ecosystems[i];
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: Icon(Icons.link, color: colors.primary),
            title: Text(eco['name'] ?? '未命名', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(eco['type'] ?? ''),
            trailing: Chip(
              label: Text(eco['status'] ?? 'offline', style: const TextStyle(fontSize: 11)),
            ),
          ),
        );
      },
    );
  }
}
