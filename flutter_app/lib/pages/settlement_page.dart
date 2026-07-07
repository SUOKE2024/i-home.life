import 'package:flutter/material.dart';
import '../services/api.dart';

class SettlementPage extends StatefulWidget {
  final String projectId;
  const SettlementPage({super.key, required this.projectId});

  @override
  State<SettlementPage> createState() => _SettlementPageState();
}

class _SettlementPageState extends State<SettlementPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();
  Map<String, dynamic>? _settlement;
  List<dynamic> _milestones = [];
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadSettlement();
    _loadMilestones();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadSettlement() async {
    setState(() => _loading = true);
    try {
      final data = await _api.get('/settlements/project/${widget.projectId}');
      setState(() => _settlement = data);
    } catch (_) {}
    finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadMilestones() async {
    try {
      final data = await _api.get('/settlements/milestones');
      setState(() => _milestones = (data['milestones'] as List?) ?? []);
    } catch (_) {}
  }

  Future<void> _generateFromBudget() async {
    setState(() => _loading = true);
    try {
      final data = await _api.post('/settlements/generate-from-budget/${widget.projectId}', {});
      setState(() => _settlement = data);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已生成结算单，应付 ¥${(data['total_amount'] as num?)?.toDouble() ?? 0}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('生成失败：$e')));
      }
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _confirmSettlement() async {
    try {
      final data = await _api.post('/settlements/confirm/${widget.projectId}', {});
      setState(() => _settlement = data);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('结算单已确认')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('确认失败：$e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('结算管理'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: '结算单'),
            Tab(text: '里程碑'),
            Tab(text: '异常检测'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildSettlementView(),
          _buildMilestonesView(),
          _buildAnomalyView(),
        ],
      ),
    );
  }

  Widget _buildSettlementView() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_settlement == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.receipt_long, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            const Text('暂无结算单', style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _generateFromBudget,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('从预算生成结算'),
            ),
          ],
        ),
      );
    }
    final totalAmount = (_settlement!['total_amount'] as num?)?.toDouble() ?? 0;
    final status = _settlement!['status'] as String? ?? 'draft';
    final lines = (_settlement!['lines'] as List?) ?? [];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          color: Colors.green.shade50,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('应付总额', style: TextStyle(fontSize: 14, color: Colors.grey)),
                    Text('¥${totalAmount.toStringAsFixed(2)}',
                        style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.green)),
                  ],
                ),
                const Divider(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('状态'),
                    _buildStatusChip(status),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        const Text('结算明细', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        ...lines.map((line) => Card(
              child: ListTile(
                title: Text(line['name'] ?? ''),
                subtitle: Text(line['milestone'] ?? ''),
                trailing: Text('¥${(line['amount'] as num?)?.toDouble().toStringAsFixed(2) ?? '0.00'}'),
              ),
            )),
        const SizedBox(height: 16),
        if (status == 'draft')
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: _confirmSettlement,
                  icon: const Icon(Icons.check_circle),
                  label: const Text('确认结算'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _loadSettlement,
                  icon: const Icon(Icons.refresh),
                  label: const Text('刷新'),
                ),
              ),
            ],
          ),
      ],
    );
  }

  Widget _buildStatusChip(String status) {
    final (label, color) = switch (status) {
      'draft' => ('草稿', Colors.grey),
      'confirmed' => ('已确认', Colors.blue),
      'paid' => ('已支付', Colors.green),
      'completed' => ('已完成', Colors.teal),
      _ => (status, Colors.grey),
    };
    return Chip(label: Text(label), backgroundColor: color.withValues(alpha: 0.2));
  }

  Widget _buildMilestonesView() {
    if (_milestones.isEmpty) {
      return const Center(child: Text('暂无里程碑'));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _milestones.length,
      itemBuilder: (context, index) {
        final m = _milestones[index] as Map<String, dynamic>;
        final ratio = (m['payment_ratio'] as num?)?.toDouble() ?? 0;
        return Card(
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: Colors.amber,
              child: Text('${(ratio * 100).toInt()}%', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
            title: Text(m['name'] ?? ''),
            subtitle: Text(m['description'] ?? ''),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => _showMilestoneDetail(m),
          ),
        );
      },
    );
  }

  Future<void> _showMilestoneDetail(Map<String, dynamic> milestone) async {
    final contractCtrl = TextEditingController(text: '200000');
    final changeCtrl = TextEditingController(text: '0');
    final deductionCtrl = TextEditingController(text: '0');
    final paidCtrl = TextEditingController(text: '0');

    await showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('生成「${milestone['name']}」结算'),
        content: SizedBox(
          width: 300,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: contractCtrl,
                decoration: const InputDecoration(labelText: '合同金额'),
                keyboardType: TextInputType.number,
              ),
              TextField(
                controller: changeCtrl,
                decoration: const InputDecoration(labelText: '变更金额'),
                keyboardType: TextInputType.number,
              ),
              TextField(
                controller: deductionCtrl,
                decoration: const InputDecoration(labelText: '扣款金额'),
                keyboardType: TextInputType.number,
              ),
              TextField(
                controller: paidCtrl,
                decoration: const InputDecoration(labelText: '已付金额'),
                keyboardType: TextInputType.number,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          ElevatedButton(
            onPressed: () async {
              try {
                final result = await _api.post('/settlements/milestone', {
                  'contract_amount': double.tryParse(contractCtrl.text) ?? 0,
                  'milestone_code': milestone['code'],
                  'change_amount': double.tryParse(changeCtrl.text) ?? 0,
                  'deduction_amount': double.tryParse(deductionCtrl.text) ?? 0,
                  'paid_amount': double.tryParse(paidCtrl.text) ?? 0,
                });
                if (ctx.mounted) {
                  Navigator.pop(ctx);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(result['reply'] ?? '已生成里程碑结算')),
                  );
                }
              } catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('生成失败：$e')));
                }
              }
            },
            child: const Text('生成'),
          ),
        ],
      ),
    );
  }

  Widget _buildAnomalyView() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('结算异常检测', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('输入合同与实际金额，自动检测超支、未授权变更、重复计费等异常', style: TextStyle(color: Colors.grey)),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _runAnomalyCheck,
            icon: const Icon(Icons.bug_report),
            label: const Text('一键检测异常'),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _generateReconciliation,
            icon: const Icon(Icons.receipt),
            label: const Text('生成对账单'),
          ),
        ],
      ),
    );
  }

  Future<void> _runAnomalyCheck() async {
    try {
      final result = await _api.post('/settlements/anomaly-check', {
        'contract_amount': 200000,
        'actual_amount': 218000,
        'change_orders': [
          {'name': '墙面升级', 'amount': 15000, 'authorized': true},
        ],
        'unaccepted_items': [],
        'line_items': [],
      });
      if (mounted) {
        final total = result['total_anomalies'] ?? 0;
        final critical = result['critical_count'] ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('检测完成：$total 项异常（$critical 项严重）')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('检测失败：$e')));
      }
    }
  }

  Future<void> _generateReconciliation() async {
    try {
      final result = await _api.post('/settlements/reconciliation', {
        'contract_amount': 200000,
        'change_orders': [
          {'name': '墙面升级', 'amount': 15000, 'authorized': true},
        ],
        'procurement_actual': 80000,
        'labor_actual': 50000,
        'unaccepted_items': [],
      });
      if (mounted) {
        final payable = result['total_payable'] ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('对账单已生成，应付 ¥$payable')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('生成失败：$e')));
      }
    }
  }
}
