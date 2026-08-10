import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

/// BIM IFC 导出页：结构 / 设计方案导出为 IFC4 文件（v1.2.x）
///
/// API 对齐 app/api/ifc_export.py（响应为二进制 FileResponse）：
///   POST /bim/export/structural/{project_id}
///   POST /bim/export/design/{plan_id}
/// 降级：
///   501 — ifcopenshell 未安装
///   404 — 项目/方案不存在或无结构数据
class IFCExportPage extends StatefulWidget {
  /// 可选：预填项目 ID（结构导出）
  final String? projectId;
  const IFCExportPage({super.key, this.projectId});

  @override
  State<IFCExportPage> createState() => _IFCExportPageState();
}

const _lodOptions = [
  ('LOD200', 'LOD200（概念设计）'),
  ('LOD300', 'LOD300（施工图设计，默认）'),
  ('LOD350', 'LOD350（深化设计）'),
];

class _IFCExportPageState extends State<IFCExportPage> {
  final ApiClient _api = ApiClient();

  String _mode = 'structural';
  final _projectIdCtrl = TextEditingController();
  final _planIdCtrl = TextEditingController();
  bool _includeFurniture = false;
  String _lodLevel = 'LOD300';

  bool _exporting = false;
  IFCExportFile? _result;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.projectId != null) {
      _projectIdCtrl.text = widget.projectId!;
    }
  }

  @override
  void dispose() {
    _projectIdCtrl.dispose();
    _planIdCtrl.dispose();
    super.dispose();
  }

  Future<void> _export() async {
    if (_exporting) return;
    final projectId = _projectIdCtrl.text.trim();
    final planId = _planIdCtrl.text.trim();
    if (_mode == 'structural' && projectId.isEmpty) {
      setState(() => _error = '请输入项目 ID');
      return;
    }
    if (_mode == 'design' && planId.isEmpty) {
      setState(() => _error = '请输入方案 ID');
      return;
    }

    setState(() {
      _exporting = true;
      _error = null;
      _result = null;
    });

    final Result<IFCExportFile> result;
    if (_mode == 'structural') {
      result = await _api.exportStructuralIFCFile(
        projectId,
        includeFurniture: _includeFurniture,
        lodLevel: _lodLevel,
      );
    } else {
      result = await _api.exportDesignIFCFile(
        planId,
        includeFurniture: _includeFurniture,
        lodLevel: _lodLevel,
      );
    }
    if (!mounted) return;
    setState(() => _exporting = false);
    if (result.isSuccess) {
      setState(() => _result = result.data);
    } else {
      setState(() => _error = _friendlyError(result));
    }
  }

  /// 501 / 404 映射为诚实提示，其余展示后端真实错误
  String _friendlyError(Result<IFCExportFile> result) {
    switch (result.statusCode) {
      case 501:
        return '服务端未安装 ifcopenshell，IFC 导出不可用。请联系管理员安装 ifcopenshell>=0.7.0';
      case 404:
        return '未找到可导出的数据：项目/方案不存在或无结构数据';
      default:
        return result.error ?? '导出失败，请稍后重试';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('BIM IFC 导出'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          _buildModeSwitch(),
          const SizedBox(height: 12),
          _buildFormCard(),
          const SizedBox(height: 12),
          if (_exporting) _buildExportingCard(),
          if (_error != null && !_exporting) _buildErrorCard(),
          if (_result != null && !_exporting) _buildSuccessCard(),
          const SizedBox(height: 12),
          _buildHintCard(),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  // ── 模式切换 ──

  Widget _buildModeSwitch() {
    return Row(
      children: [
        _buildModeChip('structural', '结构导出'),
        const SizedBox(width: 8),
        _buildModeChip('design', '设计导出'),
      ],
    );
  }

  Widget _buildModeChip(String value, String label) {
    final selected = _mode == value;
    return Expanded(
      child: ChoiceChip(
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
          setState(() {
            _mode = value;
            _error = null;
            _result = null;
          });
        },
      ),
    );
  }

  // ── 表单 ──

  Widget _buildFormCard() {
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
                const Icon(Icons.architecture,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(_mode == 'structural' ? '结构导出' : '设计导出',
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 15,
                          fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _projectIdCtrl,
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              decoration: _inputDecoration('项目 ID（结构导出必填）'),
            ),
            if (_mode == 'design') ...[
              const SizedBox(height: 12),
              TextField(
                controller: _planIdCtrl,
                style: TextStyle(color: SuokeDesignTokens.text(context)),
                decoration: _inputDecoration('方案 ID（设计导出必填）'),
              ),
            ],
            const SizedBox(height: 4),
            SwitchListTile(
              value: _includeFurniture,
              onChanged: (v) => setState(() => _includeFurniture = v),
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: Text('含家具',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 13)),
            ),
            DropdownButtonFormField<String>(
              initialValue: _lodLevel,
              dropdownColor: SuokeDesignTokens.card(context),
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              decoration: _inputDecoration('细节等级'),
              items: [
                for (final l in _lodOptions)
                  DropdownMenuItem(value: l.$1, child: Text(l.$2)),
              ],
              onChanged: (v) {
                if (v != null) setState(() => _lodLevel = v);
              },
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _exporting ? null : _export,
                icon: _exporting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.file_download_outlined, size: 18),
                label: Text(_exporting
                    ? '导出中...'
                    : '导出 ${_mode == 'structural' ? '结构' : '设计'} IFC'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── 导出中 / 错误 / 成功 ──

  Widget _buildExportingCard() {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
            const SizedBox(width: 12),
            Text('正在生成 IFC 文件，请稍候...',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorCard() {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: SuokeDesignTokens.danger),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.error_outline,
                    color: SuokeDesignTokens.danger, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(_error!,
                      style: const TextStyle(
                          color: SuokeDesignTokens.danger, fontSize: 13)),
                ),
              ],
            ),
            const SizedBox(height: 10),
            TextButton.icon(
              onPressed: () => setState(() => _error = null),
              icon: const Icon(Icons.close, size: 16),
              label: const Text('关闭'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuccessCard() {
    final file = _result!;
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: SuokeDesignTokens.success),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.check_circle_outline,
                    color: SuokeDesignTokens.success, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('IFC 文件已生成',
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 15,
                          fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text('文件名：${file.filename.isEmpty ? '（未命名）' : file.filename}',
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13)),
            const SizedBox(height: 4),
            Text('文件大小：${file.sizeLabel}',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 13)),
            const SizedBox(height: 10),
            Text('文件为 IFC4 格式，可在 Revit / ArchiCAD / BIMReviewer 中打开。'
                '移动端可直接将文件发送至电脑端使用（保存提示：文件内容已返回至本机内存，'
                '如需持久保存请通过文件管理器导出）。',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12)),
          ],
        ),
      ),
    );
  }

  Widget _buildHintCard() {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.tips_and_updates_outlined,
                color: SuokeDesignTokens.accent, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'IFC4 开放格式，可在 Revit / ArchiCAD / BIMReviewer 中打开。'
                '结构导出面向项目承重墙、梁、柱、楼板；设计导出面向户型方案墙体与门窗。',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12),
              ),
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
