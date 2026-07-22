import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../theme/suoke_theme.dart';

class ConstructionPage extends StatefulWidget {
  final String projectId;
  const ConstructionPage({super.key, required this.projectId});

  @override
  State<ConstructionPage> createState() => _ConstructionPageState();
}

class _ConstructionPageState extends State<ConstructionPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();
  List<dynamic> _tasks = [];
  Map<String, dynamic>? _plan;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadTasks();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadTasks() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.getList('/construction/tasks/${widget.projectId}');
    if (result.isSuccess) {
      setState(() => _tasks = result.data);
    } else {
      setState(() => _error = '施工任务加载失败，请检查网络后重试');
    }
    setState(() => _loading = false);
  }

  Future<void> _generatePlan() async {
    final result = await _api.post('/construction/plan', {'total_area': 126.0, 'tier': 'comfort'});
    if (result.isSuccess) {
      setState(() => _plan = result.data);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('生成失败：${result.error}')));
      }
    }
  }

  Future<void> _updateTaskStatus(String taskId, String status) async {
    final result = await _api.patch('/construction/tasks/$taskId/status', {'status': status});
    if (result.isSuccess) {
      await _loadTasks();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('更新失败：${result.error}')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('施工管理'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '任务列表'),
            Tab(text: '施工计划'),
            Tab(text: '质检清单'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildTasksView(),
          _buildPlanView(),
          _buildQualityView(),
        ],
      ),
    );
  }

  Widget _buildTasksView() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 4, itemHeight: 90);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadTasks);
    }
    if (_tasks.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.engineering, size: 64, color: SuokeDesignTokens.textSecondary),
            const SizedBox(height: 16),
            const Text('暂无施工任务', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _loadTasks,
              icon: const Icon(Icons.refresh),
              label: const Text('刷新'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadTasks,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _tasks.length,
        itemBuilder: (context, index) {
          final task = _tasks[index] as Map<String, dynamic>;
          final status = task['status'] as String? ?? 'pending';
          final statusColor = {
            'pending': SuokeDesignTokens.textSecondary,
            'in_progress': Colors.blue,
            'completed': Colors.green,
            'delayed': Colors.red,
          }[status] ?? SuokeDesignTokens.textSecondary;

          return Card(
            child: ExpansionTile(
              leading: CircleAvatar(
                backgroundColor: statusColor,
                child: Text('${task['priority'] ?? 0}', style: const TextStyle(color: Colors.white)),
              ),
              title: Text(task['name'] ?? ''),
              subtitle: Text('${task['phase'] ?? ''} · $status'),
              trailing: PopupMenuButton<String>(
                onSelected: (value) => _updateTaskStatus(task['id'], value),
                itemBuilder: (_) => [
                  const PopupMenuItem(value: 'pending', child: Text('待开始')),
                  const PopupMenuItem(value: 'in_progress', child: Text('进行中')),
                  const PopupMenuItem(value: 'completed', child: Text('已完成')),
                  const PopupMenuItem(value: 'delayed', child: Text('已延期')),
                ],
              ),
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (task['description'] != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: Text(task['description']),
                        ),
                      if (task['assigned_to'] != null)
                        Text('负责人：${task['assigned_to']}', style: const TextStyle(color: SuokeDesignTokens.textSecondary)),
                      if (task['start_date'] != null)
                        Text('开始：${task['start_date']}', style: const TextStyle(color: SuokeDesignTokens.textSecondary)),
                      if (task['end_date'] != null)
                        Text('结束：${task['end_date']}', style: const TextStyle(color: SuokeDesignTokens.textSecondary)),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildPlanView() {
    if (_plan == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.schedule, size: 64, color: SuokeDesignTokens.textSecondary),
            const SizedBox(height: 16),
            const Text('生成施工 Gantt 排期', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _generatePlan,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('生成施工计划'),
            ),
          ],
        ),
      );
    }
    final tasks = (_plan!['tasks'] as List?) ?? [];
    final milestones = (_plan!['milestones'] as List?) ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          color: Colors.blue.shade50,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Text('总工期：${_plan!['total_duration_days']} 天',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('面积：${_plan!['total_area']}㎡ · 档次：${_plan!['tier']}',
                    style: const TextStyle(color: SuokeDesignTokens.textSecondary)),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        const Text('施工阶段', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...tasks.map((task) => RepaintBoundary(
              child: Card(
                child: ListTile(
                  leading: CircleAvatar(child: Text('${task['start_day']}-\n${task['end_day']}', style: const TextStyle(fontSize: 10))),
                  title: Text(task['name'] ?? ''),
                  subtitle: Text('${task['duration_days']}天 · ${task['description'] ?? ''}'),
                ),
              ),
            )),
        const SizedBox(height: 16),
        const Text('里程碑节点', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...milestones.map((m) => RepaintBoundary(
              child: Card(
                color: Colors.amber.shade50,
                child: ListTile(
                  leading: const Icon(Icons.flag, color: Colors.amber),
                  title: Text(m['name'] ?? ''),
                  trailing: Text('第 ${m['day']} 天'),
                ),
              ),
            )),
      ],
    );
  }

  Widget _buildQualityView() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('AI 质检', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        Card(
          child: ListTile(
            leading: const Icon(Icons.water_damage, color: Colors.blue),
            title: const Text('水电阶段质检'),
            subtitle: const Text('5 项检查点'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showChecklist('mep'),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.construction, color: Colors.orange),
            title: const Text('泥瓦阶段质检'),
            subtitle: const Text('5 项检查点'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showChecklist('masonry'),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.handyman, color: Colors.brown),
            title: const Text('木工阶段质检'),
            subtitle: const Text('4 项检查点'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showChecklist('carpentry'),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.format_paint, color: Colors.purple),
            title: const Text('油漆阶段质检'),
            subtitle: const Text('4 项检查点'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showChecklist('painting'),
          ),
        ),
        Card(
          child: ListTile(
            leading: const Icon(Icons.build, color: Colors.teal),
            title: const Text('安装阶段质检'),
            subtitle: const Text('4 项检查点'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showChecklist('installation'),
          ),
        ),
        const SizedBox(height: 24),
        ElevatedButton.icon(
          onPressed: _runAiInspection,
          icon: const Icon(Icons.camera_alt),
          label: const Text('启动 AI 图像质检'),
        ),
      ],
    );
  }

  Future<void> _showChecklist(String phase) async {
    final result = await _api.get('/construction/quality-checklist/$phase');
    if (result.isSuccess) {
      final data = result.data;
      if (mounted) {
        final checklist = (data['checklist'] as List?) ?? [];
        showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: Text('${data['reply']}'),
            content: SizedBox(
              width: double.maxFinite,
              child: ListView.builder(
                shrinkWrap: true,
                itemCount: checklist.length,
                itemBuilder: (_, i) {
                  final item = checklist[i] as Map<String, dynamic>;
                  return ListTile(
                    leading: const Icon(Icons.check_circle_outline),
                    title: Text(item['item'] ?? ''),
                    subtitle: Text('标准：${item['standard']}'),
                  );
                },
              ),
            ),
            actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭'))],
          ),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('加载失败：${result.error}')));
      }
    }
  }

  Future<void> _runAiInspection() async {
    final result = await _api.post('/construction/inspections/analyze', {
      'phase': 'masonry',
      'images': [{'url': 'mock://tile.jpg', 'type': 'tile_surface'}],
    });
    if (result.isSuccess) {
      final data = result.data;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(data['reply'] ?? 'AI 质检完成')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('质检失败：${result.error}')));
      }
    }
  }
}
