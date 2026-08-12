import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

/// 拍照上架：多模态 AI 识别产品 → 人工确认表单 → 上架
class CameraScanPage extends StatefulWidget {
  const CameraScanPage({super.key});

  @override
  State<CameraScanPage> createState() => _CameraScanPageState();
}

class _CameraScanPageState extends State<CameraScanPage> {
  final ApiClient _api = ApiClient();

  // 品类映射（中文标签 -> 后端 code，不含「全部」）
  static const Map<String, String> _categoryMap = {
    '瓷砖': 'tile',
    '地板': 'flooring',
    '橱柜': 'cabinet',
    '涂料': 'paint',
    '灯具': 'lighting',
    '电器': 'appliance',
    '窗帘': 'curtain',
    '定制家具': 'custom_furniture',
    '服务': 'service',
    '其他': 'other',
  };

  // 识别
  Uint8List? _imageBytes;
  bool _scanning = false;
  Map<String, dynamic>? _result;

  // 确认表单
  final TextEditingController _nameCtrl = TextEditingController();
  final TextEditingController _priceMinCtrl = TextEditingController();
  final TextEditingController _priceMaxCtrl = TextEditingController();
  final TextEditingController _unitCtrl = TextEditingController();
  final TextEditingController _tagsCtrl = TextEditingController();
  final TextEditingController _descCtrl = TextEditingController();
  String? _categoryCode;
  int _formVersion = 0; // 强制重建下拉，重置选中值
  bool _confirming = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _priceMinCtrl.dispose();
    _priceMaxCtrl.dispose();
    _unitCtrl.dispose();
    _tagsCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  // ── 拍照/相册 → AI 识别 ──

