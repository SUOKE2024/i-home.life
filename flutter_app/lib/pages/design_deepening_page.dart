// 索克家居
import 'package:flutter/material.dart';

import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 设计深化页面 — 平面方案管理（对接 /api/floorplans）
class DesignDeepeningPage extends StatefulWidget {
  final String projectId;
  const DesignDeepeningPage({super.key, required this.projectId});

  @override
  State<DesignDeepeningPage> createState() => _DesignDeepeningPageState();
}

class _DesignDeepeningPageState extends State<DesignDeepeningPage> {
  final ApiClient _api = ApiClient();

  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _plans = [];

  @override
  void initState() {
    super.initState();
    _loadPlans();
  }

  Future<void> _loadPlans() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.get('/floorplans/project/${widget.projectId}');
    if (!mounted) return;
    if (result.isSuccess) {
      final data = result.data;
      if (data is List) {
        setState(() {
          _plans = data.cast<Map<String, dynamic>>();
          _loading = false;
        });
      } else {
        setState(() {
          _plans = [];
          _loading = false;
        });
      }
    } else {
      setState(() {
        _error = result.error;
        _loading = false;
      });
    }
  }

  Future<void> _createPlan() async {
    final nameController = TextEditingController(text: '新方案');
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('新建方案'),
        content: TextField(
          controller: nameController,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: '输入方案名称',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('创建'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final result = await _api.post('/floorplans', {
      'project_id': widget.projectId,
      'name': nameController.text,
      'data': '{}',
    });
    if (!mounted) return;
    if (result.isSuccess) {
      _loadPlans();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('创建失败: ${result.error}')),
      );
    }
  }

  Future<void> _toggleActive(String planId, bool currentActive) async {
    final result = await _api.patch('/floorplans/$planId', {
      'is_active': !currentActive,
    });
    if (!mounted) return;
    if (result.isSuccess) {
      _loadPlans();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('操作失败: ${result.error}')),
      );
    }
  }

  Future<void> _deletePlan(String planId, String name) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认删除'),
        content: Text('确定要删除方案「$name」吗？此操作不可撤销。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (ok != true) return;

    final result = await _api.delete('/floorplans/$planId');
    if (!mounted) return;
    if (result.isSuccess) {
      _loadPlans();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('删除失败: ${result.error}')),
      );
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'active':
        return const Color(0xFF4A9E6E);
      case 'draft':
        return const Color(0xFFC9973B);
      default:
        return const Color(0xFF8A8894);
    }
  }

  Color _statusBg(String status) {
    switch (status) {
      case 'active':
        return const Color(0xFF4A9E6E).withValues(alpha: 0.15);
      case 'draft':
        return const Color(0xFFC9973B).withValues(alpha: 0.15);
      default:
        return const Color(0xFF8A8894).withValues(alpha: 0.15);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设计深化'),
        backgroundColor: const Color(0xFF12121D),
        foregroundColor: Colors.white,
      ),
      body: Container(
        color: const Color(0xFF0E0E1A),
        child: _buildBody(),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _createPlan,
        backgroundColor: const Color(0xFFC9973B),
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 160);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadPlans);
    }
    if (_plans.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.design_services_outlined, size: 48, color: Colors.white38),
            const SizedBox(height: 12),
            const Text('暂无设计方案', style: TextStyle(color: Color(0xFF8A8894))),
            const SizedBox(height: 8),
            const Text('点击右下角 + 新建方案',
                style: TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadPlans,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _plans.length,
        itemBuilder: (ctx, i) {
          final plan = _plans[i];
          final name = (plan['name'] ?? '未命名方案').toString();
          final area = (plan['total_area'] ?? 0.0).toDouble();
          final rooms = (plan['room_count'] ?? 0) as int;
          final height = (plan['wall_height'] ?? 2.8).toDouble();
          final createdAt = (plan['created_at'] ?? '').toString();
          final isActive = plan['is_active'] == true;
          final status = isActive ? 'active' : 'draft';

          return Card(
            color: const Color(0xFF1A1A2E),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(
                      child: Text(name,
                          style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 15)),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: _statusBg(status),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        isActive ? '激活' : '草稿',
                        style: TextStyle(color: _statusColor(status), fontSize: 11),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 8),
                  Row(children: [
                    _infoChip(Icons.square_foot, '${area.toStringAsFixed(1)} m²'),
                    const SizedBox(width: 12),
                    _infoChip(Icons.meeting_room, '$rooms 房间'),
                    const SizedBox(width: 12),
                    _infoChip(Icons.height, '层高 ${height.toStringAsFixed(1)}m'),
                  ]),
                  const SizedBox(height: 8),
                  Text(
                    _formatDate(createdAt),
                    style: const TextStyle(color: Color(0xFF6B6B80), fontSize: 11),
                  ),
                  const Divider(color: Color(0xFF2A2A3E), height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton.icon(
                        onPressed: () => _toggleActive(plan['id'], isActive),
                        icon: Icon(
                          isActive ? Icons.visibility_off : Icons.visibility,
                          size: 16,
                        ),
                        label: Text(isActive ? '停用' : '激活'),
                        style: TextButton.styleFrom(
                            foregroundColor: const Color(0xFFC9973B)),
                      ),
                      const SizedBox(width: 8),
                      TextButton.icon(
                        onPressed: () => _deletePlan(plan['id'], name),
                        icon: const Icon(Icons.delete_outline, size: 16),
                        label: const Text('删除'),
                        style: TextButton.styleFrom(
                            foregroundColor: const Color(0xFFE05555)),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _infoChip(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: const Color(0xFF8A8894)),
        const SizedBox(width: 4),
        Text(text, style: const TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
      ],
    );
  }

  String _formatDate(String iso) {
    try {
      final dt = DateTime.parse(iso);
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }
}
