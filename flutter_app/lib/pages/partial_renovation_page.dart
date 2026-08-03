import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// F42 局部焕新页面（v1.5.0）
class PartialRenovationPage extends StatefulWidget {
  final String projectId;
  const PartialRenovationPage({super.key, required this.projectId});

  @override
  State<PartialRenovationPage> createState() => _PartialRenovationPageState();
}

class _PartialRenovationPageState extends State<PartialRenovationPage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _templates = [];
  List<dynamic> _plans = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadAll();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final templatesResult = await _api.partialListTemplates();
    final plansResult = await _api.partialListPlans(widget.projectId);
    if (!mounted) return;
    if (templatesResult.isSuccess && plansResult.isSuccess) {
      setState(() {
        _templates = _extractList(templatesResult.data, 'templates');
        _plans = _extractList(plansResult.data, 'plans');
        _loading = false;
      });
    } else {
      setState(() {
        _error = (templatesResult.error ?? plansResult.error) ??
            '加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  List<dynamic> _extractList(dynamic data, String key) {
    if (data is List) return data;
    if (data is Map) return (data[key] as List?) ?? [];
    return [];
  }

  Future<void> _createPlan(
      String name, String scopeType, String budgetLevel) async {
    final result = await _api.partialCreatePlan({
      'project_id': widget.projectId,
      'name': name,
      'scope_type': scopeType,
      'budget_level': budgetLevel,
    });
    if (!mounted) return;
    if (result.isSuccess) {
      _toast('计划已创建');
      unawaited(_loadAll());
    } else {
      _toast('创建失败：${result.error}');
    }
  }

  String _scopeLabel(String? type) {
    switch (type) {
      case 'kitchen_refresh':
        return '厨房焕新';
      case 'bathroom_refresh':
        return '卫浴焕新';
      case 'wall_refresh':
        return '墙面刷新';
      case 'single_room':
        return '单空间改造';
      case 'full_renovation':
        return '全屋焕新';
      default:
        return type ?? '-';
    }
  }

  String _budgetLevelLabel(String? level) {
    switch (level) {
      case 'economic':
        return '经济';
      case 'comfort':
        return '舒适';
      case 'quality':
        return '品质';
      default:
        return level ?? '-';
    }
  }

  String _planStatusLabel(String? status) {
    switch (status) {
      case 'draft':
        return '草稿';
      case 'active':
        return '进行中';
      case 'completed':
        return '已完成';
      default:
        return status ?? '草稿';
    }
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
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('局部焕新'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSub(context),
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '焕新模板'),
            Tab(text: '我的计划'),
          ],
        ),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 110);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadAll);
    }
    return TabBarView(
      controller: _tabController,
      children: [
        _buildTemplatesTab(),
        _buildPlansTab(),
      ],
    );
  }

  // ── Tab1: 焕新模板 ──

  Widget _buildTemplatesTab() {
    if (_templates.isEmpty) {
      return _buildEmpty('暂无焕新模板');
    }
    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      onRefresh: _loadAll,
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: _templates.length,
        itemBuilder: (context, index) {
          final template = _templates[index] as Map<String, dynamic>;
          return _buildTemplateCard(template);
        },
      ),
    );
  }

  Widget _buildTemplateCard(Map<String, dynamic> template) {
    final scopeType = (template['scope_type'] ?? '').toString();
    final budgetRange =
        (template['budget_range'] as Map?) ?? <String, dynamic>{};
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.construction,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    template['name'] ?? scopeType,
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Text('${template['duration_days'] ?? '-'} 天',
                    style: TextStyle(
                        color: SuokeDesignTokens.textSub(context),
                        fontSize: 12)),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _buildBudgetTag('经济', budgetRange['economic']),
                _buildBudgetTag('舒适', budgetRange['comfort']),
                _buildBudgetTag('品质', budgetRange['quality']),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 48,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.accent,
                  side: BorderSide(
                      color: SuokeDesignTokens.borderClr(context)),
                ),
                onPressed: () => _showCreatePlanDialog(scopeType),
                icon: const Icon(Icons.playlist_add, size: 16),
                label: const Text('以此创建计划',
                    style: TextStyle(fontSize: 13)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBudgetTag(String label, dynamic range) {
    final text = range is List && range.length >= 2
        ? '$label ${range[0]}-${range[1]}万'
        : '$label -';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.accent.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(text,
          style: const TextStyle(
              color: SuokeDesignTokens.accent, fontSize: 12)),
    );
  }

  // ── Tab2: 我的计划 ──

  Widget _buildPlansTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bg(context),
                  ),
                  onPressed: _showCreatePlanDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建计划'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.text(context),
                  side: BorderSide(
                      color: SuokeDesignTokens.borderClr(context)),
                ),
                onPressed: _loadAll,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: _plans.isEmpty
              ? _buildEmpty('暂无局部焕新计划')
              : RefreshIndicator(
                  color: SuokeDesignTokens.accent,
                  onRefresh: _loadAll,
                  child: ListView.builder(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: _plans.length,
                    itemBuilder: (context, index) {
                      final plan =
                          _plans[index] as Map<String, dynamic>;
                      return _buildPlanCard(plan);
                    },
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildPlanCard(Map<String, dynamic> plan) {
    final status = (plan['status'] ?? '').toString();
    final budgetLower = (plan['budget_lower'] as num?)?.toDouble();
    final budgetUpper = (plan['budget_upper'] as num?)?.toDouble();
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.event_note,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    plan['name'] ?? '未命名计划',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _planStatusLabel(status),
                    style: const TextStyle(
                        color: SuokeDesignTokens.accent, fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('范围',
                    _scopeLabel(plan['scope_type']?.toString())),
                _buildInfoChip('档位',
                    _budgetLevelLabel(plan['budget_level']?.toString())),
                _buildInfoChip('工期', '${plan['duration_days'] ?? '-'} 天'),
                _buildInfoChip(
                    '预算',
                    budgetLower != null && budgetUpper != null
                        ? '$budgetLower - $budgetUpper 万'
                        : '-'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoChip(String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label：',
            style: TextStyle(
                color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        Text(value,
            style:
                TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
      ],
    );
  }

  Widget _buildEmpty(String message) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.inbox_outlined,
              size: 56, color: SuokeDesignTokens.textSub(context)),
          const SizedBox(height: 12),
          Text(message,
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 14)),
        ],
      ),
    );
  }

  // ── 创建计划对话框 ──

  void _showCreatePlanDialog([String? presetScopeType]) {
    if (_templates.isEmpty) {
      _toast('暂无焕新模板，无法创建计划');
      return;
    }
    final nameCtrl = TextEditingController();
    String scopeType = presetScopeType ??
        ((_templates.first as Map)['scope_type'] ?? '').toString();
    String budgetLevel = 'comfort';
    const budgetLevels = [
      ('economic', '经济'),
      ('comfort', '舒适'),
      ('quality', '品质'),
    ];
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text('创建局部焕新计划',
              style: TextStyle(color: SuokeDesignTokens.text(context))),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('计划名称'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: scopeType,
                  dropdownColor: SuokeDesignTokens.card(context),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('改造范围'),
                  items: _templates
                      .map((t) => DropdownMenuItem(
                            value: ((t as Map)['scope_type'] ?? '')
                                .toString(),
                            child: Text(
                                (t['name'] ?? t['scope_type']).toString(),
                                style: TextStyle(
                                    color:
                                        SuokeDesignTokens.text(context))),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setDialogState(() => scopeType = v);
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: budgetLevel,
                  dropdownColor: SuokeDesignTokens.card(context),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('预算档位'),
                  items: budgetLevels
                      .map((t) => DropdownMenuItem(
                            value: t.$1,
                            child: Text(t.$2,
                                style: TextStyle(
                                    color:
                                        SuokeDesignTokens.text(context))),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setDialogState(() => budgetLevel = v);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('取消',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context))),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: SuokeDesignTokens.accent,
                  foregroundColor: SuokeDesignTokens.bg(context)),
              onPressed: () {
                final name = nameCtrl.text.trim();
                if (name.isEmpty) {
                  _toast('请输入计划名称');
                  return;
                }
                if (scopeType.isEmpty) {
                  _toast('请选择改造范围');
                  return;
                }
                Navigator.pop(ctx);
                _createPlan(name, scopeType, budgetLevel);
              },
              child: const Text('创建'),
            ),
          ],
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
