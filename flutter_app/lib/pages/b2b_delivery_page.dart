import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../widgets/empty_state.dart';

/// B2B 装企交付页：交付单创建 + 列表 + 详情 + 状态流转（v1.4.x）
///
/// API 对齐 app/api/b2b_delivery.py：
///   POST /b2b/delivery（创建，含 async_mode）
///   GET  /b2b/delivery（列表）
///   GET  /b2b/delivery/{id}（详情整包快照）
///   PUT  /b2b/delivery/{id}/status（状态流转）
class B2BDeliveryPage extends StatefulWidget {
  /// 可选：关联项目（报价走项目真实预算）
  final String? projectId;
  const B2BDeliveryPage({super.key, this.projectId});

  @override
  State<B2BDeliveryPage> createState() => _B2BDeliveryPageState();
}

// 风格（对齐后端 DeliveryRequest.style）
const _styleOptions = {
  'modern': '现代简约',
  'nordic': '北欧',
  'japanese': '日式侘寂',
  'luxury': '轻奢',
  'chinese': '新中式',
};

// 交付单状态标签
const _statusLabels = {
  'generating': '生成中',
  'draft': '草稿',
  'quoted': '已报价',
  'accepted': '已签约',
  'in_construction': '施工中',
  'completed': '已完成',
  'cancelled': '已取消',
};

// 状态流转操作（对齐后端 _ALLOWED_TRANSITIONS）
const _nextActions = {
  'generating': <(String, String)>[],
  'draft': [('quoted', '确认报价'), ('cancelled', '取消')],
  'quoted': [('accepted', '签约'), ('cancelled', '取消')],
  'accepted': [('in_construction', '开工'), ('cancelled', '取消')],
  'in_construction': [('completed', '完工'), ('cancelled', '取消')],
  'completed': <(String, String)>[],
  'cancelled': <(String, String)>[],
};

class _B2BDeliveryPageState extends State<B2BDeliveryPage> {
  final ApiClient _api = ApiClient();

  // 列表
  List<dynamic> _orders = [];
  bool _loading = true;
  String? _error;

  // 创建表单
  final _nameCtrl = TextEditingController(text: '整装交付');
  final _areaCtrl = TextEditingController(text: '100');
  final _budgetCtrl = TextEditingController(text: '200000');
  final _roomsCtrl = TextEditingController(text: '客厅,卧室,厨房,卫生间');
  final _reqCtrl = TextEditingController();
  String _style = 'modern';
  bool _asyncMode = false;
  bool _submitting = false;
  String? _formError;

  // 详情
  String? _expandedId;
  Map<String, dynamic>? _detail;
  String? _detailOrderId;
  String? _detailError;
  bool _statusBusy = false;

