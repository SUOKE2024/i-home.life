import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api.dart';
import '../theme/suoke_theme.dart';

/// 语音任务面板（语音智能体编排）
///
/// 对齐 Web 端 workbench 语音任务面板：
/// - 一句话启动后台 Agent 任务（支持多意图并行）
/// - 轮询任务进度（3s），可取消运行中任务
/// - 后端 flag `voice_agent_orchestration_enabled` 未启用时提示并停止轮询
class VoiceTaskPanel extends StatefulWidget {
  final String? projectId;

  const VoiceTaskPanel({super.key, this.projectId});

  /// 以底部弹层方式打开语音任务面板
  static Future<void> show(BuildContext context, {String? projectId}) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => VoiceTaskPanel(projectId: projectId),
    );
  }

  @override
  State<VoiceTaskPanel> createState() => _VoiceTaskPanelState();
}

class _VoiceTaskPanelState extends State<VoiceTaskPanel> {
  final _inputCtrl = TextEditingController();
  final _api = ApiClient();

  List<Map<String, dynamic>> _tasks = [];
  String _note = '';
  bool _launching = false;
  bool _disabled = false; // flag 未启用
  Timer? _pollTimer;

  static const _intentLabels = {
    'design': '设计方案',
    'budget': '预算分析',
    'procurement': '物料采购',
    'construction': '施工进度',
    'qa_inspector': '质量检查',
    'settlement': '结算对账',
    'concierge': '客服咨询',
    'ar_measurement': 'AR 测量',
  };

  static const _statusLabels = {
    'running': '进行中',
    'done': '已完成',
    'failed': '失败',
    'cancelled': '已取消',
  };

  @override
  void initState() {
    super.initState();
    _refresh();
    _startPoll();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _inputCtrl.dispose();
    super.dispose();
  }

