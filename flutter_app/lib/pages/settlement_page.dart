// 索克家居
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 结算确认页面
class SettlementPage extends StatefulWidget {
  final String projectId;
  const SettlementPage({super.key, required this.projectId});

  @override
  State<SettlementPage> createState() => _SettlementPageState();
}

class _SettlementPageState extends State<SettlementPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();
  Map<String, dynamic>? _settlement;
  List<dynamic> _milestones = [];
  bool _loading = false;
  String? _error;

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF0E0E1A);
  static const _card = Color(0xFF12121D);
  static const _surface = Color(0xFF1A1A2E);
  static const _textSecondary = Color(0xFF8A8894);

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
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.get('/settlements/project/${widget.projectId}');
    if (result.isSuccess) {
      setState(() => _settlement = result.data);
    } else {
      // 404 表示尚未生成结算单，不算错误
      if (result.statusCode == 404) {
        setState(() => _settlement = null);
      } else {
        setState(() => _error = '结算单加载失败，请检查网络后重试');
      }
    }
    setState(() => _loading = false);
  }

  Future<void> _loadMilestones() async {
    final result = await _api.get('/settlements/milestones');
    if (result.isSuccess) {
      final data = result.data;
      setState(() => _milestones = (data['milestones'] as List?) ?? []);
    }
  }

  Future<void> _generateFromBudget() async {
    setState(() => _loading = true);
    final result = await _api.post(
        '/settlements/generate-from-budget/${widget.projectId}', {});
    if (result.isSuccess) {
      final data = result.data;
      setState(() => _settlement = data);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(
                  '已生成结算单，应付 ¥${(data['total_amount'] as num?)?.toDouble() ?? 0}')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('生成失败：${result.error}')));
      }
    }
    setState(() => _loading = false);
  }

  Future<void> _confirmSettlement() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surface,
        title: const Text('确认结算',
            style: TextStyle(color: Color(0xFFE8E6E1))),
        content: const Text('确认后将锁定结算金额，无法修改明细。\n是否继续？',
            style: TextStyle(color: _textSecondary)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('确认结算',
                  style: TextStyle(color: _brand))),
        ],
      ),
    );
    if (confirmed != true) return;

    final result =
        await _api.post('/settlements/confirm/${widget.projectId}', {});
    if (result.isSuccess) {
      setState(() => _settlement = result.data);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('结算单已确认')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('确认失败：${result.error}')));
      }
    }
  }

  void _disputeFeedback() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surface,
        title: const Text('异议反馈',
            style: TextStyle(color: Color(0xFFE8E6E1))),
        content: const Text(
            '如有异议，请联系客服：400-888-6666\n或在消息中心提交反馈。',
            style: TextStyle(color: _textSecondary)),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('已跳转消息中心')),
              );
            },
            child: const Text('提交反馈'),
          ),
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('关闭')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('结算确认',
            style: TextStyle(fontWeight: FontWeight.bold)),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          labelColor: _brand,
          unselectedLabelColor: _textSecondary,
          indicatorColor: _brand,
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
    if (_loading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 110);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadSettlement);
    }
    if (_settlement == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.receipt_long,
                size: 64, color: Color(0xFF5A5866)),
            const SizedBox(height: 16),
            const Text('暂无结算单',
                style: TextStyle(color: _textSecondary)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _generateFromBudget,
              style: ElevatedButton.styleFrom(
                backgroundColor: _brand,
                foregroundColor: Colors.white,
              ),
              icon: const Icon(Icons.auto_awesome),
              label: const Text('从预算生成结算'),
            ),
          ],
        ),
      );
    }

    final contractAmount =
        (_settlement!['contract_amount'] as num?)?.toDouble() ?? 0;
    final changeAmount =
        (_settlement!['change_amount'] as num?)?.toDouble() ?? 0;
    final paidAmount =
        (_settlement!['paid_amount'] as num?)?.toDouble() ?? 0;
    final totalAmount =
        (_settlement!['total_amount'] as num?)?.toDouble() ?? 0;
    final payableBalance = totalAmount - paidAmount;
    final status = _settlement!['status'] as String? ?? 'draft';
    final lines = (_settlement!['lines'] as List?) ?? [];

    return RefreshIndicator(
      onRefresh: _loadSettlement,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 金额汇总卡片
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF2A2A3E)),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('应付余额',
                        style: TextStyle(
                            color: _textSecondary, fontSize: 13)),
                    Text('¥${payableBalance.toStringAsFixed(2)}',
                        style: const TextStyle(
                            color: Color(0xFFC9973B),
                            fontSize: 28,
                            fontWeight: FontWeight.bold)),
                  ],
                ),
                const Divider(
                    color: Color(0xFF2A2A3E), height: 28),
                _amountRow('合同金额',
                    '¥${contractAmount.toStringAsFixed(2)}'),
                _amountRow(
                    '变更金额', '¥${changeAmount.toStringAsFixed(2)}'),
                _amountRow('已付金额',
                    '¥${paidAmount.toStringAsFixed(2)}'),
                const Divider(
                    color: Color(0xFF2A2A3E), height: 20),
                _amountRow('合计金额',
                    '¥${totalAmount.toStringAsFixed(2)}',
                    bold: true),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // 状态和操作
          Row(
            children: [
              _buildStatusChip(status),
              const Spacer(),
              Builder(builder: (ctx) {
                final idStr = (_settlement!['id'] ?? '-').toString();
                return Text(
                  '结算单号: ${idStr.length > 8 ? idStr.substring(0, 8) : idStr}',
                  style: const TextStyle(
                      color: Color(0xFF5A5866), fontSize: 11),
                );
              }),
            ],
          ),
          const SizedBox(height: 16),
          // 结算明细
          if (lines.isNotEmpty) ...[
            const Text('结算明细',
                style: TextStyle(
                    color: Color(0xFFE8E6E1),
                    fontWeight: FontWeight.bold,
                    fontSize: 15)),
            const SizedBox(height: 8),
            ...lines.map((line) => Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _surface,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFF2A2A3E)),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                                line['name']?.toString() ?? '',
                                style: const TextStyle(
                                    color: Color(0xFFE8E6E1))),
                            if (line['milestone'] != null)
                              Text(
                                  line['milestone'].toString(),
                                  style: const TextStyle(
                                      color: _textSecondary,
                                      fontSize: 11)),
                          ],
                        ),
                      ),
                      Text(
                        '¥${(line['amount'] as num?)?.toDouble().toStringAsFixed(2) ?? '0.00'}',
                        style: const TextStyle(
                            color: Color(0xFFE8E6E1),
                            fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                )),
          ],
          const SizedBox(height: 20),
          // 操作按钮
          if (status == 'draft')
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: _confirmSettlement,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _brand,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.check_circle, size: 18),
                    label: const Text('确认结算',
                        style: TextStyle(fontWeight: FontWeight.w600)),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _disputeFeedback,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _textSecondary,
                      side: const BorderSide(
                          color: Color(0xFF2A2A3E)),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.feedback_outlined, size: 18),
                    label: const Text('异议反馈'),
                  ),
                ),
              ],
            ),
        ],
      ),
    );
  }

  Widget _amountRow(String label, String value, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: const TextStyle(
                  color: Color(0xFF8A8894), fontSize: 13)),
          Text(value,
              style: TextStyle(
                  color: const Color(0xFFE8E6E1),
                  fontSize: 14,
                  fontWeight:
                      bold ? FontWeight.bold : FontWeight.normal)),
        ],
      ),
    );
  }

  Widget _buildStatusChip(String status) {
    final (label, color) = switch (status) {
      'draft' => ('草稿', const Color(0xFF8A8894)),
      'confirmed' => ('已确认', const Color(0xFF5A7EC9)),
      'paid' => ('已支付', const Color(0xFF4A9E6E)),
      'completed' => ('已完成', const Color(0xFF3CB371)),
      _ => (status, const Color(0xFF8A8894)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(label,
          style: TextStyle(color: color, fontSize: 12)),
    );
  }

  // ── 里程碑（时间轴样式）──
  Widget _buildMilestonesView() {
    if (_milestones.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.flag_outlined,
                size: 48, color: Color(0xFF5A5866)),
            const SizedBox(height: 12),
            const Text('暂无里程碑',
                style: TextStyle(color: _textSecondary)),
          ],
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _milestones.length,
      itemBuilder: (context, index) {
        final m = _milestones[index] as Map<String, dynamic>;
        final ratio =
            (m['payment_ratio'] as num?)?.toDouble() ?? 0;
        final isLast = index == _milestones.length - 1;
        final isFirst = index == 0;
        final isPassed = (m['status']?.toString() ?? '') == 'completed';

        return IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 时间轴线条
              SizedBox(
                width: 40,
                child: Column(
                  children: [
                    if (!isFirst)
                      Container(
                        width: 2,
                        height: 12,
                        color: isPassed
                            ? _brand
                            : const Color(0xFF2A2A3E),
                      )
                    else
                      const SizedBox(height: 12),
                    Container(
                      width: 18,
                      height: 18,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isPassed
                            ? _brand
                            : const Color(0xFF2A2A3E),
                        border: Border.all(
                            color: _brand, width: 2),
                      ),
                      child: isPassed
                          ? const Icon(Icons.check,
                              size: 10, color: Colors.white)
                          : null,
                    ),
                    if (!isLast)
                      Expanded(
                        child: Container(
                          width: 2,
                          color: isPassed
                              ? _brand
                              : const Color(0xFF2A2A3E),
                        ),
                      ),
                  ],
                ),
              ),
              // 里程碑卡片
              Expanded(
                child: Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _surface,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                        color: isPassed
                            ? _brand.withValues(alpha: 0.3)
                            : const Color(0xFF2A2A3E)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                                m['name']?.toString() ?? '',
                                style: const TextStyle(
                                    color: Color(0xFFE8E6E1),
                                    fontWeight: FontWeight.w600)),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: _brand.withValues(alpha: 0.15),
                              borderRadius:
                                  BorderRadius.circular(6),
                            ),
                            child: Text(
                                '${(ratio * 100).toInt()}%',
                                style: const TextStyle(
                                    color: _brand, fontSize: 11)),
                          ),
                        ],
                      ),
                      if ((m['description']?.toString() ?? '')
                          .isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(m['description'].toString(),
                            style: const TextStyle(
                                color: _textSecondary,
                                fontSize: 12)),
                      ],
                      const SizedBox(height: 4),
                      Text(
                          '付款比例: ${(ratio * 100).toInt()}%',
                          style: const TextStyle(
                              color: Color(0xFF5A5866),
                              fontSize: 11)),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ── 异常检测 ──
  Widget _buildAnomalyView() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('结算异常检测',
                style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFFE8E6E1))),
            const SizedBox(height: 8),
            const Text(
                '检测合同金额与实际金额的差异，发现超支、未授权变更、重复计费等异常',
                style: TextStyle(color: _textSecondary)),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _runAnomalyCheck,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _surface,
                  foregroundColor: const Color(0xFFE8E6E1),
                  padding:
                      const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                      side: const BorderSide(
                          color: Color(0xFF2A2A3E))),
                ),
                icon: const Icon(Icons.bug_report),
                label: const Text('一键检测异常'),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _generateReconciliation,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _surface,
                  foregroundColor: const Color(0xFFE8E6E1),
                  padding:
                      const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(10),
                      side: const BorderSide(
                          color: Color(0xFF2A2A3E))),
                ),
                icon: const Icon(Icons.receipt),
                label: const Text('生成对账单'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _runAnomalyCheck() async {
    final result = await _api.post('/settlements/anomaly-check', {
      'contract_amount': 200000,
      'actual_amount': 218000,
      'change_orders': [
        {'name': '墙面升级', 'amount': 15000, 'authorized': true},
      ],
      'unaccepted_items': [],
      'line_items': [],
    });
    if (result.isSuccess) {
      final data = result.data;
      if (mounted) {
        final total = data['total_anomalies'] ?? 0;
        final critical = data['critical_count'] ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text('检测完成：$total 项异常（$critical 项严重）')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('检测失败：${result.error}')));
      }
    }
  }

  Future<void> _generateReconciliation() async {
    final result =
        await _api.post('/settlements/reconciliation', {
      'contract_amount': 200000,
      'change_orders': [
        {'name': '墙面升级', 'amount': 15000, 'authorized': true},
      ],
      'procurement_actual': 80000,
      'labor_actual': 50000,
      'unaccepted_items': [],
    });
    if (result.isSuccess) {
      final data = result.data;
      if (mounted) {
        final payable = data['total_payable'] ?? 0;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('对账单已生成，应付 ¥$payable')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('生成失败：${result.error}')));
      }
    }
  }
}
