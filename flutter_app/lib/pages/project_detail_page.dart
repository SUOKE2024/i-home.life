import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import 'budget_page.dart';
import 'construction_page.dart';
import 'settlement_page.dart';
import 'design_deepening_page.dart';
import 'procurement_enhanced_page.dart';
import 'ar_scan_page.dart';
import 'elderly_adaptation_page.dart';
import 'partial_renovation_page.dart';
import 'escrow_trustee_page.dart';
import 'eco_materials_page.dart';
import 'solution_first_page.dart';
import 'ecosystem_page.dart';
import 'ai_qa_page.dart';

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
      case 'active':
        // 后端施工中状态为 active，兼容旧值 in_progress
        return '施工中';
      case 'completed':
        return '已完成';
      case 'cancelled':
        return '已取消';
      case 'draft':
      default:
        return '草稿';
    }
  }

  Color _statusColor(String s) {
    switch (s) {
      case 'in_progress':
      case 'active':
        return const Color(0xFF4A9E6E);
      case 'completed':
        return const Color(0xFF5B8EC4);
      case 'cancelled':
        return const Color(0xFFC0392B);
      default:
        return SuokeDesignTokens.textSub(context);
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
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('删除项目', style: TextStyle(color: SuokeDesignTokens.text(context))),
        content: Text('确定要删除该项目吗？此操作不可恢复。',
            style: TextStyle(color: SuokeDesignTokens.textSub(context))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text('取消', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: SuokeDesignTokens.danger),
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
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        title: const Text('项目详情',
            style: TextStyle(fontWeight: FontWeight.bold, fontFamily: 'DM Sans')),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context, false),
        ),
      ),
      body: _loading
          ? const LoadingSkeleton(itemHeight: 110)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: _project == null
                      ? ListView(
                          children: [
                            const SizedBox(height: 120),
                            Center(
                              child: Text('项目不存在或已被删除',
                                  style: TextStyle(color: SuokeDesignTokens.textSub(context))),
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
                        _buildV150FeaturesEntry(),
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
      color: SuokeDesignTokens.card(context),
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
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: SuokeDesignTokens.text(context),
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
        Icon(icon, size: 16, color: SuokeDesignTokens.textSub(context)),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text,
              style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13),
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
        style: TextStyle(
          fontSize: 15,
          fontWeight: FontWeight.w600,
          color: SuokeDesignTokens.text(context),
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
              color: SuokeDesignTokens.card(context),
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
                            color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            '${floor['floor_number'] ?? 1}',
                            style: const TextStyle(
                                color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            (floor['name'] ?? '楼层').toString(),
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: SuokeDesignTokens.text(context),
                            ),
                          ),
                        ),
                        if (floor['area'] != null)
                          Text('${floor['area']}㎡',
                              style: TextStyle(
                                  color: SuokeDesignTokens.textSub(context), fontSize: 12)),
                      ],
                    ),
                    if (rooms.isEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Text('暂无房间',
                            style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
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
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            (room['name'] ?? '-').toString(),
            style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13),
          ),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.accent.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              _roomTypeText((room['room_type'] ?? '').toString()),
              style: const TextStyle(color: SuokeDesignTokens.accent, fontSize: 10),
            ),
          ),
          if (room['area'] != null) ...[
            const SizedBox(width: 6),
            Text('${room['area']}㎡',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
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
            color: SuokeDesignTokens.card(context),
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
        style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(
          children: [
            if (mat['brand'] != null)
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: Text((mat['brand']).toString(),
                    style: const TextStyle(color: SuokeDesignTokens.accent, fontSize: 11)),
              ),
            Text('x$qty ${mat['unit'] ?? ''}',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
            const SizedBox(width: 8),
            if (status.isNotEmpty)
              Text(_bomStatusText(status),
                  style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
          ],
        ),
      ),
      trailing: Text(
        '¥${((total ?? unitPrice ?? 0) as num).toDouble().toStringAsFixed(2)}',
        style: const TextStyle(
            color: SuokeDesignTokens.accent, fontWeight: FontWeight.bold, fontSize: 14),
      ),
    );
  }

  Widget _buildDesignDeepeningEntry() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('设计深化'),
        Card(
          color: SuokeDesignTokens.card(context),
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
                color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.design_services_outlined,
                  color: SuokeDesignTokens.accent, size: 22),
            ),
            title: Text('设计深化（厨卫水电/硬装/门窗防水/智家/场景）',
                style: TextStyle(
                    color: SuokeDesignTokens.text(context),
                    fontSize: 14,
                    fontWeight: FontWeight.w600)),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('F18 / F21 / F23 / F31 / F32',
                  style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
            ),
            trailing: Icon(Icons.chevron_right, color: SuokeDesignTokens.textSub(context)),
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
          color: SuokeDesignTokens.card(context),
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
                color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.shopping_cart_checkout,
                  color: SuokeDesignTokens.accent, size: 22),
            ),
            title: Text('采购增强（比价/托管支付/物流/样品）',
                style: TextStyle(
                    color: SuokeDesignTokens.text(context),
                    fontSize: 14,
                    fontWeight: FontWeight.w600)),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('F33 / F34',
                  style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
            ),
            trailing: Icon(Icons.chevron_right, color: SuokeDesignTokens.textSub(context)),
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

  Widget _buildV150FeaturesEntry() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('新增功能（v1.5.0）'),
        Card(
          color: SuokeDesignTokens.card(context),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: Color(0xFF1E1E32)),
          ),
          child: Column(
            children: [
              _v150FeatureTile(
                'F41 适老改造',
                '无障碍方案与合规校验（GB 50763-2012）',
                Icons.elderly,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) =>
                          ElderlyAdaptationPage(projectId: widget.projectId)),
                ),
              ),
              const Divider(height: 1, indent: 62),
              _v150FeatureTile(
                'F42 局部焕新',
                '模板化焕新计划与预算档位',
                Icons.construction,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) =>
                          PartialRenovationPage(projectId: widget.projectId)),
                ),
              ),
              const Divider(height: 1, indent: 62),
              _v150FeatureTile(
                'F43 资金托管',
                '银行存管/第三方监管与双向确认放款',
                Icons.savings_outlined,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) =>
                          EscrowTrusteePage(projectId: widget.projectId)),
                ),
              ),
              const Divider(height: 1, indent: 62),
              _v150FeatureTile(
                'F44 环保材料',
                'ENF/E0/E1 等级与环保合规校验',
                Icons.eco_outlined,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) =>
                          EcoMaterialsPage(projectId: widget.projectId)),
                ),
              ),
              const Divider(height: 1, indent: 62),
              _v150FeatureTile(
                'F45 方案前置',
                '3 套布局方案 + 预算区间生成',
                Icons.auto_awesome,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) =>
                          SolutionFirstPage(projectId: widget.projectId)),
                ),
              ),
              const Divider(height: 1, indent: 62),
              _v150FeatureTile(
                'F46 生态桥接',
                '智能家居生态配置状态与优先级',
                Icons.link,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) =>
                          EcosystemPage(projectId: widget.projectId)),
                ),
              ),
              const Divider(height: 1, indent: 62),
              _v150FeatureTile(
                'F47 AI 装修问答',
                '知识库问答搜索与 FAQ',
                Icons.smart_toy_outlined,
                () => Navigator.push(
                  context,
                  MaterialPageRoute(
                      builder: (_) => AIQAPage(projectId: widget.projectId)),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _v150FeatureTile(
    String title,
    String subtitle,
    IconData icon,
    VoidCallback onTap,
  ) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      leading: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, color: SuokeDesignTokens.accent, size: 22),
      ),
      title: Text(
        title,
        style: TextStyle(
            color: SuokeDesignTokens.text(context),
            fontSize: 14,
            fontWeight: FontWeight.w600),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Text(subtitle,
            style:
                TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 11)),
      ),
      trailing: Icon(Icons.chevron_right, color: SuokeDesignTokens.textSub(context)),
      onTap: onTap,
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
                  MaterialPageRoute(
                    builder: (_) => ARScanPage(projectId: widget.projectId),
                  ),
                ),
                icon: const Icon(Icons.straighten, size: 18),
                label: const Text('AR 空间测量'),
              ),
            ),
            const SizedBox(width: 12),
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
          foregroundColor: SuokeDesignTokens.danger,
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
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1E1E32)),
      ),
      child: Center(
        child: Text(text, style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
      ),
    );
  }
}
