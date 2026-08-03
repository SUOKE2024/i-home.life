import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// 变更订单管理页面 — F39
class ChangeOrdersPage extends StatefulWidget {
  final String projectId;
  const ChangeOrdersPage({super.key, required this.projectId});

  @override
  State<ChangeOrdersPage> createState() => _ChangeOrdersPageState();
}

class _ChangeOrdersPageState extends State<ChangeOrdersPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _orders = [];
  Map<String, dynamic>? _selectedOrder;
  bool _loading = false;
  bool _detailLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) return;
      if (_tabController.index == 1 && _selectedOrder != null) {
        _loadDetail(_selectedOrder!['id']);
      }
    });
    _loadOrders();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadOrders() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.changeOrderList(widget.projectId);
    if (result.isSuccess) {
      final data = result.data;
      setState(() {
        _orders = (data as List?) ?? [];
        _loading = false;
      });
    } else {
      setState(() {
        _error = '变更订单加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  Future<void> _loadDetail(String changeId) async {
    setState(() => _detailLoading = true);
    final result = await _api.changeOrderGet(changeId);
    if (result.isSuccess) {
      setState(() {
        _selectedOrder = result.data;
        _detailLoading = false;
      });
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('详情加载失败：${result.error}')),
        );
      }
      setState(() => _detailLoading = false);
    }
  }

  // ── 创建变更订单 ──

  void _showCreateDialog() {
    final formKey = GlobalKey<FormState>();
    final titleCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final itemNameCtrl = TextEditingController();
    final qtyCtrl = TextEditingController(text: '1');
    final priceCtrl = TextEditingController(text: '0');
    String changeType = 'owner_request';
    String itemAction = 'add';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text('发起变更订单',
              style: TextStyle(color: SuokeDesignTokens.text(context), fontWeight: FontWeight.bold)),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: titleCtrl,
                    decoration: _inputDeco('变更标题'),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    validator: (v) =>
                        (v == null || v.isEmpty) ? '请输入标题' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: descCtrl,
                    decoration: _inputDeco('变更原因 / 描述'),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    maxLines: 3,
                    validator: (v) =>
                        (v == null || v.isEmpty) ? '请输入变更原因' : null,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: changeType,
                    decoration: _inputDeco('变更类型'),
                    dropdownColor: SuokeDesignTokens.card(context),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    items: const [
                      DropdownMenuItem(value: 'owner_request', child: Text('业主需求')),
                      DropdownMenuItem(value: 'design_issue', child: Text('设计问题')),
                      DropdownMenuItem(value: 'site_condition', child: Text('现场情况')),
                      DropdownMenuItem(value: 'material_change', child: Text('材料变更')),
                    ],
                    onChanged: (v) =>
                        setDialogState(() => changeType = v ?? 'owner_request'),
                  ),
                  const SizedBox(height: 16),
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: Text('变更项',
                        style: TextStyle(
                            color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: itemNameCtrl,
                    decoration: _inputDeco('项目名称'),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    validator: (v) =>
                        (v == null || v.isEmpty) ? '请输入项目名称' : null,
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: itemAction,
                    decoration: _inputDeco('操作类型'),
                    dropdownColor: SuokeDesignTokens.card(context),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    items: const [
                      DropdownMenuItem(value: 'add', child: Text('增项')),
                      DropdownMenuItem(value: 'modify', child: Text('变更')),
                      DropdownMenuItem(value: 'remove', child: Text('减项')),
                    ],
                    onChanged: (v) =>
                        setDialogState(() => itemAction = v ?? 'add'),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextFormField(
                          controller: qtyCtrl,
                          decoration: _inputDeco('数量'),
                          style: TextStyle(color: SuokeDesignTokens.text(context)),
                          keyboardType:
                              const TextInputType.numberWithOptions(decimal: true),
                          validator: (v) {
                            final n = double.tryParse(v ?? '');
                            if (n == null || n <= 0) return '请输入有效数量';
                            return null;
                          },
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextFormField(
                          controller: priceCtrl,
                          decoration: _inputDeco('单价'),
                          style: TextStyle(color: SuokeDesignTokens.text(context)),
                          keyboardType:
                              const TextInputType.numberWithOptions(decimal: true),
                          validator: (v) {
                            final n = double.tryParse(v ?? '');
                            if (n == null || n < 0) return '请输入有效单价';
                            return null;
                          },
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('取消', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: SuokeDesignTokens.accent,
                foregroundColor: Colors.white,
              ),
              onPressed: () async {
                if (!formKey.currentState!.validate()) return;
                final qty = double.parse(qtyCtrl.text);
                final price = double.parse(priceCtrl.text);
                final body = {
                  'project_id': widget.projectId,
                  'title': titleCtrl.text.trim(),
                  'description': descCtrl.text.trim(),
                  'change_type': changeType,
                  'items': [
                    {
                      'name': itemNameCtrl.text.trim(),
                      'action': itemAction,
                      'quantity': qty,
                      'unit_price': price,
                      'amount': qty * price,
                    }
                  ],
                };
                Navigator.pop(ctx);
                await _createOrder(body);
              },
              child: const Text('提交'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createOrder(Map<String, dynamic> body) async {
    setState(() => _loading = true);
    final result = await _api.changeOrderCreate(body);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('变更订单已提交')),
        );
      }
      await _loadOrders();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('创建失败：${result.error}')),
        );
      }
      setState(() => _loading = false);
    }
  }

  // ── 审批操作 ──

  Future<void> _approveOrder(String changeId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('通过审批',
            style: TextStyle(color: SuokeDesignTokens.text(context), fontWeight: FontWeight.bold)),
        content: Text('确认通过该变更订单？',
            style: TextStyle(color: SuokeDesignTokens.textSub(context))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('取消', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('确认通过', style: TextStyle(color: SuokeDesignTokens.accent)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final result = await _api.changeOrderApprove(changeId);
    if (result.isSuccess) {
      setState(() => _selectedOrder = result.data);
      await _loadOrders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已通过审批')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败：${result.error}')),
        );
      }
    }
  }

  Future<void> _rejectOrder(String changeId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('拒绝变更',
            style: TextStyle(color: SuokeDesignTokens.text(context), fontWeight: FontWeight.bold)),
        content: Text('确认拒绝该变更订单？',
            style: TextStyle(color: SuokeDesignTokens.textSub(context))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('取消', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('确认拒绝', style: TextStyle(color: SuokeDesignTokens.danger)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final result = await _api.changeOrderCancel(changeId);
    if (result.isSuccess) {
      setState(() => _selectedOrder = result.data);
      await _loadOrders();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已拒绝变更')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败：${result.error}')),
        );
      }
    }
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        title: const Text('变更订单',
            style: TextStyle(fontWeight: FontWeight.bold)),
        foregroundColor: Colors.white,
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSub(context),
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '订单列表'),
            Tab(text: '订单详情'),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: SuokeDesignTokens.accent,
        foregroundColor: Colors.white,
        onPressed: _showCreateDialog,
        child: const Icon(Icons.add),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildOrderList(),
          _buildOrderDetail(),
        ],
      ),
    );
  }

  Widget _buildOrderList() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 110);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadOrders);
    }
    if (_orders.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.assignment_outlined,
                size: 64, color: Color(0xFF5A5866)),
            const SizedBox(height: 16),
            Text('暂无变更订单', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: SuokeDesignTokens.accent,
                foregroundColor: Colors.white,
              ),
              onPressed: _showCreateDialog,
              icon: const Icon(Icons.add),
              label: const Text('发起变更'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadOrders,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _orders.length,
        itemBuilder: (context, index) {
          final order = _orders[index] as Map<String, dynamic>;
          return _buildOrderCard(order);
        },
      ),
    );
  }

  Widget _buildOrderCard(Map<String, dynamic> order) {
    final id = order['id']?.toString() ?? '';
    final title = order['title']?.toString() ?? '未命名变更';
    final status = order['status']?.toString() ?? 'pending';
    final submittedBy = order['submitted_by']?.toString() ?? '未知';
    final items = (order['items'] as List?) ?? [];
    final orderType = _deriveOrderType(items);
    final totalAmount = _computeTotalAmount(items);
    final changeType = order['change_type']?.toString() ?? '';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () {
          setState(() => _selectedOrder = order);
          _tabController.animateTo(1);
          _loadDetail(id);
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(
                      color: SuokeDesignTokens.text(context),
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                _buildStatusChip(status),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _buildTypeChip(orderType),
                const SizedBox(width: 8),
                if (changeType.isNotEmpty)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: SuokeDesignTokens.borderClr(context),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      _changeTypeLabel(changeType),
                      style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '发起人：$submittedBy',
                  style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13),
                ),
                Text(
                  '¥${totalAmount.toStringAsFixed(2)}',
                  style: const TextStyle(
                    color: SuokeDesignTokens.accent,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOrderDetail() {
    if (_selectedOrder == null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.assignment_outlined,
                size: 64, color: Color(0xFF5A5866)),
            const SizedBox(height: 16),
            Text('请从列表中选择一个变更订单查看详情',
                style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ],
        ),
      );
    }

    if (_detailLoading) {
      return const LoadingSkeleton(itemCount: 3, itemHeight: 100);
    }

    final order = _selectedOrder!;
    final title = order['title']?.toString() ?? '';
    final status = order['status']?.toString() ?? 'pending';
    final description = order['description']?.toString() ?? '';
    final changeType = order['change_type']?.toString() ?? '';
    final submittedBy = order['submitted_by']?.toString() ?? '未知';
    final reviewedBy = order['reviewed_by']?.toString() ?? '';
    final approvedBy = order['approved_by']?.toString() ?? '';
    final costImpact = (order['cost_impact'] as num?)?.toDouble() ?? 0;
    final scheduleImpact = (order['schedule_impact_days'] as num?)?.toInt() ?? 0;
    final designImpact = order['design_impact']?.toString() ?? '';
    final feasibility = order['feasibility']?.toString() ?? '';
    final feasibilityNote = order['feasibility_note']?.toString() ?? '';
    final items = (order['items'] as List?) ?? [];
    final totalAmount = _computeTotalAmount(items);
    final canApprove = status == 'pending' || status == 'submitted' || status == 'reviewed';

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // 标题 + 状态
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: SuokeDesignTokens.card(context),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: SuokeDesignTokens.borderClr(context)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  _buildStatusChip(status),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  _buildTypeChip(_deriveOrderType(items)),
                  const SizedBox(width: 8),
                  if (changeType.isNotEmpty)
                    Text('· ${_changeTypeLabel(changeType)}',
                        style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // 变更原因
        _buildSectionCard(
          title: '变更原因',
          child: Text(
            description,
            style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14, height: 1.6),
          ),
        ),
        const SizedBox(height: 16),

        // 变更项列表
        _buildSectionCard(
          title: '变更项（${items.length}）',
          child: items.isEmpty
              ? Text('暂无变更项', style: TextStyle(color: SuokeDesignTokens.textSub(context)))
              : Column(
                  children: items.map<Widget>((item) {
                    final m = item as Map<String, dynamic>;
                    final name = m['name']?.toString() ?? '';
                    final action = m['action']?.toString() ?? 'modify';
                    final qty = (m['quantity'] as num?)?.toDouble() ?? 0;
                    final price = (m['unit_price'] as num?)?.toDouble() ?? 0;
                    final amount = (m['amount'] as num?)?.toDouble() ?? 0;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: SuokeDesignTokens.bg(context),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: SuokeDesignTokens.borderClr(context)),
                        ),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 3),
                              decoration: BoxDecoration(
                                color: _actionColor(action).withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                _actionLabel(action),
                                style: TextStyle(
                                  color: _actionColor(action),
                                  fontSize: 12,
                                ),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(name,
                                      style: TextStyle(
                                          color: SuokeDesignTokens.text(context),
                                          fontWeight: FontWeight.w500)),
                                  const SizedBox(height: 4),
                                  Text(
                                    '数量 $qty · 单价 ¥$price',
                                    style: TextStyle(
                                        color: SuokeDesignTokens.textSub(context), fontSize: 12),
                                  ),
                                ],
                              ),
                            ),
                            Text(
                              '¥${amount.toStringAsFixed(2)}',
                              style: const TextStyle(
                                color: SuokeDesignTokens.accent,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
        ),
        const SizedBox(height: 16),

        // 影响范围
        _buildSectionCard(
          title: '影响范围',
          child: Column(
            children: [
              _impactRow('变更金额', '¥${totalAmount.toStringAsFixed(2)}'),
              _impactRow('成本影响', '¥${costImpact.toStringAsFixed(2)}'),
              _impactRow('工期影响', '$scheduleImpact 天'),
              if (designImpact.isNotEmpty)
                _impactRow('设计影响', designImpact),
              if (feasibility.isNotEmpty)
                _impactRow('可行性评估', _feasibilityLabel(feasibility)),
              if (feasibilityNote.isNotEmpty)
                _impactRow('评估说明', feasibilityNote),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // 审批人信息
        _buildSectionCard(
          title: '审批信息',
          child: Column(
            children: [
              _impactRow('发起人', submittedBy),
              if (reviewedBy.isNotEmpty) _impactRow('评审人', reviewedBy),
              if (approvedBy.isNotEmpty) _impactRow('审批人', approvedBy),
            ],
          ),
        ),

        // 审批操作
        if (canApprove) ...[
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: () => _approveOrder(order['id']),
                  icon: const Icon(Icons.check),
                  label: const Text('通过'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: SuokeDesignTokens.danger,
                    side: const BorderSide(color: SuokeDesignTokens.danger),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: () => _rejectOrder(order['id']),
                  icon: const Icon(Icons.close),
                  label: const Text('拒绝'),
                ),
              ),
            ],
          ),
        ],
        const SizedBox(height: 32),
      ],
    );
  }

  // ── 辅助组件 ──

  Widget _buildSectionCard({required String title, required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold, fontSize: 14)),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }

  Widget _impactRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          Text(value,
              style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildStatusChip(String status) {
    final (label, color) = _statusStyle(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(label,
          style: TextStyle(
              color: color, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }

  Widget _buildTypeChip(String type) {
    final color = _typeColor(type);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(type,
          style: TextStyle(
              color: color, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }

  InputDecoration _inputDeco(String label) => InputDecoration(
        labelText: label,
        labelStyle: TextStyle(color: SuokeDesignTokens.textSub(context)),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: SuokeDesignTokens.borderClr(context)),
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: const BorderSide(color: SuokeDesignTokens.accent),
          borderRadius: BorderRadius.circular(8),
        ),
        filled: true,
        fillColor: SuokeDesignTokens.bg(context),
      );

  // ── 工具方法 ──

  String _deriveOrderType(List<dynamic> items) {
    if (items.isEmpty) return '变更';
    final actions = items
        .map((i) => (i as Map<String, dynamic>)['action'] as String? ?? '')
        .toSet();
    if (actions.length == 1) {
      switch (actions.first) {
        case 'add':
          return '增项';
        case 'remove':
          return '减项';
        case 'modify':
          return '变更';
      }
    }
    return '变更';
  }

  double _computeTotalAmount(List<dynamic> items) {
    double total = 0;
    for (final item in items) {
      final m = item as Map<String, dynamic>;
      final amount = (m['amount'] as num?)?.toDouble() ?? 0;
      total += amount;
    }
    return total;
  }

  (String, Color) _statusStyle(String status) {
    switch (status) {
      case 'pending':
      case 'submitted':
        return ('待审批', SuokeDesignTokens.warning);
      case 'reviewed':
        return ('已评审', SuokeDesignTokens.info);
      case 'approved':
        return ('已通过', SuokeDesignTokens.success);
      case 'rejected':
        return ('已拒绝', SuokeDesignTokens.danger);
      case 'cancelled':
        return ('已取消', SuokeDesignTokens.textSub(context));
      default:
        return (status, SuokeDesignTokens.textSub(context));
    }
  }

  Color _typeColor(String type) {
    switch (type) {
      case '增项':
        return SuokeDesignTokens.success;
      case '减项':
        return SuokeDesignTokens.danger;
      default:
        return SuokeDesignTokens.accent;
    }
  }

  Color _actionColor(String action) {
    switch (action) {
      case 'add':
        return SuokeDesignTokens.success;
      case 'remove':
        return SuokeDesignTokens.danger;
      default:
        return SuokeDesignTokens.accent;
    }
  }

  String _actionLabel(String action) {
    switch (action) {
      case 'add':
        return '增项';
      case 'remove':
        return '减项';
      case 'modify':
        return '变更';
      default:
        return action;
    }
  }

  String _changeTypeLabel(String type) {
    switch (type) {
      case 'owner_request':
        return '业主需求';
      case 'design_issue':
        return '设计问题';
      case 'site_condition':
        return '现场情况';
      case 'material_change':
        return '材料变更';
      default:
        return type;
    }
  }

  String _feasibilityLabel(String feasibility) {
    switch (feasibility) {
      case 'feasible':
        return '可行';
      case 'infeasible':
        return '不可行';
      case 'partial':
        return '部分可行';
      default:
        return feasibility;
    }
  }
}
