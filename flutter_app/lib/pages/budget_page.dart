import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class BudgetPage extends StatefulWidget {
  final String projectId;
  const BudgetPage({super.key, required this.projectId});

  @override
  State<BudgetPage> createState() => _BudgetPageState();
}

class _BudgetPageState extends State<BudgetPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();
  Map<String, dynamic>? _budget;
  Map<String, dynamic>? _compareResult;
  List<dynamic> _templates = [];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadBudget();
    _loadTemplates();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadBudget() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.get('/budgets/project/${widget.projectId}');
    if (result.isSuccess) {
      setState(() => _budget = result.data);
    } else {
      // 区分 404（预算尚未创建）与真实加载错误
      if (result.statusCode == 404) {
        setState(() => _budget = null);
      } else {
        setState(() => _error = '预算加载失败，请检查网络后重试');
      }
    }
    setState(() => _loading = false);
  }

  Future<void> _loadTemplates() async {
    final result = await _api.get('/budgets/templates');
    if (result.isSuccess) {
      final data = result.data;
      setState(() => _templates = (data['templates'] as List?) ?? []);
    }
  }

  Future<void> _generateFromBom() async {
    setState(() => _loading = true);
    final result = await _api.post('/budgets/generate-from-bom/${widget.projectId}', {});
    if (result.isSuccess) {
      final data = result.data;
      setState(() => _budget = data);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已从 BOM 生成预算，总价 ¥${(data['total_estimated'] as num?)?.toDouble() ?? 0}')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('生成失败：${result.error}')));
      }
    }
    setState(() => _loading = false);
  }

  Future<void> _comparePlans() async {
    final result = await _api.post('/budgets/compare-plans', {'message': '126㎡'});
    if (result.isSuccess) {
      setState(() => _compareResult = result.data);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('对比失败：${result.error}')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('预算管理'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '当前预算'),
            Tab(text: '方案对比'),
            Tab(text: '模板库'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildCurrentBudget(),
          _buildCompareView(),
          _buildTemplatesView(),
        ],
      ),
    );
  }

  Widget _buildCurrentBudget() {
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadBudget);
    }
    if (_budget == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.account_balance_wallet, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            const Text('暂无预算', style: TextStyle(fontSize: 16, color: Colors.grey)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _generateFromBom,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('从 BOM 生成预算'),
            ),
          ],
        ),
      );
    }
    final totalEstimated = (_budget!['total_estimated'] as num?)?.toDouble() ?? 0;
    final totalActual = (_budget!['total_actual'] as num?)?.toDouble() ?? 0;
    final variance = totalActual - totalEstimated;
    final variancePct = totalEstimated > 0 ? (variance / totalEstimated * 100).toStringAsFixed(2) : '0.00';
    final lines = (_budget!['lines'] as List?) ?? [];

    return RefreshIndicator(
      onRefresh: _loadBudget,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('预算总额', style: TextStyle(fontSize: 14, color: Colors.grey)),
                      Text('¥${totalEstimated.toStringAsFixed(2)}',
                          style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const Divider(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('实际支出'),
                      Text('¥${totalActual.toStringAsFixed(2)}',
                          style: TextStyle(color: variance > 0 ? Colors.red : Colors.green)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('偏差'),
                      Text('$variancePct%',
                          style: TextStyle(
                              color: variance.abs() > totalEstimated * 0.05 ? Colors.red : Colors.green,
                              fontWeight: FontWeight.bold)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          const Text('分项明细', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          ...lines.map((line) => Card(
                child: ListTile(
                  title: Text(line['name'] ?? ''),
                  subtitle: Text(line['category'] ?? ''),
                  trailing: Text('¥${(line['estimated_amount'] as num?)?.toDouble().toStringAsFixed(2) ?? '0.00'}'),
                ),
              )),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _comparePlans,
                  icon: const Icon(Icons.compare_arrows),
                  label: const Text('生成三档对比'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _loadBudget,
                  icon: const Icon(Icons.refresh),
                  label: const Text('刷新'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCompareView() {
    if (_compareResult == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.compare, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            const Text('点击下方生成三档预算对比', style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _comparePlans,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('生成对比'),
            ),
          ],
        ),
      );
    }
    final plans = (_compareResult!['plans'] as List?) ?? [];
    final differences = _compareResult!['differences'] as Map<String, dynamic>?;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('面积：${_compareResult!['area']}㎡',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 16),
        ...plans.map((plan) => Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(plan['tier_name'],
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        Text('¥${(plan['total_estimated'] as num?)?.toDouble().toStringAsFixed(0)}',
                            style: const TextStyle(fontSize: 20, color: Colors.blue)),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text('价格区间：¥${(plan['total_range'] as List?)?[0]} ~ ¥${(plan['total_range'] as List?)?[1]}',
                        style: const TextStyle(color: Colors.grey, fontSize: 12)),
                    const SizedBox(height: 12),
                    ...(plan['breakdown'] as Map<String, dynamic>?)?.entries.map((e) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(e.key),
                              Text('¥${(e.value as num).toDouble().toStringAsFixed(0)}'),
                            ],
                          ),
                        )) ??
                        [],
                  ],
                ),
              ),
            )),
        if (differences != null) ...[
          const SizedBox(height: 16),
          Card(
            color: Colors.orange.shade50,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('档位差异', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text('经济型→舒适型：+¥${(differences['economy_to_comfort'] as num?)?.toDouble().toStringAsFixed(0) ?? '0'}'),
                  Text('舒适型→品质型：+¥${(differences['comfort_to_premium'] as num?)?.toDouble().toStringAsFixed(0) ?? '0'}'),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 16),
        Text(_compareResult!['recommendation'] ?? '',
            style: const TextStyle(color: Colors.blue, fontStyle: FontStyle.italic)),
      ],
    );
  }

  Widget _buildTemplatesView() {
    if (_templates.isEmpty) {
      return const Center(child: Text('暂无模板'));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _templates.length,
      itemBuilder: (context, index) {
        final tpl = _templates[index] as Map<String, dynamic>;
        return Card(
          child: ListTile(
            leading: const Icon(Icons.description, color: Colors.blue),
            title: Text(tpl['name'] ?? ''),
            subtitle: Text(
                '${tpl['area']}㎡ · ${tpl['tier']} · ${tpl['style']} · ${tpl['line_count']} 项'),
            trailing: Text('¥${(tpl['total_range'] as List?)?[0]} ~ ${(tpl['total_range'] as List?)?[1]}'),
            onTap: () => _applyTemplate(tpl['code'] as String),
          ),
        );
      },
    );
  }

  Future<void> _applyTemplate(String code) async {
    final result = await _api.post('/budgets/templates/apply', {'template_code': code});
    if (result.isSuccess) {
      final data = result.data;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(data['reply'] ?? '已应用模板')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('应用失败：${result.error}')));
      }
    }
  }
}
