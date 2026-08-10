import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';
import '../image_helper.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../widgets/empty_state.dart';

/// 草图转 3D 页：上传手绘户型草图，AI 识别并生成 3D 布局（v1.2.0）
///
/// API 对齐 app/api/sketch_to_3d.py：
///   POST /sketch-to-3d/analyze（multipart：file + description）
///   POST /sketch-to-3d/generate-3d（multipart：file + description + style）
///   GET  /sketch-to-3d/supported-formats
class SketchTo3DPage extends StatefulWidget {
  const SketchTo3DPage({super.key});

  @override
  State<SketchTo3DPage> createState() => _SketchTo3DPageState();
}

// 风格（对齐后端 generate-3d style 参数）
const _styleOptions = {
  'modern': '现代简约',
  'nordic': '北欧',
  'japanese': '日式侘寂',
  'luxury': '轻奢',
  'chinese': '新中式',
};

// 后端降级模式 → 诚实提示（对齐 sketch_to_3d.py raw_layout.mode）
const _degradeMessages = {
  'feature_disabled': '服务端视觉识别未开启，草图分析暂不可用（已返回占位结果）',
  'no_vision_model': '服务端未配置视觉模型，草图分析暂不可用',
  'vision_call_failed': '视觉模型调用失败，草图分析暂不可用',
  'parse_error': '视觉模型响应解析失败，草图分析暂不可用',
};

class _SketchTo3DPageState extends State<SketchTo3DPage> {
  final ApiClient _api = ApiClient();

  String _mode = 'analyze';
  XFile? _file;
  String _fileName = '';
  String _fileSizeLabel = '';
  final _descCtrl = TextEditingController();
  String _style = 'modern';

  Map<String, dynamic>? _formats;
  bool _formatsLoading = true;
  String? _formatsError;

