import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// F44 环保材料页面（v1.5.0）
class EcoMaterialsPage extends StatefulWidget {
  final String projectId;
  const EcoMaterialsPage({super.key, required this.projectId});

  @override
  State<EcoMaterialsPage> createState() => _EcoMaterialsPageState();
}

class _EcoMaterialsPageState extends State<EcoMaterialsPage> {
  final ApiClient _api = ApiClient();

  String? _selectedGrade;
  List<dynamic> _materials = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadMaterials();
  }

  Future<void> _loadMaterials() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.ecoListMaterials(grade: _selectedGrade);
    if (!mounted) return;
    if (result.isSuccess) {
      setState(() {
        _materials = _extractList(result.data, 'materials');
        _loading = false;
      });
    } else {
      setState(() {
        _error = result.error ?? '加载失败，请检查网络后重试';
        _loading = false;
      });
    }
  }

  List<dynamic> _extractList(dynamic data, String key) {
    if (data is List) return data;
    if (data is Map) return (data[key] as List?) ?? [];
    return [];
  }

  Future<void> _assignCert(Map<String, dynamic> body) async {
    final result = await _api.ecoAssignCert(body);
    if (!mounted) return;
    if (result.isSuccess) {
      _toast('认证标签已分配');
      unawaited(_loadMaterials());
    } else {
      _toast('分配失败：${result.error}');
    }
  }

  Future<void> _validateMaterials(String input) async {
    final ids = input
        .split(RegExp(r'[,，\s]+'))
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    if (ids.isEmpty) {
      _toast('请输入材料 ID（多个用逗号分隔）');
      return;
    }
    final result = await _api.ecoValidate(ids);
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      final data = result.data as Map<String, dynamic>;
      _showValidateReport(data);
    } else {
      _toast('校验失败：${result.error}');
    }
  }

  void _showValidateReport(Map<String, dynamic> data) {
    final items = (data['items'] as List?) ?? [];
    final compliantCount = data['compliant_count'] ?? 0;
    final total = data['total'] ?? 0;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('环保合规校验报告',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        content: SizedBox(
          width: double.maxFinite,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('通过 $compliantCount / $total 项（HC-003 环保等级硬约束）',
                  style: TextStyle(
                      color: SuokeDesignTokens.text(context),
                      fontWeight: FontWeight.w600)),
              const SizedBox(height: 12),
              Flexible(
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: items.length,
                  itemBuilder: (context, index) {
                    final item = items[index] as Map<String, dynamic>;
                    final compliant = item['compliant'] == true;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            compliant
                                ? Icons.check_circle_outline
                                : Icons.cancel_outlined,
                            size: 18,
                            color: compliant
                                ? SuokeDesignTokens.success
                                : SuokeDesignTokens.danger,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item['material_name']?.toString() ?? '-',
                                  style: TextStyle(
                                      color:
                                          SuokeDesignTokens.text(context),
                                      fontSize: 14),
                                ),
                                Text(
                                  '${item['eco_grade'] ?? '-'} / ${item['certification'] ?? '-'}',
                                  style: TextStyle(
                                      color: SuokeDesignTokens.textSub(
                                          context),
                                      fontSize: 12),
                                ),
                                Text(
                                  item['note']?.toString() ?? '',
                                  style: TextStyle(
                                      color: compliant
                                          ? SuokeDesignTokens.success
                                          : SuokeDesignTokens.danger,
                                      fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('关闭',
                style:
                    TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
        ],
      ),
    );
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
        title: const Text('环保材料'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 100);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadMaterials);
    }
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
          child: Row(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildGradeChip('全部', null),
                      const SizedBox(width: 8),
                      _buildGradeChip('ENF', 'ENF'),
                      const SizedBox(width: 8),
                      _buildGradeChip('E0', 'E0'),
                      const SizedBox(width: 8),
                      _buildGradeChip('E1', 'E1'),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              Expanded(
                child: ElevatedButton.icon(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: SuokeDesignTokens.accent,
                    foregroundColor: SuokeDesignTokens.bg(context),
                  ),
                  onPressed: _showAssignCertDialog,
                  icon: const Icon(Icons.verified_outlined, size: 18),
                  label: const Text('分配认证'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: SuokeDesignTokens.text(context),
                    side: BorderSide(
                        color: SuokeDesignTokens.borderClr(context)),
                  ),
                  onPressed: _showValidateDialog,
                  icon: const Icon(Icons.fact_check_outlined, size: 18),
                  label: const Text('合规校验'),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            color: SuokeDesignTokens.accent,
            onRefresh: _loadMaterials,
            child: _materials.isEmpty
                ? ListView(
                    children: [
                      const SizedBox(height: 120),
                      Center(
                        child: Column(
                          children: [
                            Icon(Icons.eco_outlined,
                                size: 64,
                                color: SuokeDesignTokens.textSub(context)),
                            const SizedBox(height: 16),
                            Text('暂无环保材料',
                                style: TextStyle(
                                    fontSize: 16,
                                    color: SuokeDesignTokens.textSub(
                                        context))),
                          ],
                        ),
                      ),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: _materials.length,
                    itemBuilder: (context, index) {
                      final material =
                          _materials[index] as Map<String, dynamic>;
                      return _buildMaterialCard(material);
                    },
                  ),
          ),
        ),
      ],
    );
  }

  Widget _buildGradeChip(String label, String? grade) {
    final selected = _selectedGrade == grade;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      selectedColor: SuokeDesignTokens.accentGlow,
      labelStyle: TextStyle(
        color: selected
            ? SuokeDesignTokens.accent
            : SuokeDesignTokens.textSub(context),
        fontSize: 13,
      ),
      side: BorderSide(
        color: selected
            ? SuokeDesignTokens.accent
            : SuokeDesignTokens.borderClr(context),
      ),
      onSelected: (_) {
        setState(() => _selectedGrade = grade);
        unawaited(_loadMaterials());
      },
    );
  }

  Widget _buildMaterialCard(Map<String, dynamic> material) {
    final grade = (material['eco_grade'] ?? '').toString();
    final price = (material['unit_price'] as num?)?.toDouble();
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
                const Icon(Icons.eco, color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    material['material_name'] ?? '未命名材料',
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
                    color: SuokeDesignTokens.success.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    grade,
                    style: const TextStyle(
                        color: SuokeDesignTokens.success, fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('SKU', material['sku']?.toString() ?? '-'),
                _buildInfoChip(
                    '认证', material['certification']?.toString() ?? '-'),
                _buildInfoChip(
                    '单价',
                    price != null
                        ? '¥${price.toStringAsFixed(2)}'
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

  // ── 分配认证对话框 ──

  void _showAssignCertDialog() {
    final materialIdCtrl = TextEditingController();
    final certificationCtrl = TextEditingController(text: '无认证');
    String ecoGrade = 'ENF';
    String source = 'third_party';
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text('分配环保认证标签',
              style: TextStyle(color: SuokeDesignTokens.text(context))),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: materialIdCtrl,
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('材料 ID'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: ecoGrade,
                  dropdownColor: SuokeDesignTokens.card(context),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('环保等级'),
                  items: const [
                    DropdownMenuItem(value: 'ENF', child: Text('ENF（无醛添加）')),
                    DropdownMenuItem(value: 'E0', child: Text('E0（低醛）')),
                    DropdownMenuItem(value: 'E1', child: Text('E1（国标限量）')),
                  ],
                  onChanged: (v) {
                    if (v != null) setDialogState(() => ecoGrade = v);
                  },
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: source,
                  dropdownColor: SuokeDesignTokens.card(context),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('认证来源'),
                  items: const [
                    DropdownMenuItem(
                        value: 'third_party', child: Text('第三方检测')),
                    DropdownMenuItem(
                        value: 'manufacturer', child: Text('厂家自报')),
                  ],
                  onChanged: (v) {
                    if (v != null) setDialogState(() => source = v);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: certificationCtrl,
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('认证名称（如：绿色建材产品认证）'),
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
                final materialId = materialIdCtrl.text.trim();
                if (materialId.isEmpty) {
                  _toast('请输入材料 ID');
                  return;
                }
                Navigator.pop(ctx);
                _assignCert({
                  'material_id': materialId,
                  'eco_grade': ecoGrade,
                  'certification': certificationCtrl.text.trim(),
                  'source': source,
                });
              },
              child: const Text('分配'),
            ),
          ],
        ),
      ),
    );
  }

  // ── 合规校验对话框 ──

  void _showValidateDialog() {
    final idsCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('环保合规校验',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        content: TextField(
          controller: idsCtrl,
          style: TextStyle(color: SuokeDesignTokens.text(context)),
          decoration: _inputDecoration('材料 ID（多个用逗号分隔）'),
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
              final input = idsCtrl.text.trim();
              Navigator.pop(ctx);
              _validateMaterials(input);
            },
            child: const Text('校验'),
          ),
        ],
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
