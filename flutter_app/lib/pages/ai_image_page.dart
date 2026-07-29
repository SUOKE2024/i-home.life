import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../config.dart';
import '../services/api.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';

class AIImagePage extends StatefulWidget {
  final String projectId;
  const AIImagePage({super.key, required this.projectId});

  @override
  State<AIImagePage> createState() => _AIImagePageState();
}

class _AIImagePageState extends State<AIImagePage>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();

  List<dynamic> _jobs = [];
  List<dynamic> _presets = [];
  bool _loadingJobs = false;
  bool _loadingPresets = false;
  String? _errorJobs;
  String? _errorPresets;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadJobs();
    _loadPresets();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _tabController.dispose();
    super.dispose();
  }

  // ── 数据加载 ──

  Future<void> _loadJobs() async {
    setState(() {
      _loadingJobs = true;
      _errorJobs = null;
    });
    final result = await _api.aiImageListJobs(widget.projectId);
    if (result.isSuccess) {
      setState(() {
        _jobs = (result.data as List?) ?? [];
      });
      _maybeStartPolling();
    } else {
      if (mounted) {
        setState(() => _errorJobs = '加载失败，请检查网络后重试');
      }
    }
    if (mounted) setState(() => _loadingJobs = false);
  }

  Future<void> _loadPresets() async {
    setState(() {
      _loadingPresets = true;
      _errorPresets = null;
    });
    final result = await _api.aiImageListPresets();
    if (result.isSuccess) {
      setState(() {
        _presets = (result.data as List?) ?? [];
      });
    } else {
      if (mounted) {
        setState(() => _errorPresets = '加载失败，请检查网络后重试');
      }
    }
    if (mounted) setState(() => _loadingPresets = false);
  }

  // ── 轮询处理中任务 ──

  void _maybeStartPolling() {
    final hasProcessing =
        _jobs.any((j) => (j['status'] as String?) == 'processing');
    if (hasProcessing && _pollTimer == null) {
      _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _pollJobs());
    } else if (!hasProcessing && _pollTimer != null) {
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  Future<void> _pollJobs() async {
    final result = await _api.aiImageListJobs(widget.projectId);
    if (!result.isSuccess) return;
    if (!mounted) return;
    setState(() {
      _jobs = (result.data as List?) ?? [];
    });
    _maybeStartPolling();
  }

  // ── 创建任务 ──

  Future<void> _showCreateJobDialog({Map<String, dynamic>? preset}) async {
    final promptCtrl = TextEditingController(
        text: preset?['prompt_template'] as String? ?? '');
    final negativeCtrl = TextEditingController(
        text: preset?['negative_prompt_template'] as String? ?? '');
    final inputCtrl = TextEditingController();
    String jobType = preset?['category'] as String? ?? 'style_transfer';
    String modelName = 'stable-diffusion-xl';
    double guidanceScale = 7.5;
    int numSteps = 30;

    final formKey = GlobalKey<FormState>();

    await showDialog<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: SuokeDesignTokens.card(context),
          title: Text(preset != null ? '基于模板创建任务' : '创建生成任务',
              style: TextStyle(color: SuokeDesignTokens.text(context))),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextFormField(
                    controller: promptCtrl,
                    maxLines: 3,
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('提示词 Prompt'),
                    validator: (v) =>
                        (v == null || v.isEmpty) ? '请输入提示词' : null,
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: negativeCtrl,
                    maxLines: 2,
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('负面提示词（可选）'),
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: inputCtrl,
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('输入图片 URL（可选）'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: jobType,
                    dropdownColor: SuokeDesignTokens.card(context),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('任务类型'),
                    items: const [
                      DropdownMenuItem(value: 'style_transfer', child: Text('风格迁移')),
                      DropdownMenuItem(value: 'img2img', child: Text('图生图')),
                      DropdownMenuItem(value: 'inpaint', child: Text('局部重绘')),
                    ],
                    onChanged: (v) {
                      if (v != null) setDialogState(() => jobType = v);
                    },
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: modelName,
                    dropdownColor: SuokeDesignTokens.card(context),
                    style: TextStyle(color: SuokeDesignTokens.text(context)),
                    decoration: _inputDecoration('模型'),
                    items: const [
                      DropdownMenuItem(
                          value: 'stable-diffusion-xl',
                          child: Text('Stable Diffusion XL')),
                      DropdownMenuItem(
                          value: 'stable-diffusion-v1-5',
                          child: Text('Stable Diffusion v1.5')),
                    ],
                    onChanged: (v) {
                      if (v != null) setDialogState(() => modelName = v);
                    },
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Text('引导强度', style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
                      Expanded(
                        child: Slider(
                          value: guidanceScale,
                          min: 1.0,
                          max: 30.0,
                          divisions: 29,
                          activeColor: SuokeDesignTokens.accent,
                          label: guidanceScale.toStringAsFixed(1),
                          onChanged: (v) =>
                              setDialogState(() => guidanceScale = v),
                        ),
                      ),
                      Text(guidanceScale.toStringAsFixed(1),
                          style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
                    ],
                  ),
                  Row(
                    children: [
                      Text('推理步数', style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Slider(
                          value: numSteps.toDouble(),
                          min: 1,
                          max: 100,
                          divisions: 99,
                          activeColor: SuokeDesignTokens.accent,
                          label: '$numSteps',
                          onChanged: (v) =>
                              setDialogState(() => numSteps = v.round()),
                        ),
                      ),
                      Text('$numSteps',
                          style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: Text('取消', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
              onPressed: () async {
                if (!formKey.currentState!.validate()) return;
                Navigator.pop(ctx);
                await _createJob(
                  prompt: promptCtrl.text.trim(),
                  negativePrompt: negativeCtrl.text.trim(),
                  inputImageUrl: inputCtrl.text.trim(),
                  jobType: jobType,
                  modelName: modelName,
                  guidanceScale: guidanceScale,
                  numSteps: numSteps,
                );
              },
              child: const Text('创建'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _createJob({
    required String prompt,
    required String negativePrompt,
    required String inputImageUrl,
    required String jobType,
    required String modelName,
    required double guidanceScale,
    required int numSteps,
  }) async {
    final body = <String, dynamic>{
      'project_id': widget.projectId,
      'job_type': jobType,
      'prompt': prompt,
      'model_name': modelName,
      'guidance_scale': guidanceScale,
      'num_inference_steps': numSteps,
    };
    if (negativePrompt.isNotEmpty) body['negative_prompt'] = negativePrompt;
    if (inputImageUrl.isNotEmpty) body['input_image_url'] = inputImageUrl;

    final result = await _api.aiImageCreateJob(body);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('任务已创建')));
      }
      unawaited(_loadJobs());
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('创建失败：${result.error}')));
      }
    }
  }

  // ── 触发生成 ──

  Future<void> _processJob(String jobId) async {
    final result = await _api.aiImageProcessJob(jobId);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('已触发生成')));
      }
      unawaited(_loadJobs());
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('生成失败：${result.error}')));
      }
    }
  }

  // ── 删除任务 ──

  Future<void> _deleteJob(String jobId) async {
    final result = await _api.aiImageDeleteJob(jobId);
    if (result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('已删除')));
      }
      unawaited(_loadJobs());
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('删除失败：${result.error}')));
      }
    }
  }

  // ── 查看详情 ──

  Future<void> _showJobDetail(String jobId) async {
    final result = await _api.aiImageGetJob(jobId);
    if (!result.isSuccess) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('加载详情失败：${result.error}')));
      }
      return;
    }
    final job = result.data;
    if (!mounted) return;
    unawaited(showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: SuokeDesignTokens.card(context),
        title: Text('任务详情', style: TextStyle(color: SuokeDesignTokens.text(context))),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _detailRow('ID', job['id']?.toString() ?? ''),
              _detailRow('状态', job['status']?.toString() ?? ''),
              _detailRow('类型', job['job_type']?.toString() ?? ''),
              _detailRow('模型', job['model_name']?.toString() ?? ''),
              _detailRow('进度', '${job['progress_percent'] ?? 0}%'),
              _detailRow('引导强度', '${job['guidance_scale'] ?? 0}'),
              _detailRow('推理步数', '${job['num_inference_steps'] ?? 0}'),
              if (job['prompt'] != null)
                _detailRow('提示词', job['prompt'].toString()),
              if (job['negative_prompt'] != null)
                _detailRow('负面提示词', job['negative_prompt'].toString()),
              if (job['error_message'] != null)
                _detailRow('错误信息', job['error_message'].toString()),
              if (job['output_image_url'] != null) ...[
                const SizedBox(height: 12),
                Text('生成结果',
                    style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: CachedNetworkImage(
                    imageUrl: _resolveUrl(job['output_image_url'].toString()),
                    height: 200,
                    fit: BoxFit.cover,
                    placeholder: (context, url) => Container(
                      height: 200,
                      color: SuokeDesignTokens.borderClr(context),
                      child: const Center(
                          child: CircularProgressIndicator(strokeWidth: 2)),
                    ),
                    errorWidget: (context, url, error) => Container(
                      height: 200,
                      color: SuokeDesignTokens.borderClr(context),
                      child: Center(
                        child: Icon(Icons.broken_image,
                            color: SuokeDesignTokens.textSub(context), size: 40),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('关闭', style: TextStyle(color: SuokeDesignTokens.textSub(context))),
          ),
        ],
      ),
    ));
  }

  // ── 下载（打开图片） ──

  void _downloadJob(Map<String, dynamic> job) {
    final url = job['output_image_url'] as String?;
    if (url == null || url.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('暂无可下载的图片')));
      return;
    }
    final fullUrl = _resolveUrl(url);
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text('图片地址：$fullUrl')));
  }

  // ── 工具方法 ──

  String _resolveUrl(String url) {
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    return '${AppConfig.apiBaseUrl}$url';
  }

  InputDecoration _inputDecoration(String label) => InputDecoration(
        labelText: label,
        labelStyle: TextStyle(color: SuokeDesignTokens.textSub(context)),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: SuokeDesignTokens.borderClr(context)),
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: const BorderSide(color: SuokeDesignTokens.accent),
          borderRadius: BorderRadius.circular(8),
        ),
      );

  Widget _detailRow(String label, String value) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 80,
              child: Text(label,
                  style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 13)),
            ),
            Expanded(
              child: Text(value,
                  style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 13)),
            ),
          ],
        ),
      );

  // ── 状态 Chip ──

  Widget _statusChip(String? status) {
    Color color;
    String label;
    switch (status) {
      case 'processing':
        color = const Color(0xFF2196F3);
        label = '生成中';
        break;
      case 'completed':
        color = const Color(0xFF4CAF50);
        label = '已完成';
        break;
      case 'failed':
        color = const Color(0xFFF44336);
        label = '失败';
        break;
      default: // queued / pending
        color = const Color(0xFF9E9E9E);
        label = '待处理';
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 12)),
    );
  }

  // ── 时间格式化 ──

  String _formatTime(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    try {
      final dt = DateTime.parse(iso).toLocal();
      return '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return iso;
    }
  }

  // ── 构建 UI ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bg(context),
        foregroundColor: SuokeDesignTokens.text(context),
        title: const Text('AI 图片生成'),
        bottom: TabBar(
          controller: _tabController,
          labelColor: SuokeDesignTokens.accent,
          unselectedLabelColor: SuokeDesignTokens.textSub(context),
          indicatorColor: SuokeDesignTokens.accent,
          tabs: const [
            Tab(text: '生成任务'),
            Tab(text: '预设模板'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildJobsTab(),
          _buildPresetsTab(),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: SuokeDesignTokens.accent,
        foregroundColor: SuokeDesignTokens.bg(context),
        onPressed: () => _showCreateJobDialog(),
        child: const Icon(Icons.add),
      ),
    );
  }

  // ── 生成任务 Tab ──

  Widget _buildJobsTab() {
    if (_loadingJobs) {
      return const LoadingSkeleton(itemHeight: 90);
    }
    if (_errorJobs != null) {
      return ErrorRetryWidget(message: _errorJobs!, onRetry: _loadJobs);
    }
    if (_jobs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.image_outlined, size: 64, color: SuokeDesignTokens.textSub(context)),
            const SizedBox(height: 16),
            Text('暂无生成任务',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 16)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
              onPressed: () => _showCreateJobDialog(),
              icon: const Icon(Icons.add),
              label: const Text('创建任务'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      onRefresh: _loadJobs,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _jobs.length,
        itemBuilder: (context, index) => _buildJobCard(_jobs[index]),
      ),
    );
  }

  Widget _buildJobCard(dynamic raw) {
    final job = raw as Map<String, dynamic>;
    final status = job['status'] as String?;
    final outputUrl = job['output_image_url'] as String?;
    final prompt = job['prompt'] as String? ?? '';
    final promptSummary =
        prompt.isEmpty ? '（无提示词）' : (prompt.length > 50 ? '${prompt.substring(0, 50)}…' : prompt);
    final canProcess = status == 'queued' || status == 'pending' || status == 'failed';

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.card(context),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 顶部：状态 + 时间
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _statusChip(status),
                Text(_formatTime(job['created_at'] as String?),
                    style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
              ],
            ),
            const SizedBox(height: 10),
            // prompt 摘要
            Text(promptSummary,
                style: TextStyle(color: SuokeDesignTokens.text(context), fontSize: 14),
                maxLines: 2,
                overflow: TextOverflow.ellipsis),
            const SizedBox(height: 6),
            // 元信息
            Row(
              children: [
                Icon(Icons.style, size: 14, color: SuokeDesignTokens.textSub(context)),
                const SizedBox(width: 4),
                Text(job['job_type']?.toString() ?? '',
                    style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
                const SizedBox(width: 16),
                Icon(Icons.memory, size: 14, color: SuokeDesignTokens.textSub(context)),
                const SizedBox(width: 4),
                Text(job['model_name']?.toString() ?? '',
                    style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
                if (status == 'processing') ...[
                  const SizedBox(width: 16),
                  Text('${job['progress_percent'] ?? 0}%',
                      style: const TextStyle(color: Colors.blue, fontSize: 12)),
                ],
              ],
            ),
            // 结果图片
            if (outputUrl != null && outputUrl.isNotEmpty) ...[
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: CachedNetworkImage(
                  imageUrl: _resolveUrl(outputUrl),
                  height: 160,
                  width: double.infinity,
                  fit: BoxFit.cover,
                  placeholder: (context, url) => Container(
                    height: 160,
                    color: SuokeDesignTokens.borderClr(context),
                    child: const Center(
                        child: CircularProgressIndicator(strokeWidth: 2)),
                  ),
                  errorWidget: (context, url, error) => Container(
                    height: 160,
                    color: SuokeDesignTokens.borderClr(context),
                    child: Center(
                      child: Icon(Icons.broken_image,
                          color: SuokeDesignTokens.textSub(context), size: 36),
                    ),
                  ),
                ),
              ),
            ],
            const SizedBox(height: 12),
            // 操作按钮
            Row(
              children: [
                if (canProcess)
                  _actionBtn('生成', Icons.play_arrow, () => _processJob(job['id'])),
                if (canProcess) const SizedBox(width: 8),
                _actionBtn('详情', Icons.info_outline,
                    () => _showJobDetail(job['id'])),
                const SizedBox(width: 8),
                if (status == 'completed')
                  _actionBtn('下载', Icons.download,
                      () => _downloadJob(job)),
                const Spacer(),
                _actionBtn('删除', Icons.delete_outline, () => _deleteJob(job['id']),
                    isDanger: true),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionBtn(String label, IconData icon, VoidCallback onTap,
      {bool isDanger = false}) {
    final color = isDanger ? const Color(0xFFF44336) : SuokeDesignTokens.accent;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.4)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
            Text(label, style: TextStyle(color: color, fontSize: 12)),
          ],
        ),
      ),
    );
  }

  // ── 预设模板 Tab ──

  Widget _buildPresetsTab() {
    if (_loadingPresets) {
      return const LoadingSkeleton(itemHeight: 90);
    }
    if (_errorPresets != null) {
      return ErrorRetryWidget(message: _errorPresets!, onRetry: _loadPresets);
    }
    if (_presets.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.dashboard_outlined, size: 64, color: SuokeDesignTokens.textSub(context)),
            const SizedBox(height: 16),
            Text('暂无预设模板',
                style: TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 16)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(backgroundColor: SuokeDesignTokens.accent),
              onPressed: _loadPresets,
              icon: const Icon(Icons.refresh),
              label: const Text('刷新'),
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      onRefresh: _loadPresets,
      child: GridView.builder(
        padding: const EdgeInsets.all(16),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 0.72,
        ),
        itemCount: _presets.length,
        itemBuilder: (context, index) => _buildPresetCard(_presets[index]),
      ),
    );
  }

  Widget _buildPresetCard(dynamic raw) {
    final preset = raw as Map<String, dynamic>;
    final previewUrl = preset['preview_image_url'] as String?;
    final name = preset['name']?.toString() ?? '';
    final category = preset['category']?.toString() ?? '';
    final promptTemplate = preset['prompt_template'] as String? ?? '';
    final usageCount = preset['usage_count'] ?? 0;

    return GestureDetector(
      onTap: () => _showCreateJobDialog(preset: preset),
      child: Container(
        decoration: BoxDecoration(
          color: SuokeDesignTokens.card(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: SuokeDesignTokens.borderClr(context)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 示例图
            Expanded(
              flex: 3,
              child: ClipRRect(
                borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                child: previewUrl != null && previewUrl.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: _resolveUrl(previewUrl),
                        width: double.infinity,
                        fit: BoxFit.cover,
                        placeholder: (context, url) => Container(
                          color: SuokeDesignTokens.borderClr(context),
                          child: const Center(
                              child: CircularProgressIndicator(strokeWidth: 2)),
                        ),
                        errorWidget: (context, url, error) => Container(
                          color: SuokeDesignTokens.borderClr(context),
                          child: Center(
                            child: Icon(Icons.image_outlined,
                                color: SuokeDesignTokens.textSub(context), size: 32),
                          ),
                        ),
                      )
                    : Container(
                        color: SuokeDesignTokens.borderClr(context),
                        child: Center(
                          child: Icon(Icons.image_outlined,
                              color: SuokeDesignTokens.textSub(context), size: 32),
                        ),
                      ),
              ),
            ),
            // 信息
            Expanded(
              flex: 2,
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name,
                        style: TextStyle(
                            color: SuokeDesignTokens.text(context),
                            fontSize: 14,
                            fontWeight: FontWeight.bold),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(category,
                              style: const TextStyle(
                                  color: SuokeDesignTokens.accent, fontSize: 11)),
                        ),
                        const Spacer(),
                        Text('使用 $usageCount',
                            style: TextStyle(
                                color: SuokeDesignTokens.textSub(context), fontSize: 11)),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(promptTemplate,
                        style: TextStyle(
                            color: SuokeDesignTokens.textSub(context), fontSize: 11),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
