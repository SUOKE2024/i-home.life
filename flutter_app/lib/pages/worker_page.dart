import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 服务者匹配页面 (F35) — 设计师/监理/预算师
class WorkerPage extends StatefulWidget {
  final String projectId;
  const WorkerPage({super.key, required this.projectId});

  @override
  State<WorkerPage> createState() => _WorkerPageState();
}

class _WorkerPageState extends State<WorkerPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _workers = [];
  List<dynamic> _matches = [];
  bool _loading = false;
  String? _error;
  String _roleFilter = 'designer';

  static const _roleLabels = {
    'designer': '设计师',
    'supervisor': '监理',
    'estimator': '预算师',
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadWorkers();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadWorkers() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.getList('/workers?role=$_roleFilter');
    if (result.isSuccess) {
      _workers = result.data;
    } else {
      _error = '加载服务者数据失败';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadMatches() async {
    final result = await _api.getList('/workers/matches/${widget.projectId}');
    if (result.isSuccess) {
      _matches = result.data;
    }
  }

  Future<void> _matchWorker() async {
    final result = await _api.post('/workers/match', {
      'project_id': widget.projectId,
    });
    if (result.isSuccess) {
      await _loadMatches();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('匹配请求已发送')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('匹配失败：${result.error}')),
        );
      }
    }
  }

  Future<void> _updateMatchStatus(String matchId, String status) async {
    final result = await _api.patch('/workers/matches/$matchId/status', {'status': status});
    if (result.isSuccess) {
      await _loadMatches();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('更新失败：${result.error}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('服务者匹配'),
        bottom: TabBar(
          controller: _tabController,
          onTap: (i) {
            if (i == 0) _loadWorkers();
            if (i == 1) _loadMatches();
          },
          tabs: const [
            Tab(text: '服务者'),
            Tab(text: '匹配记录'),
            Tab(text: '智能匹配'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadWorkers),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 3, itemHeight: 160)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadWorkers)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildWorkerList(colors),
                    _buildMatchList(colors),
                    _buildMatchPanel(colors),
                  ],
                ),
    );
  }

  Widget _buildWorkerList(ColorScheme colors) {
    if (_workers.isEmpty) {
      return Center(child: Text('暂无服务者', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return Column(
      children: [
        _buildRoleFilter(colors),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: _workers.length,
            itemBuilder: (_, i) => _buildWorkerCard(_workers[i], colors),
          ),
        ),
      ],
    );
  }

  Widget _buildRoleFilter(ColorScheme colors) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: _roleLabels.entries.map((e) {
          final active = _roleFilter == e.key;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: ChoiceChip(
              label: Text(e.value, style: TextStyle(fontSize: 13, color: active ? Colors.white : colors.onSurfaceVariant)),
              selected: active,
              onSelected: (_) {
                setState(() => _roleFilter = e.key);
                _loadWorkers();
              },
              selectedColor: colors.primary,
              backgroundColor: colors.surfaceVariant,
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildWorkerCard(dynamic worker, ColorScheme colors) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: colors.primary.withValues(alpha: 0.1),
                  child: Icon(Icons.person, color: colors.primary, size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(worker['name'] ?? '未命名',
                          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                      Text(_roleLabels[worker['role']] ?? worker['role'] ?? '',
                          style: TextStyle(color: colors.onSurfaceVariant, fontSize: 12)),
                    ],
                  ),
                ),
                _buildRating(worker['rating'] ?? 0),
              ],
            ),
            const SizedBox(height: 10),
            _buildSixDimScore(worker, colors),
            if (worker['description'] != null) ...[
              const SizedBox(height: 8),
              Text(worker['description'].toString(),
                  maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSixDimScore(dynamic worker, ColorScheme colors) {
    final dims = [
      ('专业', worker['professional_score'] ?? 0),
      ('服务', worker['service_score'] ?? 0),
      ('沟通', worker['communication_score'] ?? 0),
      ('效率', worker['efficiency_score'] ?? 0),
      ('品控', worker['quality_score'] ?? 0),
      ('成本', worker['cost_score'] ?? 0),
    ];
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: dims.map((d) {
        final score = (d.$2 is num) ? (d.$2 as num).toDouble() : 0.0;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            color: const Color(0xFF1A1A2E),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${d.$1}: ', style: const TextStyle(fontSize: 11, color: Color(0xFFA0A0C0))),
              Text(score.toStringAsFixed(1),
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: score >= 4.5 ? Colors.green : score >= 3.5 ? Colors.orange : Colors.red,
                  )),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildMatchList(ColorScheme colors) {
    if (_matches.isEmpty) {
      return Center(child: Text('暂无匹配记录', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _matches.length,
      itemBuilder: (_, i) {
        final m = _matches[i];
        final status = m['status'] ?? 'pending';
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            title: Text(m['worker_name'] ?? '服务者', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('${_roleLabels[m['role']] ?? m['role']} · 评分: ${m['score'] ?? '-'}'),
            trailing: status == 'pending'
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      TextButton(onPressed: () => _updateMatchStatus(m['id'], 'accepted'), child: const Text('接受')),
                      TextButton(onPressed: () => _updateMatchStatus(m['id'], 'rejected'),
                          child: const Text('拒绝', style: TextStyle(color: Colors.red))),
                    ],
                  )
                : Chip(label: Text(status, style: const TextStyle(fontSize: 12))),
          ),
        );
      },
    );
  }

  Widget _buildMatchPanel(ColorScheme colors) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.people_alt_outlined, size: 48, color: Color(0xFF7C5CFC)),
          const SizedBox(height: 16),
          Text('智能匹配服务者',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colors.primary)),
          const SizedBox(height: 8),
          Text('根据项目需求和风格偏好，智能匹配设计师、监理和预算师',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.onSurfaceVariant, fontSize: 14)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _matchWorker,
            icon: const Icon(Icons.auto_awesome),
            label: const Text('开始匹配'),
            style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
          ),
        ],
      ),
    );
  }

  Widget _buildRating(dynamic rating) {
    final r = (rating is num) ? rating.toDouble() : 0.0;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(r.toStringAsFixed(1), style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        const SizedBox(width: 2),
        const Icon(Icons.star, size: 16, color: Color(0xFFFFB800)),
      ],
    );
  }
}
