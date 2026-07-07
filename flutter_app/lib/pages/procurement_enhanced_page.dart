import 'package:flutter/material.dart';
import '../services/api.dart';

/// 采购增强页面 - 整合 F33/F34
/// 4 Tab: 比价 / 托管支付 / 物流 / 样品申请
class ProcurementEnhancedPage extends StatefulWidget {
  final String projectId;
  const ProcurementEnhancedPage({super.key, required this.projectId});

  @override
  State<ProcurementEnhancedPage> createState() =>
      _ProcurementEnhancedPageState();
}

class _ProcurementEnhancedPageState extends State<ProcurementEnhancedPage>
    with TickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF08080F);
  static const _card = Color(0xFF12121D);
  static const _textSecondary = Color(0xFF8A8894);

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _toast(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('采购增强',
            style: TextStyle(
                fontWeight: FontWeight.bold, fontFamily: 'DM Sans')),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          labelColor: _brand,
          unselectedLabelColor: _textSecondary,
          indicatorColor: _brand,
          tabs: const [
            Tab(text: '比价'),
            Tab(text: '托管支付'),
            Tab(text: '物流'),
            Tab(text: '样品申请'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _PriceComparisonTab(
              api: _api, projectId: widget.projectId, toast: _toast),
          _EscrowTab(api: _api, projectId: widget.projectId, toast: _toast),
          _LogisticsTab(api: _api, projectId: widget.projectId, toast: _toast),
          _SampleTab(api: _api, projectId: widget.projectId, toast: _toast),
        ],
      ),
    );
  }
}

/// 通用空状态
Widget _procEmptyState(String text, {IconData icon = Icons.inbox_outlined}) {
  return Center(
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 56, color: const Color(0xFF5A5866)),
        const SizedBox(height: 12),
        Text(text, style: const TextStyle(color: Color(0xFF8A8894))),
      ],
    ),
  );
}

Widget _procSectionCard({required List<Widget> children}) {
  return Card(
    color: const Color(0xFF12121D),
    margin: const EdgeInsets.only(bottom: 10),
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(12),
      side: const BorderSide(color: Color(0xFF1E1E32)),
    ),
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    ),
  );
}

Widget _procKv(String k, String v) {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: 2),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 80,
          child: Text(k,
              style: const TextStyle(color: Color(0xFF8A8894), fontSize: 12)),
        ),
        Expanded(
          child: Text(v,
              style: const TextStyle(color: Color(0xFFE8E6E1), fontSize: 13)),
        ),
      ],
    ),
  );
}

Color _statusColor(String? status) {
  switch (status) {
    case 'pending':
      return const Color(0xFF8A8894);
    case 'in_progress':
    case 'shipping':
    case 'confirmed':
      return const Color(0xFF5B8EC4);
    case 'completed':
    case 'delivered':
    case 'approved':
      return const Color(0xFF4A9E6E);
    case 'rejected':
    case 'failed':
      return const Color(0xFFD9534F);
    default:
      return const Color(0xFF8A8894);
  }
}

String _statusText(String? s) {
  const map = {
    'pending': '待处理',
    'in_progress': '进行中',
    'shipping': '运输中',
    'confirmed': '已确认',
    'completed': '已完成',
    'delivered': '已送达',
    'approved': '已批准',
    'rejected': '已拒绝',
    'failed': '失败',
  };
  return map[s] ?? (s ?? '-');
}

// ─────────────────────────────────────────────
// F33 比价
// ─────────────────────────────────────────────
class _PriceComparisonTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _PriceComparisonTab(
      {required this.api, required this.projectId, required this.toast});

  @override
  State<_PriceComparisonTab> createState() => _PriceComparisonTabState();
}

