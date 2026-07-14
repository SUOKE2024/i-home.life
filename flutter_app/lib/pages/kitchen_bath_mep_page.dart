import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 厨卫水电页面 (F18) — 给排水/燃气/回路/等电位
class KitchenBathMepPage extends StatefulWidget {
  final String projectId;
  const KitchenBathMepPage({super.key, required this.projectId});

  @override
  State<KitchenBathMepPage> createState() => _KitchenBathMepPageState();
}

class _KitchenBathMepPageState extends State<KitchenBathMepPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _plans = [];
  Map<String, dynamic>? _currentPlan;
  List<dynamic> _points = [];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _loadPlans();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadPlans() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.getList('/mep-kb/plans/${widget.projectId}');
    if (result.isSuccess) {
      _plans = result.data;
      if (_plans.isNotEmpty) {
        _currentPlan = _plans.first;
        await _loadPoints(_currentPlan!['id']);
      }
    } else {
      _error = '加载厨卫水电数据失败';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadPoints(String planId) async {
    final result = await _api.getList('/mep-kb/plans/$planId/points');
    if (result.isSuccess) {
      _points = result.data;
    }
  }

  Future<void> _createPlan() async {
    final result = await _api.post('/mep-kb/plans', {
      'project_id': widget.projectId,
      'name': '厨卫水电方案',
      'room_type': 'kitchen',
    });
    if (result.isSuccess) {
      await _loadPlans();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('方案已创建')),
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

  Future<void> _viewCompliance(String planId) async {
    final gasResult = await _api.get('/mep-kb/plans/$planId/gas');
    final circuitResult = await _api.get('/mep-kb/plans/$planId/circuits');
    final epResult = await _api.get('/mep-kb/plans/$planId/equipotential');
    if (mounted) {
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('合规检查'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                _section('燃气系统', gasResult.data),
                const Divider(),
                _section('电路回路', circuitResult.data),
                const Divider(),
                _section('等电位', epResult.data),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('关闭')),
          ],
        ),
      );
    }
  }

  Widget _section(String title, dynamic data) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
          const SizedBox(height: 4),
          Text(data is Map ? data.toString() : (data?.toString() ?? '无数据'),
              style: const TextStyle(fontSize: 13, color: Colors.grey)),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('厨卫水电'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '方案列表'),
            Tab(text: '水电点位'),
            Tab(text: '合规检查'),
            Tab(text: '燃气/等电位'),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.add), onPressed: _createPlan),
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadPlans),
        ],
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 3, itemHeight: 140)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadPlans)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildPlanList(colors),
                    _buildPointsList(colors),
                    _buildCompliancePanel(colors),
                    _buildGasEpPanel(colors),
                  ],
                ),
    );
  }

  Widget _buildPlanList(ColorScheme colors) {
    if (_plans.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.plumbing, size: 48, color: colors.onSurfaceVariant),
            const SizedBox(height: 12),
            Text('暂无厨卫水电方案', style: TextStyle(color: colors.onSurfaceVariant)),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _createPlan,
              icon: const Icon(Icons.add),
              label: const Text('新建方案'),
            ),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _plans.length,
      itemBuilder: (_, i) {
        final plan = _plans[i];
        final roomType = plan['room_type'] == 'kitchen' ? '厨房' : '卫生间';
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: Icon(
              plan['room_type'] == 'kitchen' ? Icons.kitchen : Icons.bathtub,
              color: colors.primary,
            ),
            title: Text(plan['name'] ?? '未命名方案', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('$roomType · ${plan['points_count'] ?? 0} 个点位'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () {
              setState(() => _currentPlan = plan);
              _loadPoints(plan['id']);
            },
          ),
        );
      },
    );
  }

  Widget _buildPointsList(ColorScheme colors) {
    if (_points.isEmpty) {
      return Center(child: Text('暂无水电点位', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _points.length,
      itemBuilder: (_, i) {
        final point = _points[i];
        final typeLabel = switch (point['type'] ?? '') {
          'water_supply' => '给水',
          'drain' => '排水',
          'power' => '电源',
          'gas' => '燃气',
          'vent' => '通风',
          _ => point['type'] ?? '',
        };
        return Card(
          margin: const EdgeInsets.only(bottom: 6),
          child: ListTile(
            dense: true,
            leading: Container(
              width: 36, height: 36,
              decoration: BoxDecoration(
                color: colors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.circle, size: 12, color: colors.primary),
            ),
            title: Text(point['name'] ?? '未命名点位'),
            subtitle: Text('$typeLabel · ${point['position_x'] ?? 0}, ${point['position_y'] ?? 0}'),
          ),
        );
      },
    );
  }

  Widget _buildCompliancePanel(ColorScheme colors) {
    if (_currentPlan == null) {
      return Center(child: Text('请先选择方案', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.verified, size: 48, color: Color(0xFF4CAF50)),
          const SizedBox(height: 16),
          Text('合规检查', textAlign: TextAlign.center,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colors.primary)),
          const SizedBox(height: 8),
          Text('检查厨卫水电方案的规范合规性，包括给排水间距、燃气管道安全距离、电路回路容量等',
              textAlign: TextAlign.center,
              style: TextStyle(color: colors.onSurfaceVariant, fontSize: 14)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => _viewCompliance(_currentPlan!['id']),
            icon: const Icon(Icons.checklist),
            label: const Text('执行合规检查'),
            style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
          ),
        ],
      ),
    );
  }

  Widget _buildGasEpPanel(ColorScheme colors) {
    if (_currentPlan == null) {
      return Center(child: Text('请先选择方案', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _infoCard('燃气系统', Icons.local_fire_department, '检查燃气管道布局、阀门位置、泄漏检测', colors),
        _infoCard('电路回路', Icons.electrical_services, '计算回路容量、分配电路负载、设置漏电保护', colors),
        _infoCard('等电位连接', Icons.shield, '检查等电位端子箱、接地电阻、防雷保护', colors),
        const SizedBox(height: 16),
        ElevatedButton.icon(
          onPressed: () => _viewCompliance(_currentPlan!['id']),
          icon: const Icon(Icons.fact_check_outlined),
          label: const Text('查看全部合规报告'),
          style: ElevatedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
        ),
      ],
    );
  }

  Widget _infoCard(String title, IconData icon, String desc, ColorScheme colors) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading: Icon(icon, color: colors.primary, size: 28),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(desc, style: TextStyle(color: colors.onSurfaceVariant, fontSize: 13)),
        trailing: const Icon(Icons.arrow_forward_ios, size: 14),
        onTap: () => _viewCompliance(_currentPlan!['id']),
      ),
    );
  }
}