  void _startPoll() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) => _refresh());
  }

  void _stopPoll() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _refresh() async {
    final r = await _api.listVoiceTasks();
    if (!mounted) return;
    if (r.isSuccess && r.data is Map<String, dynamic>) {
      final list = (r.data['tasks'] as List<dynamic>?) ?? [];
      setState(() {
        _tasks = list.whereType<Map<String, dynamic>>().toList();
        _disabled = false;
      });
    } else if (r.statusCode == 503) {
      setState(() {
        _disabled = true;
        _note = '语音智能体编排未启用（voice_agent_orchestration_enabled）';
      });
      _stopPoll();
    }
    // 其他错误（如网络抖动）静默，等待下一轮轮询
  }

  Future<void> _launch() async {
    final text = _inputCtrl.text.trim();
    if (text.isEmpty || _launching) return;
    _inputCtrl.clear();
    setState(() => _launching = true);
    final r = await _api.orchestrateVoice(text, projectId: widget.projectId);
    if (!mounted) return;
    setState(() => _launching = false);
    if (r.isSuccess && r.data is Map<String, dynamic>) {
      setState(() => _note = (r.data['reply'] ?? '').toString());
      unawaited(_refresh());
    } else if (r.statusCode == 503) {
      setState(() {
        _disabled = true;
        _note = '语音智能体编排未启用（voice_agent_orchestration_enabled）';
      });
      _stopPoll();
    } else {
      setState(() => _note = '启动失败：${r.error ?? '未知错误'}');
    }
  }

  Future<void> _cancel(Map<String, dynamic> task) async {
    final seq = task['seq'];
    final r = await _api.orchestrateVoice('取消任务 $seq');
    if (!mounted) return;
    if (r.isSuccess && r.data is Map<String, dynamic>) {
      setState(() => _note = (r.data['reply'] ?? '').toString());
    }
    unawaited(_refresh());
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'running':
        return SuokeDesignTokens.warning;
      case 'done':
        return SuokeDesignTokens.success;
      case 'failed':
        return SuokeDesignTokens.danger;
      default:
        return SuokeDesignTokens.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: Container(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.of(context).size.height * 0.7,
        ),
        decoration: const BoxDecoration(
          color: SuokeDesignTokens.surface1,
          borderRadius: BorderRadius.vertical(
            top: Radius.circular(SuokeDesignTokens.radiusLg),
          ),
          border: Border(top: BorderSide(color: SuokeDesignTokens.border)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildHeader(),
            if (!_disabled) _buildLaunchBar(),
            if (_note.isNotEmpty) _buildNote(),
            Flexible(child: _buildTaskList()),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: SuokeDesignTokens.spacingLg,
        vertical: SuokeDesignTokens.spacingMd,
      ),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: SuokeDesignTokens.border)),
      ),
      child: Row(
        children: [
          const Icon(Icons.task_alt, size: 18, color: SuokeDesignTokens.accent),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          const Expanded(
            child: Text(
              '语音任务',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: SuokeDesignTokens.fontSizeMd,
                color: SuokeDesignTokens.textPrimary,
              ),
            ),
          ),
          GestureDetector(
            onTap: () => Navigator.of(context).pop(),
            child: const Icon(Icons.close, size: 20, color: SuokeDesignTokens.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildLaunchBar() {
    return Padding(
      padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _inputCtrl,
              style: const TextStyle(
                fontSize: SuokeDesignTokens.fontSizeMd,
                color: SuokeDesignTokens.textPrimary,
              ),
              decoration: InputDecoration(
                hintText: '试试：帮我设计客厅，同时做份预算',
                hintStyle: const TextStyle(
                  fontSize: SuokeDesignTokens.fontSizeSm,
                  color: SuokeDesignTokens.textMuted,
                ),
                filled: true,
                fillColor: SuokeDesignTokens.inputBg,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: SuokeDesignTokens.spacingMd,
                  vertical: SuokeDesignTokens.spacingSm,
                ),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
                  borderSide: const BorderSide(color: SuokeDesignTokens.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusInput),
                  borderSide: const BorderSide(color: SuokeDesignTokens.border),
                ),
              ),
              onSubmitted: (_) => _launch(),
            ),
          ),
          const SizedBox(width: SuokeDesignTokens.spacingSm),
          FilledButton(
            onPressed: _launching ? null : _launch,
            style: FilledButton.styleFrom(
              backgroundColor: SuokeDesignTokens.accent,
              foregroundColor: Colors.black,
              padding: const EdgeInsets.symmetric(
                horizontal: SuokeDesignTokens.spacingLg,
                vertical: SuokeDesignTokens.spacingMd,
              ),
            ),
            child: Text(_launching ? '启动中' : '启动'),
          ),
        ],
      ),
    );
  }

  Widget _buildNote() {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(horizontal: SuokeDesignTokens.spacingMd),
      padding: const EdgeInsets.all(SuokeDesignTokens.spacingSm),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.surface2,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
      ),
      child: Text(
        _note,
        style: const TextStyle(
          fontSize: SuokeDesignTokens.fontSizeSm,
          color: SuokeDesignTokens.textSecondary,
        ),
      ),
    );
  }

  Widget _buildTaskList() {
    if (_disabled) {
      return const SizedBox(height: SuokeDesignTokens.spacingXl);
    }
    if (_tasks.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(SuokeDesignTokens.spacingXl),
        child: Text(
          '暂无语音任务，输入指令启动第一个后台任务',
          style: TextStyle(
            fontSize: SuokeDesignTokens.fontSizeSm,
            color: SuokeDesignTokens.textMuted,
          ),
        ),
      );
    }
    return ListView.separated(
      shrinkWrap: true,
      padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
      itemCount: _tasks.length,
      separatorBuilder: (_, _) => const SizedBox(height: SuokeDesignTokens.spacingSm),
      itemBuilder: (_, i) => _buildTaskItem(_tasks[i]),
    );
  }

  Widget _buildTaskItem(Map<String, dynamic> task) {
    final status = (task['status'] ?? '').toString();
    final seq = task['seq'];
    final intent = (task['intent'] ?? '').toString();
    final command = (task['command'] ?? '').toString();
    final reply = (task['reply'] ?? '').toString();
    final error = (task['error'] ?? '').toString();
    final isRunning = status == 'running';

    return Container(
      padding: const EdgeInsets.all(SuokeDesignTokens.spacingMd),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.surface2,
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
        border: Border.all(color: SuokeDesignTokens.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  '#$seq ${_intentLabels[intent] ?? intent}',
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: SuokeDesignTokens.fontSizeMd,
                    color: SuokeDesignTokens.textPrimary,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: _statusColor(status).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                ),
                child: Text(
                  _statusLabels[status] ?? status,
                  style: TextStyle(
                    fontSize: SuokeDesignTokens.fontSizeXs,
                    color: _statusColor(status),
                  ),
                ),
              ),
              if (isRunning) ...[
                const SizedBox(width: SuokeDesignTokens.spacingSm),
                GestureDetector(
                  onTap: () => _cancel(task),
                  child: const Text(
                    '取消',
                    style: TextStyle(
                      fontSize: SuokeDesignTokens.fontSizeSm,
                      color: SuokeDesignTokens.danger,
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: SuokeDesignTokens.spacingXs),
          Text(
            command,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: SuokeDesignTokens.fontSizeSm,
              color: SuokeDesignTokens.textSecondary,
            ),
          ),
          if (reply.isNotEmpty) ...[
            const SizedBox(height: SuokeDesignTokens.spacingXs),
            Text(
              reply,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: SuokeDesignTokens.fontSizeSm,
                color: SuokeDesignTokens.textPrimary,
              ),
            ),
          ],
          if (error.isNotEmpty) ...[
            const SizedBox(height: SuokeDesignTokens.spacingXs),
            Text(
              error,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: SuokeDesignTokens.fontSizeSm,
                color: SuokeDesignTokens.danger,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