  Future<void> _pickAndScan(ImageSource source) async {
    try {
      final picked = await ImagePicker().pickImage(source: source);
      if (picked == null || !mounted) return;
      final bytes = await picked.readAsBytes();
      if (!mounted) return;
      final filename = '${DateTime.now().millisecondsSinceEpoch}.jpg';
      setState(() {
        _imageBytes = bytes;
        _scanning = true;
        _result = null;
      });
      final result = await _api.cameraScan(bytes, filename);
      if (!mounted) return;
      setState(() => _scanning = false);
      if (result.isSuccess && result.data is Map) {
        final data = result.data as Map<String, dynamic>;
        setState(() {
          _result = data;
          // 预填确认表单
          _nameCtrl.text = data['name']?.toString() ?? '';
          _categoryCode = _matchCategoryCode(data['category_code']?.toString());
          _unitCtrl.text = data['suggested_unit']?.toString() ?? '';
          final tags = (data['tags'] as List?) ?? [];
          _tagsCtrl.text = tags.map((t) => t.toString()).join(',');
          _formVersion++;
        });
      } else if (result.statusCode == 403) {
        _showSnack('仅已认证供应商可用');
      } else {
        _showSnack('识别失败：${result.error}');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _scanning = false);
        _showSnack('图片读取失败，请重试');
      }
    }
  }

  // ── 确认上架 ──

  Future<void> _confirmUpload() async {
    if (_confirming) return;
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      _showSnack('请输入产品名称');
      return;
    }
    final category = _categoryCode;
    if (category == null || category.isEmpty) {
      _showSnack('请选择产品品类');
      return;
    }
    final priceMin = double.tryParse(_priceMinCtrl.text.trim());
    final priceMax = double.tryParse(_priceMaxCtrl.text.trim());
    if (priceMin != null && priceMax != null && priceMin > priceMax) {
      _showSnack('价格下限不能大于上限');
      return;
    }
    setState(() => _confirming = true);
    final result = await _api.cameraConfirm({
      'name': name,
      'category': category,
      'description': _descCtrl.text.trim(),
      'price_min': priceMin,
      'price_max': priceMax,
      'unit': _unitCtrl.text.trim(),
      'tags': _tagsCtrl.text.trim(),
      'stock_status': 'in_stock',
      'ai_assisted': true,
    });
    if (!mounted) return;
    setState(() => _confirming = false);
    if (result.isSuccess) {
      _showSnack('上架成功');
      _clearForm();
    } else if (result.statusCode == 403) {
      _showSnack('仅已认证供应商可用');
    } else {
      _showSnack('上架失败：${result.error}');
    }
  }

  void _clearForm() {
    setState(() {
      _nameCtrl.clear();
      _priceMinCtrl.clear();
      _priceMaxCtrl.clear();
      _unitCtrl.clear();
      _tagsCtrl.clear();
      _descCtrl.clear();
      _categoryCode = null;
      _formVersion++;
    });
  }

  // ── 辅助 ──

  String? _matchCategoryCode(String? code) {
    if (code == null || code.isEmpty) return null;
    if (_categoryMap.containsValue(code)) return code;
    return null;
  }

  String _confidenceText(Object? value) {
    final numVal =
        value is num ? value.toDouble() : double.tryParse(value?.toString() ?? '');
    if (numVal == null) return '—';
    if (numVal <= 1) return '${(numVal * 100).toStringAsFixed(0)}%';
    return '${numVal.toStringAsFixed(0)}%';
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  InputDecoration _inputDecoration(String? hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13),
      filled: true,
      fillColor: SuokeDesignTokens.bg(context),
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
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

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bg(context),
        title: Text('拍照上架',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        iconTheme: IconThemeData(color: SuokeDesignTokens.text(context)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildHonestBanner(),
            const SizedBox(height: 12),
            _buildPickButtons(),
            if (_scanning) ...[
              const SizedBox(height: 12),
              _buildScanningCard(),
            ],
            if (_result != null) ...[
              const SizedBox(height: 12),
              _buildResultCard(),
              const SizedBox(height: 12),
              _buildConfirmForm(),
            ],
          ],
        ),
      ),
    );
  }

  /// 页面顶部诚实标注：识别由多模态 AI 完成
  Widget _buildHonestBanner() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Row(
        children: [
          const Icon(Icons.auto_awesome, color: SuokeDesignTokens.accent, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text('识别由多模态 AI 完成，识别结果仅供参考，请核对后确认上架',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _buildPickButtons() {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: _scanning ? null : () => _pickAndScan(ImageSource.camera),
            icon: const Icon(Icons.photo_camera_outlined),
            label: const Text('拍照'),
            style: OutlinedButton.styleFrom(
              foregroundColor: SuokeDesignTokens.text(context),
              side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: _scanning ? null : () => _pickAndScan(ImageSource.gallery),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('相册'),
            style: OutlinedButton.styleFrom(
              foregroundColor: SuokeDesignTokens.text(context),
              side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
              padding: const EdgeInsets.symmetric(vertical: 12),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildScanningCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        children: [
          const CircularProgressIndicator(color: SuokeDesignTokens.accent),
          const SizedBox(height: 12),
          Text('正在识别产品...',
              style:
                  TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildResultCard() {
    final data = _result!;
    final tags = (data['tags'] as List?) ?? [];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('识别结果',
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 15,
                  fontWeight: FontWeight.bold)),
          if (data['fallback'] == true) ...[
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.warning.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Row(
                children: [
                  Icon(Icons.warning_amber_rounded,
                      color: SuokeDesignTokens.warning, size: 14),
                  SizedBox(width: 6),
                  Text('识别置信度低，请人工核对',
                      style: TextStyle(color: SuokeDesignTokens.warning, fontSize: 12)),
                ],
              ),
            ),
          ],
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: _buildPreviewImage(data),
          ),
          const SizedBox(height: 12),
          _infoRow('名称', data['name']?.toString() ?? '—'),
          _infoRow('品类', data['category_cn']?.toString() ?? '—'),
          if (data['material'] != null && data['material'].toString().isNotEmpty)
            _infoRow('材质', data['material'].toString()),
          if (data['color'] != null && data['color'].toString().isNotEmpty)
            _infoRow('颜色', data['color'].toString()),
          if (data['style'] != null && data['style'].toString().isNotEmpty)
            _infoRow('风格', data['style'].toString()),
          _infoRow('置信度', _confidenceText(data['confidence'])),
          if (data['suggested_price'] != null &&
              data['suggested_price'].toString().isNotEmpty)
            _infoRow('建议价格', data['suggested_price'].toString()),
          if (data['origin'] != null && data['origin'].toString().isNotEmpty)
            _infoRow('产地', data['origin'].toString()),
          if (tags.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('标签',
                style: TextStyle(
                    color: SuokeDesignTokens.accent,
                    fontSize: 13,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: tags
                  .map((t) => Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: SuokeDesignTokens.bg(context),
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(
                              color: SuokeDesignTokens.borderClr(context)),
                        ),
                        child: Text(t.toString(),
                            style: TextStyle(
                                color: SuokeDesignTokens.textSub(context),
                                fontSize: 11)),
                      ))
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }

  /// 预览图：优先展示后端缩略图（base64），失败/缺失时回退原图
  Widget _buildPreviewImage(Map<String, dynamic> data) {
    final thumb = data['thumbnail']?.toString();
    if (thumb != null && thumb.isNotEmpty) {
      try {
        return Image.memory(
          base64Decode(thumb),
          height: 180,
          width: double.infinity,
          fit: BoxFit.cover,
          errorBuilder: (_, _, _) => _buildFallbackPreview(),
        );
      } catch (_) {}
    }
    return _buildFallbackPreview();
  }

  Widget _buildFallbackPreview() {
    final bytes = _imageBytes;
    if (bytes != null) {
      return Image.memory(
        bytes,
        height: 180,
        width: double.infinity,
        fit: BoxFit.cover,
      );
    }
    return Container(
      height: 180,
      width: double.infinity,
      color: SuokeDesignTokens.bg(context),
      child: Icon(Icons.image_outlined,
          color: SuokeDesignTokens.textSub(context), size: 32),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 68,
            child: Text(label,
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          ),
          Expanded(
            child: Text(value,
                style:
                    TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
        ],
      ),
    );
  }

  Widget _buildConfirmForm() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('确认信息',
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 15,
                  fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _buildLabeledField('名称', _nameCtrl, hint: '产品名称'),
          const SizedBox(height: 12),
          Text('品类',
              style:
                  TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
          const SizedBox(height: 6),
          DropdownButtonFormField<String>(
            key: ValueKey(_formVersion),
            initialValue: _categoryCode,
            decoration: _inputDecoration('请选择品类'),
            dropdownColor: SuokeDesignTokens.card(context),
            style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13),
            items: _categoryMap.entries
                .map((e) => DropdownMenuItem(
                      value: e.value,
                      child: Text(e.key,
                          style: TextStyle(
                              color: SuokeDesignTokens.text(context),
                              fontSize: 13)),
                    ))
                .toList(),
            onChanged: (v) => setState(() => _categoryCode = v),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _priceMinCtrl,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('单价下限'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _priceMaxCtrl,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  style: TextStyle(color: SuokeDesignTokens.text(context)),
                  decoration: _inputDecoration('单价上限'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildLabeledField('单位', _unitCtrl, hint: '如：个/平方米'),
          const SizedBox(height: 12),
          _buildLabeledField('标签', _tagsCtrl, hint: '多个标签用逗号分隔'),
          const SizedBox(height: 12),
          _buildLabeledField('描述', _descCtrl, hint: '产品描述（可选）', maxLines: 3),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _confirming ? null : _confirmUpload,
              child: _confirming
                  ? SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: SuokeDesignTokens.bg(context)),
                    )
                  : const Text('确认上架'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLabeledField(String label, TextEditingController ctrl,
      {String? hint, int maxLines = 1}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style:
                TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        const SizedBox(height: 6),
        TextField(
          controller: ctrl,
          maxLines: maxLines,
          style: TextStyle(color: SuokeDesignTokens.text(context)),
          decoration: _inputDecoration(hint),
        ),
      ],
    );
  }
}
