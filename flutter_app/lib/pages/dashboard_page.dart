import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  int _projectCount = 0;
  int _inProgress = 0;
  double _totalArea = 0;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final api = ApiClient();
    final result = await api.getList('/projects');
    if (result.isSuccess) {
      final projects = result.data as List;
      setState(() {
        _projectCount = projects.length;
        _inProgress = projects.where((p) => p['status'] == 'in_progress').length;
        _totalArea = projects.fold<double>(0, (s, p) => s + ((p['total_area'] as num?)?.toDouble() ?? 0));
        _loading = false;
      });
    } else {
      setState(() {
        _loading = false;
        _error = '加载失败，请检查网络后重试';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('工作台', style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: false,
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 100);
    }
    if (_error != null) {
      return ErrorRetryWidget(
        message: _error!,
        onRetry: _load,
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              _statCard('项目总数', '$_projectCount', Icons.home_work),
              const SizedBox(width: 12),
              _statCard('施工中', '$_inProgress', Icons.engineering),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _statCard('总面积', '${_totalArea.toStringAsFixed(0)}㎡', Icons.square_foot),
              const SizedBox(width: 12),
              _statCard('AI Agent', '6', Icons.smart_toy),
            ],
          ),
          const SizedBox(height: 24),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _QuickActionsTitle(),
                  SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _QuickAction(icon: Icons.design_services, label: '设计规划'),
                      _QuickAction(icon: Icons.account_balance_wallet, label: '预算管理'),
                      _QuickAction(icon: Icons.shopping_cart, label: '物料采购'),
                      _QuickAction(icon: Icons.build, label: '施工进度'),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _statCard(String label, String value, IconData icon) {
    final cs = Theme.of(context).colorScheme;
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, size: 18, color: SuokeDesignTokens.accent),
                  const SizedBox(width: 8),
                  Text(label, style: TextStyle(color: cs.onSurface.withValues(alpha: 0.45), fontSize: 11, letterSpacing: 1)),
                ],
              ),
              const SizedBox(height: 8),
              Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: cs.onSurface)),
            ],
          ),
        ),
      ),
    );
  }
}

class _QuickActionsTitle extends StatelessWidget {
  const _QuickActionsTitle();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Text('快速入口',
        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: cs.onSurface));
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;

  const _QuickAction({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Column(
      children: [
        Container(
          width: 48, height: 48,
          decoration: BoxDecoration(
            color: SuokeDesignTokens.accent.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: SuokeDesignTokens.accent, size: 22),
        ),
        const SizedBox(height: 6),
        Text(label, style: TextStyle(fontSize: 11, color: cs.onSurface.withValues(alpha: 0.5))),
      ],
    );
  }
}