class _PriceComparisonTabState extends State<_PriceComparisonTab>
    with AutomaticKeepAliveClientMixin {
  List<dynamic> _items = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.api.procPriceComparisons(projectId: widget.projectId);
      _items = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载比价失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final materialName = await _showInputDialog('新建比价', '物料名称');
    if (materialName == null || materialName.isEmpty) return;
    try {
      await widget.api.procCreatePriceComparison({
        'project_id': widget.projectId,
        'material_name': materialName,
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _procEmptyState('暂无比价记录，点击右下角新建',
                          icon: Icons.compare_arrows_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    itemBuilder: (ctx, i) {
                      final item = Map<String, dynamic>.from(_items[i] as Map);
                      final status = item['status']?.toString();
                      final offers = item['offers'] is List
                          ? item['offers'] as List
                          : <dynamic>[];
                      final lowest = item['lowest_price'];
                      final highest = item['highest_price'];
                      return _procSectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                  (item['material_name'] ?? '比价').toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: _statusColor(status)
                                    .withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(_statusText(status),
                                  style: TextStyle(
                                      color: _statusColor(status),
                                      fontSize: 10)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _procKv('ID', (item['id'] ?? '-').toString()),
                        if (lowest != null)
                          _procKv('最低价', '¥$lowest'),
                        if (highest != null)
                          _procKv('最高价', '¥$highest'),
                        _procKv('报价数', '${offers.length}'),
                        if (item['recommended_supplier'] != null)
                          _procKv('推荐供应商',
                              item['recommended_supplier'].toString()),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F33 托管支付
// ─────────────────────────────────────────────
class _EscrowTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _EscrowTab(
      {required this.api, required this.projectId, required this.toast});

  @override
  State<_EscrowTab> createState() => _EscrowTabState();
}

class _EscrowTabState extends State<_EscrowTab>
    with AutomaticKeepAliveClientMixin {
  List<dynamic> _items = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data =
          await widget.api.procEscrowPayments(projectId: widget.projectId);
      _items = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载托管支付失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final amountStr = await _showInputDialog('新建托管支付', '金额（元）');
    if (amountStr == null || amountStr.isEmpty) return;
    final amount = double.tryParse(amountStr);
    if (amount == null) {
      widget.toast('金额格式错误');
      return;
    }
    try {
      await widget.api.procCreateEscrowPayment({
        'project_id': widget.projectId,
        'amount': amount,
        'currency': 'CNY',
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<void> _confirm(String id) async {
    try {
      await widget.api.procConfirmEscrow(id);
      widget.toast('已确认');
      _load();
    } catch (e) {
      widget.toast('确认失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _procEmptyState('暂无托管支付，点击右下角新建',
                          icon: Icons.account_balance_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    itemBuilder: (ctx, i) {
                      final item = Map<String, dynamic>.from(_items[i] as Map);
                      final status = item['status']?.toString();
                      final amount = item['amount'];
                      return _procSectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                  (item['payee'] ?? '托管支付').toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: _statusColor(status)
                                    .withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(_statusText(status),
                                  style: TextStyle(
                                      color: _statusColor(status),
                                      fontSize: 10)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _procKv('ID', (item['id'] ?? '-').toString()),
                        if (amount != null)
                          _procKv('金额', '¥$amount'),
                        if (item['currency'] != null)
                          _procKv('币种', item['currency'].toString()),
                        if (item['escrow_no'] != null)
                          _procKv('托管号', item['escrow_no'].toString()),
                        if (item['created_at'] != null)
                          _procKv('创建时间', item['created_at'].toString()),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            if (status == 'pending')
                              TextButton.icon(
                                onPressed: () =>
                                    _confirm(item['id']?.toString() ?? ''),
                                icon: const Icon(Icons.check, size: 16),
                                label: const Text('确认放款'),
                              ),
                          ],
                        ),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F34 物流
// ─────────────────────────────────────────────
class _LogisticsTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _LogisticsTab(
      {required this.api, required this.projectId, required this.toast});

  @override
  State<_LogisticsTab> createState() => _LogisticsTabState();
}

class _LogisticsTabState extends State<_LogisticsTab>
    with AutomaticKeepAliveClientMixin {
  List<dynamic> _items = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data =
          await widget.api.procLogistics(projectId: widget.projectId);
      _items = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载物流失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final trackingNo = await _showInputDialog('新建物流', '运单号');
    if (trackingNo == null || trackingNo.isEmpty) return;
    try {
      await widget.api.procCreateLogistics({
        'project_id': widget.projectId,
        'tracking_no': trackingNo,
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<void> _track(String id) async {
    try {
      final result = await widget.api.procTrackLogistics(id);
      if (!mounted) return;
      final tracks = result is Map ? result['tracks'] : null;
      showDialog(
        context: context,
        builder: (_) => AlertDialog(
          backgroundColor: const Color(0xFF12121D),
          title: const Text('物流跟踪', style: TextStyle(color: Color(0xFFE8E6E1))),
          content: SizedBox(
            width: double.maxFinite,
            child: (tracks is List && tracks.isNotEmpty)
                ? ListView.builder(
                    shrinkWrap: true,
                    itemCount: tracks.length,
                    itemBuilder: (_, i) {
                      final t = Map<String, dynamic>.from(tracks[i] as Map);
                      return ListTile(
                        dense: true,
                        leading: const Icon(Icons.circle,
                            size: 10, color: Color(0xFFC9973B)),
                        title: Text((t['event'] ?? '').toString(),
                            style: const TextStyle(color: Color(0xFFE8E6E1))),
                        subtitle: Text((t['time'] ?? '').toString(),
                            style: const TextStyle(color: Color(0xFF8A8894))),
                      );
                    },
                  )
                : const Text('暂无轨迹',
                    style: TextStyle(color: Color(0xFF8A8894))),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('关闭'),
            ),
          ],
        ),
      );
    } catch (e) {
      widget.toast('查询失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _procEmptyState('暂无物流记录，点击右下角新建',
                          icon: Icons.local_shipping_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    itemBuilder: (ctx, i) {
                      final item = Map<String, dynamic>.from(_items[i] as Map);
                      final status = item['status']?.toString();
                      return _procSectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                  (item['tracking_no'] ?? '物流').toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: _statusColor(status)
                                    .withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(_statusText(status),
                                  style: TextStyle(
                                      color: _statusColor(status),
                                      fontSize: 10)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _procKv('ID', (item['id'] ?? '-').toString()),
                        if (item['carrier'] != null)
                          _procKv('承运商', item['carrier'].toString()),
                        if (item['origin'] != null)
                          _procKv('起点', item['origin'].toString()),
                        if (item['destination'] != null)
                          _procKv('终点', item['destination'].toString()),
                        if (item['eta'] != null)
                          _procKv('预计送达', item['eta'].toString()),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton.icon(
                              onPressed: () =>
                                  _track(item['id']?.toString() ?? ''),
                              icon: const Icon(Icons.location_on_outlined,
                                  size: 16),
                              label: const Text('跟踪'),
                            ),
                          ],
                        ),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}

// ─────────────────────────────────────────────
// F34 样品申请
// ─────────────────────────────────────────────
class _SampleTab extends StatefulWidget {
  final ApiClient api;
  final String projectId;
  final void Function(String) toast;
  const _SampleTab(
      {required this.api, required this.projectId, required this.toast});

  @override
  State<_SampleTab> createState() => _SampleTabState();
}

class _SampleTabState extends State<_SampleTab>
    with AutomaticKeepAliveClientMixin {
  List<dynamic> _items = [];
  bool _loading = false;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data =
          await widget.api.procSampleRequests(projectId: widget.projectId);
      _items = data is List ? data : (data['items'] as List? ?? []);
    } catch (e) {
      widget.toast('加载样品申请失败: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _create() async {
    final material = await _showInputDialog('新建样品申请', '物料名称');
    if (material == null || material.isEmpty) return;
    try {
      await widget.api.procCreateSampleRequest({
        'project_id': widget.projectId,
        'material_name': material,
      });
      widget.toast('已创建');
      _load();
    } catch (e) {
      widget.toast('创建失败: $e');
    }
  }

  Future<void> _approve(String id) async {
    try {
      await widget.api.procApproveSample(id);
      widget.toast('已批准');
      _load();
    } catch (e) {
      widget.toast('操作失败: $e');
    }
  }

  Future<String?> _showInputDialog(String title, String label) {
    final ctrl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF12121D),
        title: Text(title, style: const TextStyle(color: Color(0xFFE8E6E1))),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          decoration: InputDecoration(
            labelText: label,
            labelStyle: const TextStyle(color: Color(0xFF8A8894)),
          ),
          style: const TextStyle(color: Color(0xFFE8E6E1)),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('取消')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, ctrl.text.trim()),
              child: const Text('确定')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _items.isEmpty
              ? RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    children: [
                      const SizedBox(height: 120),
                      _procEmptyState('暂无样品申请，点击右下角新建',
                          icon: Icons.inventory_2_outlined),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _items.length,
                    itemBuilder: (ctx, i) {
                      final item = Map<String, dynamic>.from(_items[i] as Map);
                      final status = item['status']?.toString();
                      return _procSectionCard(children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                  (item['material_name'] ?? '样品申请')
                                      .toString(),
                                  style: const TextStyle(
                                      color: Color(0xFFE8E6E1),
                                      fontWeight: FontWeight.w600,
                                      fontSize: 15)),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                color: _statusColor(status)
                                    .withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(_statusText(status),
                                  style: TextStyle(
                                      color: _statusColor(status),
                                      fontSize: 10)),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        _procKv('ID', (item['id'] ?? '-').toString()),
                        if (item['supplier'] != null)
                          _procKv('供应商', item['supplier'].toString()),
                        if (item['quantity'] != null)
                          _procKv('数量', item['quantity'].toString()),
                        if (item['remark'] != null)
                          _procKv('备注', item['remark'].toString()),
                        if (item['created_at'] != null)
                          _procKv('创建时间', item['created_at'].toString()),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            if (status == 'pending')
                              TextButton.icon(
                                onPressed: () =>
                                    _approve(item['id']?.toString() ?? ''),
                                icon: const Icon(Icons.check, size: 16),
                                label: const Text('批准'),
                              ),
                          ],
                        ),
                      ]);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFFC9973B),
        foregroundColor: Colors.black,
        onPressed: _create,
        child: const Icon(Icons.add),
      ),
    );
  }
}
