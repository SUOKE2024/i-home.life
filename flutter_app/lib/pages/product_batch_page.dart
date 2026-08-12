import 'dart:async';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../services/api.dart';
import '../theme/suoke_theme.dart';

/// 批量上传：xlsx/csv 文件批量创建产品 + AI 文案生成进度轮询
class ProductBatchPage extends StatefulWidget {
  const ProductBatchPage({super.key});

  @override
  State<ProductBatchPage> createState() => _ProductBatchPageState();
}

class _ProductBatchPageState extends State<ProductBatchPage> {
  final ApiClient _api = ApiClient();

  // 文件
  Uint8List? _fileBytes;
  String? _fileName;
  String? _fileSizeLabel;

  // 上传
  bool _uploading = false;
  Map<String, dynamic>? _uploadResult;
  String? _error;

  // AI 文案进度
  Map<String, dynamic>? _aiStatus;
  Timer? _pollTimer;

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['xlsx', 'csv'],
      );
      if (result == null || result.files.isEmpty || !mounted) return;
      final file = result.files.first;
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      if (bytes.isEmpty) {
        _showSnack('无法读取文件内容，请重试');
        return;
      }
      setState(() {
        _fileBytes = bytes;
        _fileName = file.name;
        _fileSizeLabel = _formatSize(bytes.length);
        _uploadResult = null;
        _aiStatus = null;
        _error = null;
      });
    } catch (_) {
      if (mounted) _showSnack('选择文件失败，请检查文件权限');
    }
  }

  Future<void> _upload() async {
    if (_uploading) return;
    final bytes = _fileBytes;
    if (bytes == null) {
      _showSnack('请先选择文件');
      return;
    }
    setState(() {
      _uploading = true;
      _error = null;
      _uploadResult = null;
      _aiStatus = null;
    });
    final result =
        await _api.productBatchUpload(bytes, _fileName ?? 'products.xlsx');
    if (!mounted) return;
    setState(() => _uploading = false);
    if (result.isSuccess && result.data is Map) {
      final data = result.data as Map<String, dynamic>;
      setState(() => _uploadResult = data);
      final aiPending = (data['ai_jobs_pending'] as num?)?.toInt() ?? 0;
      final batchId = data['batch_id']?.toString();
      if (aiPending > 0 && batchId != null && batchId.isNotEmpty) {
        _startPolling(batchId);
      }
    } else if (result.statusCode == 403) {
      setState(() => _error = '仅已认证供应商可用');
    } else {
      setState(() => _error = '上传失败：${result.error}');
    }
  }

  void _startPolling(String batchId) {
    _pollTimer?.cancel();
    _pollTimer =
        Timer.periodic(const Duration(seconds: 3), (_) => _pollAiStatus(batchId));
  }

  Future<void> _pollAiStatus(String batchId) async {
    final result = await _api.productBatchAiCopyStatus(batchId);
    if (!mounted) return;
    if (result.isSuccess && result.data is Map) {
      final data = result.data as Map<String, dynamic>;
      setState(() => _aiStatus = data);
      // in_progress 为 false 表示 AI 文案生成完成，停止轮询
      if (data['in_progress'] == false) _stopPolling();
    } else {
      // 任务过期（404）等场景停止轮询，避免无限重试
      _stopPolling();
      _showSnack('AI 文案状态查询失败：${result.error}');
    }
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  String _formatSize(int bytes) {
    if (bytes >= 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / 1024).toStringAsFixed(1)} KB';
  }

  void _showSnack(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bg(context),
        title: Text('批量上传',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        iconTheme: IconThemeData(color: SuokeDesignTokens.text(context)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildGuideCard(),
            const SizedBox(height: 12),
            _buildFilePicker(),
            if (_fileName != null) ...[
              const SizedBox(height: 12),
              _buildFileInfoCard(),
            ],
            if (_fileBytes != null) ...[
              const SizedBox(height: 12),
              _buildUploadButton(),
            ],
            if (_uploading) ...[
              const SizedBox(height: 12),
              _buildUploadingCard(),
            ],
            if (_error != null) ...[
              const SizedBox(height: 12),
              _buildErrorBanner(),
            ],
            if (_uploadResult != null) ...[
              const SizedBox(height: 12),
              _buildResultCard(),
            ],
            if (_aiStatus != null) ...[
              const SizedBox(height: 12),
              _buildAiStatusCard(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildGuideCard() {
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
          Row(
            children: [
              const Icon(Icons.info_outline,
                  color: SuokeDesignTokens.accent, size: 16),
              const SizedBox(width: 6),
              Text('上传说明',
                  style: TextStyle(
                      color: SuokeDesignTokens.text(context),
                      fontSize: 14,
                      fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 8),
          _guideLine('支持 .xlsx / .csv 文件，单次最多 500 个产品'),
          _guideLine(
              '首行表头须包含：名称、分类、最低价、最高价、单位、描述、标签、库存状态、图片URL'),
          _guideLine('上传成功后自动为产品生成 AI 文案（后台任务，可实时查看进度）'),
        ],
      ),
    );
  }

  Widget _guideLine(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(text,
          style: TextStyle(
              color: SuokeDesignTokens.textSub(context),
              fontSize: 12,
              height: 1.5)),
    );
  }

  Widget _buildFilePicker() {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: _uploading ? null : _pickFile,
        icon: const Icon(Icons.attach_file),
        label: const Text('选择文件'),
        style: OutlinedButton.styleFrom(
          foregroundColor: SuokeDesignTokens.text(context),
          side: BorderSide(color: SuokeDesignTokens.borderClr(context)),
          padding: const EdgeInsets.symmetric(vertical: 12),
        ),
      ),
    );
  }

  Widget _buildFileInfoCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Row(
        children: [
          const Icon(Icons.description_outlined,
              color: SuokeDesignTokens.accent, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(_fileName ?? '',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
          const SizedBox(width: 8),
          Text(_fileSizeLabel ?? '',
              style:
                  TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildUploadButton() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: _uploading ? null : _upload,
        child: const Text('开始上传'),
      ),
    );
  }

  Widget _buildUploadingCard() {
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
          Text('正在上传并解析文件...',
              style:
                  TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        ],
      ),
    );
  }

  Widget _buildErrorBanner() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.danger.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
            color: SuokeDesignTokens.danger.withValues(alpha: 0.4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: SuokeDesignTokens.danger, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(_error ?? '',
                style: const TextStyle(color: SuokeDesignTokens.danger, fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _buildResultCard() {
    final data = _uploadResult!;
    final success = (data['success_count'] as num?)?.toInt() ?? 0;
    final failed = (data['failed_count'] as num?)?.toInt() ?? 0;
    final aiPending = (data['ai_jobs_pending'] as num?)?.toInt() ?? 0;
    final results = (data['results'] as List?) ?? [];
    final failures = results
        .whereType<Map>()
        .where((r) => r['success'] != true)
        .toList();

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
          Text('上传结果',
              style: TextStyle(
                  color: SuokeDesignTokens.text(context),
                  fontSize: 15,
                  fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Row(
            children: [
              _statItem('成功', success, SuokeDesignTokens.success),
              _statItem('失败', failed,
                  failed > 0 ? SuokeDesignTokens.danger : SuokeDesignTokens.textSub(context)),
              _statItem('AI 文案', aiPending,
                  aiPending > 0 ? SuokeDesignTokens.accent : SuokeDesignTokens.textSub(context)),
            ],
          ),
          if (failures.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('失败明细',
                style: TextStyle(
                    color: SuokeDesignTokens.accent,
                    fontSize: 13,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            ...failures.map((r) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.close,
                          color: SuokeDesignTokens.danger, size: 14),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          '${r['name']?.toString() ?? '未命名'}：${r['error']?.toString() ?? '未知错误'}',
                          style: TextStyle(
                              color: SuokeDesignTokens.textSub(context),
                              fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                )),
          ],
        ],
      ),
    );
  }

  Widget _statItem(String label, int value, Color color) {
    return Expanded(
      child: Column(
        children: [
          Text('$value',
              style: TextStyle(
                  color: color, fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label,
              style:
                  TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
        ],
      ),
    );
  }

  Widget _buildAiStatusCard() {
    final data = _aiStatus!;
    final total = (data['total'] as num?)?.toInt() ?? 0;
    final completed = (data['completed'] as num?)?.toInt() ?? 0;
    final failed = (data['failed'] as num?)?.toInt() ?? 0;
    final done = completed + failed;
    final isRunning = data['in_progress'] != false;

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
          Row(
            children: [
              const Icon(Icons.auto_awesome,
                  color: SuokeDesignTokens.accent, size: 16),
              const SizedBox(width: 6),
              Text('AI 文案生成',
                  style: TextStyle(
                      color: SuokeDesignTokens.text(context),
                      fontSize: 14,
                      fontWeight: FontWeight.bold)),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: total > 0 ? done / total : null,
              minHeight: 6,
              backgroundColor: SuokeDesignTokens.bg(context),
            ),
          ),
          const SizedBox(height: 8),
          Text(isRunning ? '生成中：$done / $total' : '已完成：$done / $total',
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 12)),
        ],
      ),
    );
  }
}
