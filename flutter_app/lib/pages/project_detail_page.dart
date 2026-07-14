import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import 'budget_page.dart';
import 'construction_page.dart';
import 'settlement_page.dart';
import 'design_deepening_page.dart';
import 'procurement_enhanced_page.dart';

class ProjectDetailPage extends StatefulWidget {
  final String projectId;
  const ProjectDetailPage({super.key, required this.projectId});

  @override
  State<ProjectDetailPage> createState() => _ProjectDetailPageState();
}

class _ProjectDetailPageState extends State<ProjectDetailPage> {
  Map<String, dynamic>? _project;
  List<Map<String, dynamic>> _bomItems = [];
  bool _loading = true;
  bool _actionBusy = false;
  String? _error;

  static const _brand = Color(0xFFC9973B);
  static const _bg = Color(0xFF08080F);
  static const _card = Color(0xFF12121D);
  static const _textPrimary = Color(0xFFE8E6E1);
  static const _textSecondary = Color(0xFF8A8894);

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
    final projResult = await api.get('/projects/${widget.projectId}');
    if (projResult.isSuccess) {
      _project = Map<String, dynamic>.from(projResult.data as Map);
    } else {
      _project = null;
      _error = '项目加载失败，请检查网络后重试';
    }
    final bomResult = await api.getList('/materials/bom/${widget.projectId}');
    if (bomResult.isSuccess) {
      _bomItems = List<Map<String, dynamic>>.from(bomResult.data as List);
    } else {
      _bomItems = [];
    }
    if (mounted) setState(() => _loading = false);
  }

  String _statusText(String s) {
    switch (s) {
      case 'in_progress':
        return '施工中';
      case 'completed':
        return '已完成';
      case 'draft':
      default:
        return '草稿';
    }
  }

  Color _statusColor(String s) {
    switch (s) {
      case 'in_progress':
        return const Color(0xFF4A9E6E);
      case 'completed':
        return const Color(0xFF5B8EC4);
      default:
        return _textSecondary;
    }
  }

  String _roomTypeText(String t) {
    const map = {
      'bedroom': '卧室',
      'living_room': '客厅',
      'kitchen': '厨房',
      'bathroom': '卫生间',
      'balcony': '阳台',
      'dining': '餐厅',
      'study': '书房',
      'cloakroom': '衣帽间',
      'entryway': '玄关',
    };
    return map[t] ?? t;
  }

  String _bomStatusText(String s) {
    switch (s) {
      case 'pending':
        return '待采购';
      case 'ordered':
        return '已下单';
      case 'delivered':
        return '已到货';
      case 'installed':
        return '已安装';
      default:
        return s;
    }
  }

  Future<void> _generateBudget() async {
    if (_actionBusy) return;
    setState(() => _actionBusy = true);
    final api = ApiClient();
    final result = await api.post('/budgets/generate-from-bom/${widget.projectId}', {});
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('预算已生成')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('生成预算失败: ${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _actionBusy = false);
  }

  Future<void> _generateSettlement() async {
    if (_actionBusy) return;
    setState(() => _actionBusy = true);
    final api = ApiClient();
    final result = await api.post('/settlements/generate-from-budget/${widget.projectId}', {});
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('结算已生成')),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('生成结算失败: ${result.error}')),
        );
      }
    }
    if (mounted) setState(() => _actionBusy = false);
  }

  Future<void> _confirmDelete() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _card,
        title: const Text('删除项目', style: TextStyle(color: _textPrimary)),
        content: const Text('确定要删除该项目吗？此操作不可恢复。',
            style: TextStyle(color: _textSecondary)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消', style: TextStyle(color: _textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: const Color(0xFFD9534F)),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final api = ApiClient();
    final result = await api.delete('/projects/${widget.projectId}');
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('项目已删除')),
        );
        Navigator.pop(context, true);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('删除失败: ${result.error}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _card,
        title: const Text('项目详情',
            style: TextStyle(fontWeight: FontWeight.bold, fontFamily: 'DM Sans')),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context, false),
        ),
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 4, itemHeight: 110)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _project == null
                      ? ListView(
                          children: const [
                            SizedBox(height: 120),
                            Center(
                              child: Text('项目不存在或已被删除',
                                  style: TextStyle(color: _textSecondary)),
                            ),
                          ],
                        )
                      : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        _buildHeader(),
                        const SizedBox(height: 16),
                        _buildFloors(),
                        const SizedBox(height: 16),
                        _buildBom(),
                        const SizedBox(height: 16),
                        _buildDesignDeepeningEntry(),
                        const SizedBox(height: 12),
                        _buildProcurementEnhancedEntry(),
                        const SizedBox(height: 16),
                        _buildActions(),
                        const SizedBox(height: 12),
                        _buildDeleteButton(),
                        const SizedBox(height: 32),
                      ],
                    ),
            ),
    );
  }

  Widget _buildHeader() {
    final p = _project!;
    final status = (p['status'] ?? 'draft').toString();
    return Card(
      color: _card,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0xFF1E1E32)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    (p['name'] ?? '-').toString(),
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: _textPrimary,
                      fontFamily: 'DM Sans',
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _statusColor(status).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(100),
                  ),
                  child: Text(
                    _statusText(status),
                    style: TextStyle(fontSize: 12, color: _statusColor(status)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _infoRow(Icons.location_on_outlined,
                (p['address'] ?? '未填写地址').toString()),
            const SizedBox(height: 8),
            _infoRow(Icons.crop_free_outlined,
                '总面积 ${(p['total_area'] ?? '-')}㎡'),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(IconData icon, String text) {
    return Row(
      children: [
        Icon(icon, size: 16, color: _textSecondary),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text,
              style: const TextStyle(color: _textSecondary, fontSize: 13),
              overflow: TextOverflow.ellipsis),
        ),
      ],
    );
  }

  Widget _sectionTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 10),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: _textPrimary,
          fontFamily: 'DM Sans',
        ),
      ),
    );
  }

  Widget _buildFloors() {
    final floors = (_project!['floors'] as List?) ?? [];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('楼层与房间 (${floors.length})'),
        if (floors.isEmpty)
          _emptyHint('暂无楼层信息')
        else
          ...floors.map((f) {
            final floor = Map<String, dynamic>.from(f as Map);
            final rooms = (floor['rooms'] as List?) ?? [];
            return Card(
              color: _card,
              margin: const EdgeInsets.only(bottom: 10),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: const BorderSide(color: Color(0xFF1E1E32)),
              ),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 28,
                          height: 28,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: _brand.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '${floor['floor_number'] ?? 1}',
                            style: const TextStyle(
                                color: _brand, fontWeight: FontWeight.bold),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            (floor['name'] ?? '楼层').toString(),
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: _textPrimary,
                            ),
                          ),
                        ),
                        if (floor['area'] != null)
                          Text('${floor['area']}㎡',
                              style: const TextStyle(
                                  color: _textSecondary, fontSize: 12)),
                      ],
                    ),
                    if (rooms.isEmpty)
                      const Padding(
                        padding: EdgeInsets.only(top: 10),
                        child: Text('暂无房间',
                            style: TextStyle(color: _textSecondary, fontSize: 12)),
                      )
                    else
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: rooms.map((r) {
                            final room = Map<String, dynamic>.from(r as Map);
                            return _roomChip(room);
                          }).toList(),
                        ),
                      ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }

  Widget _roomChip(Map<String, dynamic> room) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D18),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF1E1E32)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            (room['name'] ?? '-').toString(),
            style: const TextStyle(color: _textPrimary, fontSize: 13),
          ),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: _brand.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              _roomTypeText((room['room_type'] ?? '').toString()),
              style: const TextStyle(color: _brand, fontSize: 10),
            ),
          ),
          if (room['area'] != null) ...[
            const SizedBox(width: 6),
            Text('${room['area']}㎡',
                style: const TextStyle(color: _textSecondary, fontSize: 11)),
          ],
        ],
      ),
    );
  }

  Widget _buildBom() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('物料清单 BOM (${_bomItems.length})'),
        if (_bomItems.isEmpty)
          _emptyHint('暂无物料，请先添加物料清单')
        else
          Card(
            color: _card,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: const BorderSide(color: Color(0xFF1E1E32)),
            ),
            child: Column(
              children: [
                ..._bomItems.map((item) => _bomTile(item)),
              ],
            ),
          ),
      ],
    );
  }

  Widget _bomTile(Map<String, dynamic> item) {
    final mat = item['material'] is Map
        ? Map<String, dynamic>.from(item['material'] as Map)
        : <String, dynamic>{};
    final qty = item['quantity'];
    final unitPrice = item['unit_price'];
    final total = item['total_price'];
    final status = (item['status'] ?? '').toString();
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      title: Text(
        (mat['name'] ?? '物料').toString(),
        style: const TextStyle(color: _textPrimary, fontSize: 14),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(
          children: [
            if (mat['brand'] != null)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Text((mat['brand']).toString(),
                    style: const TextStyle(color: _brand, fontSize: 11)),
              ),
            Text('x$qty ${mat['unit'] ?? ''}',
                style: const TextStyle(color: _textSecondary, fontSize: 12)),
            const SizedBox(width: 8),
            if (status.isNotEmpty)
              Text(_bomStatusText(status),
                  style: const TextStyle(color: _textSecondary, fontSize: 11)),
          ],
        ),
      ),
      trailing: Text(
        '¥${((total ?? unitPrice ?? 0) as num).toDouble().toStringAsFixed(2)}',
        style: const TextStyle(
            color: Color(0xFFE0AA4A), fontWeight: FontWeight.bold, fontSize: 14),
      ),
    );
  }

  Widget _buildDesignDeepeningEntry() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('设计深化'),
        Card(
          color: _card,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: Color(0xFF1E1E32)),
          ),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            leading: Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: _brand.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.design_services_outlined,
                  color: _brand, size: 22),
            ),
            title: const Text('设计深化（厨卫水电/硬装/门窗防水/智家/场景）',
                style: TextStyle(
                    color: _textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600)),
            subtitle: const Padding(
              padding: EdgeInsets.only(top: 4),
              child: Text('F18 / F21 / F23 / F31 / F32',
                  style: TextStyle(color: _textSecondary, fontSize: 11)),
            ),
            trailing: const Icon(Icons.chevron_right, color: _textSecondary),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) =>
                      DesignDeepeningPage(projectId: widget.projectId)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProcurementEnhancedEntry() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('采购增强'),
        Card(
          color: _card,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: Color(0xFF1E1E32)),
          ),
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            leading: Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: _brand.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.shopping_cart_checkout,
                  color: _brand, size: 22),
            ),
            title: const Text('采购增强（比价/托管支付/物流/样品）',
                style: TextStyle(
                    color: _textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600)),
            subtitle: const Padding(
              padding: EdgeInsets.only(top: 4),
              child: Text('F33 / F34',
                  style: TextStyle(color: _textSecondary, fontSize: 11)),
            ),
            trailing: const Icon(Icons.chevron_right, color: _textSecondary),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) =>
                      ProcurementEnhancedPage(projectId: widget.projectId)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('操作'),
        Row(
          children: [
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _actionBusy ? null : _generateBudget,
                icon: const Icon(Icons.request_quote_outlined, size: 18),
                label: const Text('生成预算'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: _actionBusy ? null : _generateSettlement,
                icon: const Icon(Icons.receipt_long_outlined, size: 18),
                label: const Text('生成结算'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => BudgetPage(projectId: widget.projectId)),
                ),
                icon: const Icon(Icons.account_balance_wallet, size: 18),
                label: const Text('预算管理'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => ConstructionPage(projectId: widget.projectId)),
                ),
                icon: const Icon(Icons.engineering, size: 18),
                label: const Text('施工管理'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => SettlementPage(projectId: widget.projectId)),
                ),
                icon: const Icon(Icons.receipt_long, size: 18),
                label: const Text('结算管理'),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildDeleteButton() {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: _confirmDelete,
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFFD9534F),
          side: const BorderSide(color: Color(0xFF3A1E1E)),
          padding: const EdgeInsets.symmetric(vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
        icon: const Icon(Icons.delete_outline, size: 18),
        label: const Text('删除项目'),
      ),
    );
  }

  Widget _emptyHint(String text) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 24),
      decoration: BoxDecoration(
        color: _card,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E1E32)),
      ),
      child: Center(
        child: Text(text, style: const TextStyle(color: _textSecondary, fontSize: 13)),
      ),
    );
  }
}
