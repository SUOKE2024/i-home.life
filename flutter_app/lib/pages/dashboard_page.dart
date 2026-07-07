import 'package:flutter/material.dart';
import '../services/api.dart';

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  int _projectCount = 0;
  int _inProgress = 0;
  double _totalArea = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final api = ApiClient();
      final projects = (await api.getList('/projects')) as List;
      setState(() {
        _projectCount = projects.length;
        _inProgress = projects.where((p) => p['status'] == 'in_progress').length;
        _totalArea = projects.fold<double>(0, (s, p) => s + ((p['total_area'] as num?)?.toDouble() ?? 0));
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('工作台', style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: false,
      ),
      body: RefreshIndicator(
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
                    Text('快速入口', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFFE8E6E1))),
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
      ),
    );
  }

  Widget _statCard(String label, String value, IconData icon) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, size: 18, color: const Color(0xFFC9973B)),
                  const SizedBox(width: 8),
                  Text(label, style: const TextStyle(color: Color(0xFF5A5866), fontSize: 11, letterSpacing: 1)),
                ],
              ),
              const SizedBox(height: 8),
              Text(value, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFFE8E6E1))),
            ],
          ),
        ),
      ),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String label;

  const _QuickAction({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 48, height: 48,
          decoration: BoxDecoration(
            color: const Color(0xFFC9973B).withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: const Color(0xFFC9973B), size: 22),
        ),
        const SizedBox(height: 6),
        Text(label, style: const TextStyle(fontSize: 11, color: Color(0xFF8A8894))),
      ],
    );
  }
}