  bool _submitting = false;
  Map<String, dynamic>? _analysis;
  Map<String, dynamic>? _generated;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadFormats();
  }

  @override
  void dispose() {
    _descCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadFormats() async {
    setState(() {
      _formatsLoading = true;
      _formatsError = null;
    });
    final result = await _api.sketchSupportedFormats();
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      setState(() {
        _formats = result.data as Map<String, dynamic>;
        _formatsLoading = false;
      });
    } else {
      // 格式信息为展示性提示，失败不阻塞上传（页面内仍可提交）
      setState(() {
        _formatsError = result.error ?? '支持格式加载失败';
        _formatsLoading = false;
      });
    }
  }

  Future<void> _pickImage() async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 90,
      );
      if (picked == null || !mounted) return;
      final length = await picked.length();
      if (!mounted) return;
      setState(() {
        _file = picked;
        _fileName = picked.name;
        _fileSizeLabel = length > 1024 * 1024
            ? '${(length / (1024 * 1024)).toStringAsFixed(1)} MB'
            : '${(length / 1024).toStringAsFixed(1)} KB';
        _analysis = null;
        _generated = null;
        _error = null;
      });
    } catch (_) {
      if (mounted) setState(() => _error = '选择图片失败，请检查相册权限');
    }
  }

  Future<void> _submit() async {
    final file = _file;
    if (file == null || _submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
      _analysis = null;
      _generated = null;
    });
    final bytes = await file.readAsBytes();
    if (!mounted) return;
    final description = _descCtrl.text.trim();
    if (_mode == 'analyze') {
      final result = await _api.sketchAnalyze(
        fileBytes: bytes,
        filename: file.name,
        description: description,
      );
      if (!mounted) return;
      setState(() => _submitting = false);
      if (result.isSuccess && result.data is Map) {
        final data = result.data as Map<String, dynamic>;
        final degrade = _degradeMode(data['raw_layout']);
        if (degrade != null) {
          // 后端 200 + 降级占位 → 诚实提示而非空成功
          setState(() => _error =
              _degradeMessages[degrade] ?? '草图分析暂不可用（$degrade）');
        } else {
          setState(() => _analysis = data);
        }
      } else {
        setState(() => _error = result.error ?? '分析失败，请稍后重试');
      }
    } else {
      final result = await _api.sketchGenerate3D(
        fileBytes: bytes,
        filename: file.name,
        description: description,
        style: _style,
      );
      if (!mounted) return;
      setState(() => _submitting = false);
      if (result.isSuccess && result.data is Map) {
        final data = result.data as Map<String, dynamic>;
        final analysis = data['analysis'];
        final degrade = analysis is Map
            ? _degradeMode(analysis['raw_layout'])
            : null;
        if (degrade != null) {
          setState(() => _error =
              _degradeMessages[degrade] ?? '3D 生成暂不可用（$degrade）');
        } else {
          setState(() => _generated = data);
        }
      } else {
        setState(() => _error = result.error ?? '生成失败，请稍后重试');
      }
    }
  }

  /// 识别后端降级占位结果（raw_layout.mode 非 vision_analyzed 时返回该 mode）
  String? _degradeMode(Object? rawLayout) {
    if (rawLayout is! Map) return null;
    final mode = (rawLayout['mode'] ?? '').toString();
    if (mode.isEmpty || mode == 'vision_analyzed') return null;
    return mode;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.card(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('草图转 3D'),
      ),
      body: _formatsLoading
          ? const LoadingSkeleton(itemHeight: 90)
          : ListView(
              padding: const EdgeInsets.all(12),
              children: [
                if (_formatsError != null)
                  ErrorRetryWidget(
                      message: _formatsError!, onRetry: _loadFormats)
                else
                  _buildFormatsCard(),
                const SizedBox(height: 12),
                _buildModeSwitch(),
                const SizedBox(height: 12),
                if (_file == null)
                  _buildPickZone()
                else
                  _buildPickedCard(),
                const SizedBox(height: 12),
                _buildDescriptionField(),
                if (_mode == 'generate') ...[
                  const SizedBox(height: 12),
                  _buildStylePicker(),
                ],
                const SizedBox(height: 12),
                if (_file != null)
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _submitting ? null : _submit,
                      icon: _submitting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : Icon(_mode == 'analyze'
                              ? Icons.search
                              : Icons.view_in_ar_outlined,
                              size: 18),
                      label: Text(_submitting
                          ? (_mode == 'analyze' ? '分析中...' : '生成中...')
                          : (_mode == 'analyze' ? '开始分析' : '生成 3D')),
                    ),
                  ),
                if (_submitting)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Center(
                      child: Text('正在处理草图，请稍候...',
                          style: TextStyle(
                              color: SuokeDesignTokens.textSub(context),
                              fontSize: 13)),
                    ),
                  ),
                if (_error != null && !_submitting)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(_error!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                            color: SuokeDesignTokens.danger, fontSize: 13)),
                  ),
                if (_mode == 'analyze' && _analysis != null && !_submitting)
                  _buildAnalysisResult(),
                if (_mode == 'generate' && _generated != null && !_submitting)
                  _buildGeneratedResult(),
                const SizedBox(height: 24),
              ],
            ),
    );
  }

  // ── 支持格式卡片 ──

  Widget _buildFormatsCard() {
    final formats = _formats;
    final imageFormats = formats?['image_formats'];
    final maxMb = (formats?['max_file_size_mb'] as num?)?.toInt() ?? 10;
    final resolution = (formats?['recommended_resolution'] ?? '').toString();
    final tips = formats?['tips'];
    final formatNames = imageFormats is List && imageFormats.isNotEmpty
        ? imageFormats.join(' / ')
        : 'PNG / JPG';
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
                const Icon(Icons.info_outline,
                    color: SuokeDesignTokens.accent, size: 20),
                const SizedBox(width: 8),
                Text('支持格式',
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 15,
                        fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '$formatNames · 最大 ${maxMb}MB'
              '${resolution.isNotEmpty ? ' · 建议 $resolution' : ''}',
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 12),
            ),
            if (tips is List && tips.isNotEmpty) ...[
              const SizedBox(height: 6),
              for (final tip in tips)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text('• ${tip.toString()}',
                      style: TextStyle(
                          color: SuokeDesignTokens.textSub(context),
                          fontSize: 12)),
                ),
            ],
          ],
        ),
      ),
    );
  }

  // ── 模式切换 ──

  Widget _buildModeSwitch() {
    return Row(
      children: [
        _buildModeChip('analyze', '草图分析', Icons.search),
        const SizedBox(width: 8),
        _buildModeChip('generate', '生成 3D', Icons.view_in_ar_outlined),
      ],
    );
  }

  Widget _buildModeChip(String value, String label, IconData icon) {
    final selected = _mode == value;
    return Expanded(
      child: ChoiceChip(
        avatar: Icon(icon,
            size: 18,
            color: selected
                ? SuokeDesignTokens.accent
                : SuokeDesignTokens.textSub(context)),
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
            _analysis = null;
            _generated = null;
            _error = null;
          });
        },
      ),
    );
  }

  // ── 选择图片（空态） ──

  Widget _buildPickZone() {
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: _pickImage,
        child: const Padding(
          padding: EdgeInsets.all(24),
          child: EmptyStateWidget(
            icon: Icons.add_photo_alternate_outlined,
            title: '选择草图图片',
            description: '支持 PNG / JPG / JPEG，建议使用黑色笔在白色纸上绘制户型图',
          ),
        ),
      ),
    );
  }

  // ── 已选图片预览 ──

  Widget _buildPickedCard() {
    final path = _file!.path;
    return Card(
      color: SuokeDesignTokens.card(context),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
      ),
      margin: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: const BorderRadius.vertical(
                top: Radius.circular(12)),
            child: SizedBox(
              width: double.infinity,
              height: 160,
              child: buildLocalImage(
                path,
                fit: BoxFit.cover,
                errorWidget: Container(
                  color: SuokeDesignTokens.bg(context),
                  alignment: Alignment.center,
                  child: const Icon(Icons.broken_image_outlined,
                      size: 40, color: SuokeDesignTokens.textMuted),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
            child: Row(
              children: [
                Expanded(
                  child: Text('$_fileName（$_fileSizeLabel）',
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 13),
                      overflow: TextOverflow.ellipsis),
                ),
                TextButton(
                  onPressed: () => setState(() {
                    _file = null;
                    _analysis = null;
                    _generated = null;
                    _error = null;
                  }),
                  child: const Text('重新选择'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── 描述与风格 ──

  Widget _buildDescriptionField() {
    return TextField(
      controller: _descCtrl,
      style: TextStyle(color: SuokeDesignTokens.text(context)),
      maxLines: 2,
      maxLength: 500,
      decoration: _inputDecoration('草图描述（可选，如：三室两厅户型）'),
    );
  }

  Widget _buildStylePicker() {
    return DropdownButtonFormField<String>(
      initialValue: _style,
      dropdownColor: SuokeDesignTokens.card(context),
      style: TextStyle(color: SuokeDesignTokens.text(context)),
      decoration: _inputDecoration('装修风格'),
      items: [
        for (final e in _styleOptions.entries)
          DropdownMenuItem(value: e.key, child: Text(e.value)),
      ],
      onChanged: (v) {
        if (v != null) setState(() => _style = v);
      },
    );
  }

  // ── 分析结果 ──

  Widget _buildAnalysisResult() {
    final a = _analysis!;
    final walls = (a['detected_walls'] as List?) ?? [];
    final doors = (a['detected_doors'] as List?) ?? [];
    final windows = (a['detected_windows'] as List?) ?? [];
    final rooms = (a['room_count'] as num?)?.toInt() ?? 0;
    final area = (a['estimated_area'] as num?)?.toDouble() ?? 0.0;
    final confidence = (a['confidence'] as num?)?.toDouble() ?? 0.0;
    final sketchId = (a['sketch_id'] ?? '').toString();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('分析结果'),
        Card(
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
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _statChip('墙体', '${walls.length}'),
                    _statChip('门', '${doors.length}'),
                    _statChip('窗', '${windows.length}'),
                    _statChip('房间数', '$rooms'),
                    _statChip('估算面积', '${area.toStringAsFixed(1)}㎡'),
                    _statChip('置信度', '${(confidence * 100).round()}%'),
                  ],
                ),
                if (sketchId.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Text('草图 ID：$sketchId',
                        style: TextStyle(
                            color: SuokeDesignTokens.textSub(context),
                            fontSize: 12)),
                  ),
                _buildElementList('检测墙体', walls, 'length_cm'),
                _buildElementList('检测门', doors, 'width_cm'),
                _buildElementList('检测窗', windows, 'width_cm'),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildElementList(String title, List<dynamic> items, String unitKey) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 13,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 4),
          for (final item in items)
            if (item is Map)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Text(
                  '${item['id'] ?? '-'}（${item[unitKey] ?? '?'}cm）',
                  style: TextStyle(
                      color: SuokeDesignTokens.textSub(context),
                      fontSize: 12),
                ),
              ),
        ],
      ),
    );
  }

  // ── 生成 3D 结果 ──

  Widget _buildGeneratedResult() {
    final g = _generated!;
    final sketchId = (g['sketch_id'] ?? '').toString();
    final layout = g['layout_3d'] is Map
        ? Map<String, dynamic>.from(g['layout_3d'] as Map)
        : <String, dynamic>{};
    final suggestions = (g['suggestions'] as List?) ?? [];
    final plans = layout['plans'];
    final analysis = g['analysis'];
    final rooms = analysis is Map
        ? (analysis['room_count'] as num?)?.toInt() ?? 0
        : 0;
    final area = analysis is Map
        ? (analysis['estimated_area'] as num?)?.toDouble() ?? 0.0
        : 0.0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('3D 生成结果'),
        Card(
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
                    const Icon(Icons.check_circle_outline,
                        color: SuokeDesignTokens.success, size: 20),
                    const SizedBox(width: 8),
                    Text('方案已生成',
                        style: TextStyle(
                            color: SuokeDesignTokens.text(context),
                            fontSize: 15,
                            fontWeight: FontWeight.w600)),
                  ],
                ),
                if (sketchId.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('草图 ID：$sketchId',
                        style: TextStyle(
                            color: SuokeDesignTokens.textSub(context),
                            fontSize: 12)),
                  ),
                if (rooms > 0 || area > 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('识别 $rooms 个房间 · 估算面积 ${area.toStringAsFixed(1)}㎡',
                        style: TextStyle(
                            color: SuokeDesignTokens.textSub(context),
                            fontSize: 12)),
                  ),
                if (layout['bim_compatible'] != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      layout['bim_compatible'] == true
                          ? 'BIM 兼容'
                          : '非 BIM 兼容',
                      style: TextStyle(
                          color: layout['bim_compatible'] == true
                              ? SuokeDesignTokens.success
                              : SuokeDesignTokens.warning,
                          fontSize: 12),
                    ),
                  ),
                if (plans is List)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('共 ${plans.length} 套布局方案',
                        style: TextStyle(
                            color: SuokeDesignTokens.textSub(context),
                            fontSize: 12)),
                  ),
                if ((layout['recommendation'] ?? '').toString().isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      layout['recommendation'].toString(),
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 13),
                    ),
                  ),
                if (suggestions.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text('优化建议',
                      style: TextStyle(
                          color: SuokeDesignTokens.text(context),
                          fontSize: 13,
                          fontWeight: FontWeight.w600)),
                  for (final s in suggestions)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Text('• ${s.toString()}',
                          style: TextStyle(
                              color: SuokeDesignTokens.textSub(context),
                              fontSize: 12)),
                    ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }

  // ── 通用组件 ──

  Widget _statChip(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.accent.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(value,
              style: const TextStyle(
                  color: SuokeDesignTokens.accent,
                  fontSize: 16,
                  fontWeight: FontWeight.bold)),
          Text(label,
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 11)),
        ],
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