  @override
  void initState() {
    super.initState();
    _loadOrders();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _areaCtrl.dispose();
    _budgetCtrl.dispose();
    _roomsCtrl.dispose();
    _reqCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadOrders() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.b2bListDeliveries();
    if (!mounted) return;
    if (result.isSuccess && result.data is List) {
      setState(() {
        _orders = result.data as List;
        _loading = false;
      });
    } else {
      setState(() {
        _error = result.error ?? '加载交付单失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  Future<void> _createOrder() async {
    if (_submitting) return;
    final area = double.tryParse(_areaCtrl.text.trim());
    if (area == null || area <= 0) {
      _toast('请填写有效的建筑面积（>0 平方米）');
      return;
    }
    final budget = double.tryParse(_budgetCtrl.text.trim());
    final name = _nameCtrl.text.trim().isEmpty ? '整装交付' : _nameCtrl.text.trim();
    final rooms = _roomsCtrl.text.trim().isEmpty
        ? '客厅,卧室,厨房,卫生间'
        : _roomsCtrl.text.trim();

    setState(() {
      _submitting = true;
      _formError = null;
    });
    final result = await _api.b2bCreateDelivery({
      'name': name,
      'area': area,
      'style': _style,
      'budget': budget ?? 0,
      'requirements': _reqCtrl.text.trim(),
      'rooms': rooms,
      if (widget.projectId != null) 'project_id': widget.projectId,
      'async_mode': _asyncMode,
    });
    if (!mounted) return;
    setState(() => _submitting = false);
    if (!result.isSuccess) {
      // 后端 403（功能未启用）等真实错误文案诚实展示
      setState(() => _formError = result.error ?? '创建交付单失败，请稍后重试');
      return;
    }
    _toast('交付单已创建');
    _reqCtrl.clear();
    final data = result.data is Map ? result.data as Map : null;
    final orderId = data?['delivery_order_id']?.toString();
    await _loadOrders();
    if (orderId != null) {
      setState(() {
        _expandedId = orderId;
        _detail = null;
        _detailOrderId = null;
        _detailError = null;
      });
      if (_asyncMode) {
        unawaited(_pollUntilReady(orderId));
      } else {
        unawaited(_loadDetail(orderId));
      }
    }
  }

  /// 异步生成：轮询详情直至非 generating（对齐 Web 端 pollUntilReady）
  Future<void> _pollUntilReady(String orderId) async {
    for (var i = 0; i < 30; i++) {
      await Future.delayed(const Duration(seconds: 1));
      if (!mounted) return;
      final result = await _api.b2bGetDelivery(orderId);
      if (!result.isSuccess || result.data is! Map) continue;
      final status = (result.data as Map)['status']?.toString();
      if (status != 'generating') break;
    }
    if (!mounted) return;
    await _loadDetail(orderId);
    await _loadOrders();
  }

  Future<void> _loadDetail(String orderId) async {
    setState(() {
      _detailError = null;
    });
    final result = await _api.b2bGetDelivery(orderId);
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      setState(() {
        _detail = result.data as Map<String, dynamic>;
        _detailOrderId = orderId;
      });
    } else {
      setState(() {
        _detailError = result.error ?? '加载详情失败';
      });
    }
  }

  Future<void> _transition(String orderId, String status) async {
    if (_statusBusy) return;
    setState(() => _statusBusy = true);
    final result = await _api.b2bUpdateDeliveryStatus(orderId, status);
    if (!mounted) return;
    setState(() => _statusBusy = false);
    if (!result.isSuccess) {
      _toast('状态流转失败：${result.error}');
      return;
    }
    _toast('状态已更新');
    await _loadOrders();
    if (_expandedId == orderId) await _loadDetail(orderId);
  }

  void _toggleDetail(String orderId) {
    if (_expandedId == orderId) {
      setState(() {
        _expandedId = null;
        _detail = null;
        _detailOrderId = null;
        _detailError = null;
      });
      return;
    }
    setState(() {
      _expandedId = orderId;
      _detail = null;
      _detailOrderId = null;
      _detailError = null;
    });
    unawaited(_loadDetail(orderId));
  }

  void _toast(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(msg)));
    }
  }

  String _statusLabel(String s) => _statusLabels[s] ?? s;

  String _styleLabel(String s) => _styleOptions[s] ?? s;

  Color _statusColor(String s) {
    switch (s) {
      case 'generating':
        return SuokeDesignTokens.warning;
      case 'quoted':
        return SuokeDesignTokens.info;
      case 'accepted':
        return SuokeDesignTokens.accent;
      case 'in_construction':
        return SuokeDesignTokens.teal;
      case 'completed':
        return SuokeDesignTokens.success;
      case 'cancelled':
        return SuokeDesignTokens.danger;
      default:
        return SuokeDesignTokens.textSub(context);
    }
  }

  String _formatInt(num value) {
    return value.toInt().toString().replaceAllMapped(
        RegExp(r'(\d)(?=(\d{3})+$)'), (m) => '${m[1]},');
  }

  String _formatTime(String iso) {
    if (iso.isEmpty) return '';
    final dt = DateTime.tryParse(iso);
    if (dt == null) return '';
    final local = dt.toLocal();
    String two(int n) => n.toString().padLeft(2, '0');
    return '${local.year}-${two(local.month)}-${two(local.day)} '
        '${two(local.hour)}:${two(local.minute)}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('B2B 装企交付'),
      ),
      body: _loading
          ? const LoadingSkeleton(itemHeight: 110)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadOrders)
              : RefreshIndicator(
                  color: SuokeDesignTokens.accent,
                  onRefresh: _loadOrders,
                  child: ListView(
                    padding: const EdgeInsets.all(12),
                    children: [
                      _buildCreateForm(),
                      const SizedBox(height: 16),
                      _sectionTitle('我的交付单（${_orders.length}）'),
                      if (_orders.isEmpty)
                        const EmptyStateWidget(
                          icon: Icons.inventory_2_outlined,
                          title: '暂无交付单',
                          description: '先在上方填写信息，生成一单「设计方案 + 报价 + 施工计划」整包交付',
                        )
                      else
                        ..._orders.map((o) => _buildOrderCard(
                            Map<String, dynamic>.from(o as Map))),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
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
        ),
      ),
    );
  }

  // ── 创建表单 ──

  Widget _buildCreateForm() {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.inventory_2_outlined,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('创建交付单',
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 15,
                          fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text('一次生成设计方案 + 报价 + 施工计划整包交付',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12)),
            if (widget.projectId != null) ...[
              const SizedBox(height: 8),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: SuokeDesignTokens.accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text('已关联当前项目（报价走项目真实预算）',
                    style: TextStyle(
                        color: SuokeDesignTokens.accent, fontSize: 12)),
              ),
            ],
            const SizedBox(height: 12),
            TextField(
              controller: _nameCtrl,
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              maxLength: 200,
              decoration: _inputDecoration('交付名称'),
            ),
            const SizedBox(height: 4),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: TextField(
                    controller: _areaCtrl,
                    keyboardType: const TextInputType.numberWithOptions(
                        decimal: true),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('建筑面积（㎡，必填）'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _style,
                    dropdownColor: SuokeDesignTokens.card(context),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('装修风格'),
                    items: [
                      for (final e in _styleOptions.entries)
                        DropdownMenuItem(
                            value: e.key, child: Text(e.value)),
                    ],
                    onChanged: (v) {
                      if (v != null) setState(() => _style = v);
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _budgetCtrl,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              decoration: _inputDecoration('业主预算（元，0 = 不限定）'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _roomsCtrl,
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              maxLength: 200,
              decoration: _inputDecoration('房间列表（逗号分隔）'),
            ),
            TextField(
              controller: _reqCtrl,
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              maxLines: 3,
              maxLength: 2000,
              decoration: _inputDecoration('设计需求补充（如：主卧带衣帽间）'),
            ),
            SwitchListTile(
              value: _asyncMode,
              onChanged: (v) => setState(() => _asyncMode = v),
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text('异步生成（立即返回，后台填充整包）',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 13)),
            ),
            if (_formError != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Text(_formError!,
                    style: const TextStyle(
                        color: SuokeDesignTokens.danger, fontSize: 13)),
              ),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _submitting ? null : _createOrder,
                icon: _submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.rocket_launch_outlined, size: 18),
                label: Text(_submitting ? '生成中...' : '生成交付包'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── 交付单列表卡片 ──

  Widget _buildOrderCard(Map<String, dynamic> order) {
    final orderId = (order['delivery_order_id'] ?? '').toString();
    final status = (order['status'] ?? 'draft').toString();
    final area = (order['area'] as num?)?.toDouble();
    final style = (order['style'] ?? '').toString();
    final created = (order['created_at'] ?? '').toString();
    final expanded = _expandedId == orderId;
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Column(
        children: [
          ListTile(
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
            title: Text(
              (order['name'] ?? '未命名交付单').toString(),
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 15,
                  fontWeight: FontWeight.w600),
            ),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '${area?.toStringAsFixed(1) ?? '-'}㎡ · ${_styleLabel(style)} · ${_formatTime(created)}',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12),
              ),
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _statusColor(status).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(_statusLabel(status),
                      style:
                          TextStyle(fontSize: 12, color: _statusColor(status))),
                ),
                const SizedBox(width: 4),
                Icon(expanded ? Icons.expand_less : Icons.expand_more,
                    color: SuokeDesignTokens.textSub(context)),
              ],
            ),
            onTap: () => _toggleDetail(orderId),
          ),
          if (expanded) _buildDetailBody(orderId),
        ],
      ),
    );
  }

  // ── 详情（整包快照） ──

  Widget _buildDetailBody(String orderId) {
    if (_detailOrderId != orderId) {
      if (_detailError != null) {
        return Padding(
          padding: const EdgeInsets.all(16),
          child: ErrorRetryWidget(
              message: _detailError!, onRetry: () => _loadDetail(orderId)),
        );
      }
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(
          child: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      );
    }
    final detail = _detail!;
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Divider(height: 1),
          const SizedBox(height: 10),
          if ((detail['summary'] ?? '').toString().isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(
                (detail['summary'] ?? '').toString(),
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13),
              ),
            ),
          _buildSources(detail['sources']),
          _buildBudget(detail['budget_estimate']),
          _buildConstruction(detail['construction_plan']),
          _buildProposals(detail['proposals']),
          _buildTransitions(detail),
        ],
      ),
    );
  }

  /// 数据来源诚实标注（design/budget/construction）
  Widget _buildSources(Object? sources) {
    if (sources is! Map || sources.isEmpty) return const SizedBox.shrink();
    String label(String key, String value) {
      switch (key) {
        case 'design':
          return value == 'llm' ? 'LLM 生成' : '确定性回退';
        case 'budget':
          return value == 'db' ? '项目真实预算' : '分档估算';
        case 'construction':
          return value == 'db' ? '项目真实排期' : '确定性估算';
        default:
          return value;
      }
    }

    final parts = sources.entries
        .map((e) => '${e.key}: ${label(e.key, e.value.toString())}')
        .join(' · ');
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text('来源 $parts',
          style: TextStyle(
              color: SuokeDesignTokens.textSub(context), fontSize: 11)),
    );
  }

  /// 报价档：db = 项目真实预算 / estimated = 分档估算
  Widget _buildBudget(Object? budgetObj) {
    if (budgetObj is! Map || budgetObj.isEmpty) return const SizedBox.shrink();
    final budget = Map<String, dynamic>.from(budgetObj);
    final source = (budget['source'] ?? '').toString();
    final children = <Widget>[
      _detailSectionTitle(
          '报价（${source == 'db' ? '项目真实预算' : '分档估算'}）'),
    ];
    if (source == 'db') {
      final total = (budget['total_estimated'] as num?)?.toDouble();
      final lineCount = (budget['line_count'] as num?)?.toInt();
      children.add(_detailText(
          total != null
              ? '总预算 ¥${_formatInt(total)}'
              : '总预算 -',
          bold: total != null));
      if (lineCount != null) {
        children.add(_detailText('$lineCount 项明细', sub: true));
      }
      final breakdown = budget['breakdown_by_category'];
      if (breakdown is Map && breakdown.isNotEmpty) {
        for (final e in breakdown.entries) {
          final v = (e.value as num?)?.toDouble();
          children.add(_detailText(
              '${e.key}：¥${v != null ? _formatInt(v) : '-'}',
              sub: true));
        }
      }
    } else {
      final tiers = budget['tiers'];
      final recommended = (budget['recommended_tier'] ?? '').toString();
      if (tiers is Map && tiers.isNotEmpty) {
        for (final e in tiers.entries) {
          final t = e.value is Map ? Map<String, dynamic>.from(e.value as Map) : null;
          if (t == null) continue;
          final total = (t['total_estimate'] as num?)?.toDouble();
          final isRec = e.key == recommended;
          children.add(Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  '${t['label'] ?? e.key}：¥${total != null ? _formatInt(total) : '-'}（${t['price_per_sqm'] ?? '-'}）',
                  style: TextStyle(
                    color: isRec
                        ? SuokeDesignTokens.accent
                        : SuokeDesignTokens.text(context),
                    fontSize: 13,
                    fontWeight: isRec ? FontWeight.w600 : FontWeight.normal,
                  ),
                ),
              ),
              if (isRec)
                const Text(' 推荐',
                    style: TextStyle(
                        color: SuokeDesignTokens.accent, fontSize: 12)),
            ],
          ));
          children.add(const SizedBox(height: 4));
        }
      }
      final breakdown = budget['breakdown_ratio'];
      if (breakdown is Map && breakdown.isNotEmpty) {
        children.add(const SizedBox(height: 4));
        final ratios = breakdown.entries
            .map((e) => '${e.key} ${(e.value as num?)?.toString() ?? '-'}')
            .join(' / ');
        children.add(_detailText(ratios, sub: true));
      }
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  /// 施工计划：总工期 + 分阶段
  Widget _buildConstruction(Object? planObj) {
    if (planObj is! Map || planObj.isEmpty) return const SizedBox.shrink();
    final plan = Map<String, dynamic>.from(planObj);
    final totalDays = (plan['total_days'] as num?)?.toInt();
    final bufferDays = (plan['buffer_days'] as num?)?.toInt();
    final phases = plan['phases'];
    final children = <Widget>[
      _detailSectionTitle('施工计划'),
      _detailText(
          totalDays != null ? '总工期 $totalDays 天' : '总工期 -',
          bold: true),
      if (bufferDays != null)
        _detailText('含 $bufferDays 天缓冲（≥10%）', sub: true),
      if (phases is List && phases.isNotEmpty) ...[
        const SizedBox(height: 6),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final p in phases)
              if (p is Map)
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.accent.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${p['name'] ?? '-'} ${(p['days'] as num?)?.toInt() ?? '-'}天',
                    style: const TextStyle(
                        color: SuokeDesignTokens.accent, fontSize: 12),
                  ),
                ),
          ],
        ),
      ],
      if ((plan['note'] ?? '').toString().isNotEmpty)
        Padding(
          padding: const EdgeInsets.only(top: 6),
          child: _detailText((plan['note'] ?? '').toString(), sub: true),
        ),
    ];
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  /// 设计备选方案列表
  Widget _buildProposals(Object? proposalsObj) {
    if (proposalsObj is! List || proposalsObj.isEmpty) {
      return const SizedBox.shrink();
    }
    final children = <Widget>[
      _detailSectionTitle('设计备选（${proposalsObj.length} 套）'),
    ];
    for (final p in proposalsObj) {
      if (p is! Map) continue;
      final highlights = p['highlights'];
      children.add(Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: SuokeDesignTokens.bg(context),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: SuokeDesignTokens.borderClr(context)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '方案${p['proposal_id'] ?? '-'} · ${p['title'] ?? '-'} · ¥${p['budget_cny'] != null ? _formatInt((p['budget_cny'] as num).toDouble()) : '-'}',
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 13,
                  fontWeight: FontWeight.w600),
            ),
            if ((p['layout_type'] ?? '').toString().isNotEmpty)
              _detailText((p['layout_type'] ?? '').toString(), sub: true),
            if (highlights is List && highlights.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  highlights.map((h) => h.toString()).join(' · '),
                  style: const TextStyle(
                      color: SuokeDesignTokens.accent, fontSize: 12),
                ),
              ),
            if ((p['rationale'] ?? '').toString().isNotEmpty)
              _detailText((p['rationale'] ?? '').toString(), sub: true),
          ],
        ),
      ));
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  /// 状态流转按钮
  Widget _buildTransitions(Map<String, dynamic> detail) {
    final status = (detail['status'] ?? 'draft').toString();
    final actions = _nextActions[status] ?? const <(String, String)>[];
    if (actions.isEmpty) return const SizedBox.shrink();
    final orderId = (detail['delivery_order_id'] ?? '').toString();
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final action in actions)
          if (action.$1 == 'cancelled')
            OutlinedButton(
              onPressed: _statusBusy ? null : () => _transition(orderId, action.$1),
              style: OutlinedButton.styleFrom(
                foregroundColor: SuokeDesignTokens.danger,
                side: const BorderSide(color: SuokeDesignTokens.danger),
              ),
              child: Text(action.$2),
            )
          else
            ElevatedButton(
              onPressed:
                  _statusBusy ? null : () => _transition(orderId, action.$1),
              child: Text(action.$2),
            ),
      ],
    );
  }

  Widget _detailSectionTitle(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 6, bottom: 6),
      child: Text(
        text,
        style: TextStyle(
            color: SuokeDesignTokens.text(context),
            fontSize: 14,
            fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _detailText(String text, {bool bold = false, bool sub = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Text(
        text,
        style: TextStyle(
          color: sub
              ? SuokeDesignTokens.textSub(context)
              : SuokeDesignTokens.text(context),
          fontSize: 13,
          fontWeight: bold ? FontWeight.w600 : FontWeight.normal,
        ),
      ),
    );
  }

  InputDecoration _inputDecoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: TextStyle(color: SuokeDesignTokens.textSub(context)),
      filled: true,
      fillColor: SuokeDesignTokens.bg(context),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: SuokeDesignTokens.accent),
      ),
    );
  }
}
