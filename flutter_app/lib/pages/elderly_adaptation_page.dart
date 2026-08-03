import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

/// F41 适老改造页面（v1.5.0）
class ElderlyAdaptationPage extends StatefulWidget {
  final String projectId;
  const ElderlyAdaptationPage({super.key, required this.projectId});

  @override
  State<ElderlyAdaptationPage> createState() => _ElderlyAdaptationPageState();
}

class _ElderlyAdaptationPageState extends State<ElderlyAdaptationPage> {
  final ApiClient _api = ApiClient();

  List<dynamic> _schemes = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSchemes();
  }

  Future<void> _loadSchemes() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.elderlyListSchemes(widget.projectId);
    if (!mounted) return;
    if (result.isSuccess) {
      setState(() {
        _schemes = _extractList(result.data, 'schemes');
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

  Future<void> _createScheme(String name, String occupantType) async {
    final result = await _api.elderlyCreateScheme({
      'project_id': widget.projectId,
      'name': name,
      'occupant_type': occupantType,
    });
    if (!mounted) return;
    if (result.isSuccess) {
      _toast('方案已创建');
      unawaited(_loadSchemes());
    } else {
      _toast('创建失败：${result.error}');
    }
  }

  Future<void> _validateScheme(Map<String, dynamic> scheme) async {
    final id = (scheme['id'] ?? '').toString();
    final result = await _api.elderlyValidateScheme(id);
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      final data = result.data as Map<String, dynamic>;
      _showValidateResult(scheme, data);
      unawaited(_loadSchemes());
    } else {
      _toast('校验失败：${result.error}');
    }
  }

  void _showValidateResult(
      Map<String, dynamic> scheme, Map<String, dynamic> data) {
    final compliance = (data['compliance_status'] ?? '').toString();
    final score = data['score'];
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('合规校验结果',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('方案：${scheme['name'] ?? ''}',
                style: TextStyle(color: SuokeDesignTokens.text(context))),
            const SizedBox(height: 8),
            Text('得分：${score ?? '待实测'}',
                style: TextStyle(color: SuokeDesignTokens.text(context))),
            const SizedBox(height: 8),
            Text('合规状态：${_complianceLabel(compliance)}',
                style: TextStyle(color: SuokeDesignTokens.text(context))),
            const SizedBox(height: 8),
            Text(data['summary']?.toString() ?? '',
                style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('知道了',
                style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
        ],
      ),
    );
  }

  String _occupantLabel(String? type) {
    switch (type) {
      case 'elderly_living':
        return '老人独立生活';
      case 'semi_selfcare':
        return '半自理';
      case 'nursing':
        return '失能护理';
      case 'family':
        return '多代同堂';
      default:
        return type ?? '老人独立生活';
    }
  }

  String _complianceLabel(String? status) {
    switch (status) {
      case 'pass':
        return '合规';
      case 'warning':
        return '待复核';
      case 'fail':
        return '不合规';
      case 'pending':
        return '待检查';
      default:
        return status ?? '待复核';
    }
  }

  Color _complianceColor(String? status) {
    switch (status) {
      case 'pass':
        return SuokeDesignTokens.success;
      case 'fail':
        return SuokeDesignTokens.danger;
      case 'pending':
        return SuokeDesignTokens.info;
      default:
        return SuokeDesignTokens.warning;
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
        title: const Text('适老改造'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const LoadingSkeleton(itemHeight: 110);
    }
    if (_error != null) {
      return ErrorRetryWidget(message: _error!, onRetry: _loadSchemes);
    }
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
                  onPressed: _showCreateDialog,
                  icon: const Icon(Icons.add),
                  label: const Text('创建方案'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: SuokeDesignTokens.text(context),
                  side: BorderSide(
                      color: SuokeDesignTokens.borderClr(context)),
                ),
                onPressed: _loadSchemes,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            color: SuokeDesignTokens.accent,
            onRefresh: _loadSchemes,
            child: _schemes.isEmpty
                ? ListView(
                    children: [
                      const SizedBox(height: 120),
                      Center(
                        child: Column(
                          children: [
                            Icon(Icons.elderly,
                                size: 64,
                                color: SuokeDesignTokens.textSub(context)),
                            const SizedBox(height: 16),
                            Text('暂无适老改造方案',
                                style: TextStyle(
                                    fontSize: 16,
                                    color: SuokeDesignTokens.textSub(context))),
                          ],
                        ),
                      ),
                    ],
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: _schemes.length,
                    itemBuilder: (context, index) {
                      final scheme =
                          _schemes[index] as Map<String, dynamic>;
                      return _buildSchemeCard(scheme);
                    },
                  ),
          ),
        ),
      ],
    );
  }

  Widget _buildSchemeCard(Map<String, dynamic> scheme) {
    final compliance = (scheme['compliance_status'] ?? '').toString();
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
                const Icon(Icons.elderly,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    scheme['name'] ?? '未命名方案',
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
                    color: _complianceColor(compliance)
                        .withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _complianceLabel(compliance),
                    style: TextStyle(
                      color: _complianceColor(compliance),
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 12,
              runSpacing: 4,
              children: [
                _buildInfoChip('居住人群',
                    _occupantLabel(scheme['occupant_type']?.toString())),
                _buildInfoChip(
                    '条目数', '${(scheme['items'] as List?)?.length ?? 0}'),
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
                onPressed: () => _validateScheme(scheme),
                icon: const Icon(Icons.fact_check_outlined, size: 16),
                label: const Text('校验', style: TextStyle(fontSize: 13)),
              ),
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

  void _showCreateDialog() {
    final nameCtrl = TextEditingController();
    String occupantType = 'elderly_living';
    const types = [
      ('elderly_living', '老人独立生活'),
      ('semi_selfcare', '半自理'),
      ('nursing', '失能护理'),
      ('family', '多代同堂'),
    ];
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text('创建适老改造方案',
              style: TextStyle(color: SuokeDesignTokens.text(context))),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('方案名称'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: occupantType,
                  dropdownColor: SuokeDesignTokens.card(context),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('居住人群'),
                  items: types
                      .map((t) => DropdownMenuItem(
                            value: t.$1,
                            child: Text(t.$2,
                                style: TextStyle(
                                    color: SuokeDesignTokens.text(context))),
                          ))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) setDialogState(() => occupantType = v);
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
                  _toast('请输入方案名称');
                  return;
                }
                Navigator.pop(ctx);
                _createScheme(name, occupantType);
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
