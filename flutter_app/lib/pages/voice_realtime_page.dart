import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import '../theme/suoke_theme.dart';
import '../services/api.dart';
import '../services/voice_realtime_service.dart';

/// 实时语音交互页（文本输入模式，项目未引入录音依赖）。
///
/// 通过 WebSocket 连接后端 `/voice/realtime`（mock/realtime 双模式），
/// 另附 REST 快捷指令区：processVoice 指令解析 + 语音任务列表。
class VoiceRealtimePage extends StatefulWidget {
  const VoiceRealtimePage({super.key});

  @override
  State<VoiceRealtimePage> createState() => _VoiceRealtimePageState();
}

class _Msg {
  final String role; // user / assistant / tool / system
  final String text;
  final bool isError;
  const _Msg(this.role, this.text, {this.isError = false});
}

class _VoiceRealtimePageState extends State<VoiceRealtimePage> {
  final ApiClient _api = ApiClient();
  final VoiceRealtimeService _voice = VoiceRealtimeService();

  final TextEditingController _msgCtrl = TextEditingController();
  final TextEditingController _restCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();

  final List<_Msg> _messages = [];
  bool _assistantInProgress = false;

  // REST 快捷指令
  bool _restLoading = false;
  Map<String, dynamic>? _restResult;
  String? _restError;

  // 语音任务
  bool _tasksLoading = false;
  List<dynamic> _tasks = [];
  String? _tasksError;

  @override
  void initState() {
    super.initState();
    _voice.onTranscript = _onTranscript;
    _voice.onResponseDone = _onResponseDone;
    _voice.onError = _onError;
    _voice.onToolCall = _onToolCall;
    _connect();
  }

  @override
  void dispose() {
    _voice.onTranscript = null;
    _voice.onResponseDone = null;
    _voice.onError = null;
    _voice.onToolCall = null;
    unawaited(_voice.disconnect());
    _msgCtrl.dispose();
    _restCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  // ── 连接管理 ──

  Future<void> _connect() async {
    final token = _api.token;
    if (token == null || token.isEmpty) {
      if (mounted) {
        _showSnack('请先登录后再使用实时语音');
        setState(() {
          _messages.add(
              const _Msg('system', '未登录，无法建立实时语音连接', isError: true));
        });
      }
      return;
    }
    if (mounted) setState(() {}); // 反映 connecting 状态
    await _voice.connect(token: token);
    if (mounted) setState(() {}); // 反映连接结果
  }

  Future<void> _reconnect() async {
    await _voice.disconnect();
    await _connect();
  }

  // ── 服务回调 ──

  void _onTranscript(String text, bool isFinal) {
    if (!mounted) return;
    setState(() {
      if (_assistantInProgress &&
          _messages.isNotEmpty &&
          _messages.last.role == 'assistant') {
        _messages[_messages.length - 1] =
            _Msg('assistant', _messages.last.text + text);
      } else {
        _messages.add(_Msg('assistant', text));
      }
      _assistantInProgress = !isFinal;
    });
    _scrollToBottom();
  }

  void _onResponseDone() {
    if (!mounted) return;
    setState(() {
      _assistantInProgress = false;
      _messages.add(const _Msg('system', '— 本轮回复完成 —'));
    });
    _scrollToBottom();
  }

  void _onToolCall(String name, Map<String, dynamic> result) {
    if (!mounted) return;
    final summary = result.isEmpty ? '' : _summary(result);
    setState(() {
      _messages.add(
          _Msg('tool', '调用工具：$name${summary.isEmpty ? '' : '\n$summary'}'));
    });
    _scrollToBottom();
  }

  void _onError(String message) {
    if (!mounted) return;
    setState(() {
      _messages.add(_Msg('system', '错误：$message', isError: true));
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollCtrl.hasClients) return;
      _scrollCtrl.jumpTo(_scrollCtrl.position.maxScrollExtent);
    });
  }

  // ── 交互 ──

  void _sendMessage() {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty) return;
    if (!_voice.isConnected) {
      _showSnack('未连接，请先点击重连');
      return;
    }
    setState(() {
      _assistantInProgress = false;
      _messages.add(_Msg('user', text));
    });
    _msgCtrl.clear();
    _voice.sendText(text);
    _scrollToBottom();
  }

  Future<void> _processRest() async {
    final text = _restCtrl.text.trim();
    if (text.isEmpty) {
      _showSnack('请输入指令文本');
      return;
    }
    setState(() {
      _restLoading = true;
      _restError = null;
      _restResult = null;
    });
    final result = await _api.processVoice(text);
    if (!mounted) return;
    setState(() {
      _restLoading = false;
      if (result.isSuccess) {
        final data = result.data;
        _restResult = data is Map ? Map<String, dynamic>.from(data) : null;
      } else {
        _restResult = null;
        _restError = '处理失败：${result.error ?? '未知错误'}';
      }
    });
  }

  Future<void> _loadVoiceTasks() async {
    setState(() {
      _tasksLoading = true;
      _tasksError = null;
    });
    final result = await _api.listVoiceTasks();
    if (!mounted) return;
    setState(() {
      _tasksLoading = false;
      if (result.isSuccess) {
        final data = result.data;
        if (data is List) {
          _tasks = data;
        } else if (data is Map && data['tasks'] is List) {
          _tasks = data['tasks'] as List;
        } else {
          _tasks = [];
        }
      } else {
        _tasks = [];
        _tasksError = '任务加载失败：${result.error ?? '未知错误'}';
      }
    });
  }

  void _showSnack(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  // ── UI 构建 ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: SuokeDesignTokens.bg(context),
      appBar: AppBar(
        backgroundColor: SuokeDesignTokens.bg(context),
        title: Text('实时语音',
            style: TextStyle(color: SuokeDesignTokens.text(context))),
        iconTheme: IconThemeData(color: SuokeDesignTokens.text(context)),
      ),
      body: Column(
        children: [
          _buildStatusBar(),
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState('暂无消息，输入文字开始对话', Icons.chat_bubble_outline)
                : ListView.builder(
                    controller: _scrollCtrl,
                    padding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) =>
                        _buildMessageBubble(_messages[index]),
                  ),
          ),
          _buildInputBar(),
          _buildRestSection(),
        ],
      ),
    );
  }

  Widget _buildStatusBar() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      color: SuokeDesignTokens.bg(context),
      child: Row(
        children: [
          _buildStatusChip(),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '文本输入模式 · WebSocket 实时交互',
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusChip() {
    String label;
    Color color;
    switch (_voice.status) {
      case VoiceConnectionStatus.connected:
        label = '已连接';
        color = SuokeDesignTokens.success;
        break;
      case VoiceConnectionStatus.connecting:
        label = '连接中...';
        color = SuokeDesignTokens.warning;
        break;
      case VoiceConnectionStatus.error:
        label = '连接异常';
        color = SuokeDesignTokens.danger;
        break;
      case VoiceConnectionStatus.disconnected:
        label = '未连接';
        color = SuokeDesignTokens.textSub(context);
        break;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle, size: 8, color: color),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(
                  color: color, fontSize: 12, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(_Msg m) {
    switch (m.role) {
      case 'user':
        return Align(
          alignment: Alignment.centerRight,
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            constraints: const BoxConstraints(maxWidth: 300),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.accent.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                  color: SuokeDesignTokens.accent.withValues(alpha: 0.4)),
            ),
            child: Text(m.text,
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
        );
      case 'assistant':
        return Align(
          alignment: Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            constraints: const BoxConstraints(maxWidth: 300),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.card(context),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: SuokeDesignTokens.borderClr(context)),
            ),
            child: Text(m.text,
                style: TextStyle(
                    color: SuokeDesignTokens.text(context), fontSize: 13)),
          ),
        );
      case 'tool':
        return Align(
          alignment: Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(10),
            constraints: const BoxConstraints(maxWidth: 320),
            decoration: BoxDecoration(
              color: SuokeDesignTokens.bg(context),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: SuokeDesignTokens.borderClr(context)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.handyman_outlined,
                        color: SuokeDesignTokens.accent, size: 13),
                    SizedBox(width: 4),
                    Text('工具调用',
                        style: TextStyle(
                            color: SuokeDesignTokens.accent,
                            fontSize: 11,
                            fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 4),
                Text(m.text,
                    style: TextStyle(
                        color: SuokeDesignTokens.textSub(context),
                        fontSize: 11)),
              ],
            ),
          ),
        );
      case 'system':
      default:
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Center(
            child: Text(
              m.text,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: m.isError
                    ? SuokeDesignTokens.danger
                    : SuokeDesignTokens.textSub(context),
                fontSize: 11,
              ),
            ),
          ),
        );
    }
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bg(context),
        border:
            Border(top: BorderSide(color: SuokeDesignTokens.borderClr(context))),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _msgCtrl,
              style: TextStyle(color: SuokeDesignTokens.text(context)),
              decoration: const InputDecoration(
                hintText: '输入消息...',
                isDense: true,
              ),
              onSubmitted: (_) => _sendMessage(),
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            height: 44,
            child: ElevatedButton(
              onPressed: _sendMessage,
              child: const Text('发送'),
            ),
          ),
          const SizedBox(width: 4),
          IconButton(
            tooltip: '重连',
            onPressed: _reconnect,
            icon: Icon(Icons.refresh, color: SuokeDesignTokens.textSub(context)),
          ),
        ],
      ),
    );
  }

  Widget _buildRestSection() {
    return ExpansionTile(
      title: Text('REST 快捷指令',
          style: TextStyle(
              color: SuokeDesignTokens.text(context),
              fontSize: 14,
              fontWeight: FontWeight.bold)),
      iconColor: SuokeDesignTokens.textSub(context),
      collapsedIconColor: SuokeDesignTokens.textSub(context),
      backgroundColor: SuokeDesignTokens.card(context),
      collapsedBackgroundColor: SuokeDesignTokens.card(context),
      shape: const Border(top: BorderSide(color: SuokeDesignTokens.border)),
      collapsedShape:
          const Border(top: BorderSide(color: SuokeDesignTokens.border)),
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _restCtrl,
                      style: TextStyle(color: SuokeDesignTokens.text(context)),
                      decoration: const InputDecoration(
                        hintText: '输入指令文本，如「帮我查一下装修预算」',
                        isDense: true,
                      ),
                      onSubmitted: (_) => _processRest(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    height: 44,
                    child: ElevatedButton(
                      onPressed: _restLoading ? null : _processRest,
                      child: const Text('发送'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                height: 40,
                child: OutlinedButton(
                  onPressed: _tasksLoading ? null : _loadVoiceTasks,
                  child: const Text('查看语音任务'),
                ),
              ),
              const SizedBox(height: 8),
              _buildRestResult(),
              _buildTaskList(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildRestResult() {
    if (_restLoading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(
          child: CircularProgressIndicator(color: SuokeDesignTokens.accent),
        ),
      );
    }
    if (_restError != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(_restError!,
            style: const TextStyle(color: SuokeDesignTokens.danger, fontSize: 12)),
      );
    }
    final r = _restResult;
    if (r == null) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.bg(context),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: SuokeDesignTokens.borderClr(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('处理结果',
              style: TextStyle(
                  color: SuokeDesignTokens.accent,
                  fontSize: 12,
                  fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          for (final e in r.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                '${e.key}: ${_summary(e.value)}',
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildTaskList() {
    if (_tasksLoading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 12),
        child: Center(
          child: CircularProgressIndicator(color: SuokeDesignTokens.accent),
        ),
      );
    }
    if (_tasksError != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text(_tasksError!,
            style: const TextStyle(color: SuokeDesignTokens.danger, fontSize: 12)),
      );
    }
    if (_tasks.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Text('暂无语音任务',
            style:
                TextStyle(color: SuokeDesignTokens.textSub(context), fontSize: 12)),
      );
    }
    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 220),
      child: ListView.builder(
        shrinkWrap: true,
        itemCount: _tasks.length,
        itemBuilder: (context, index) => _buildTaskItem(_tasks[index]),
      ),
    );
  }

  Widget _buildTaskItem(dynamic task) {
    final m =
        task is Map ? Map<String, dynamic>.from(task) : <String, dynamic>{};
    final taskId = m['task_id']?.toString() ??
        m['id']?.toString() ??
        '任务 #${_tasks.indexOf(task) + 1}';
    final status = m['status']?.toString() ?? '—';
    final command = m['command']?.toString() ?? m['text']?.toString() ?? '';
    final result = m['result'];
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
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
              Expanded(
                child: Text(taskId,
                    style: TextStyle(
                        color: SuokeDesignTokens.text(context),
                        fontSize: 12,
                        fontWeight: FontWeight.bold)),
              ),
              _statusBadge(status),
            ],
          ),
          if (command.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(command,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 12)),
          ],
          if (result != null) ...[
            const SizedBox(height: 4),
            Text('结果：${_summary(result)}',
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    color: SuokeDesignTokens.textSub(context), fontSize: 11)),
          ],
        ],
      ),
    );
  }

  Widget _statusBadge(String status) {
    Color color;
    switch (status) {
      case 'running':
      case 'pending':
      case 'queued':
        color = SuokeDesignTokens.warning;
        break;
      case 'success':
      case 'completed':
      case 'done':
        color = SuokeDesignTokens.success;
        break;
      case 'failed':
      case 'error':
      case 'cancelled':
        color = SuokeDesignTokens.danger;
        break;
      default:
        color = SuokeDesignTokens.textSub(context);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(status, style: TextStyle(color: color, fontSize: 11)),
    );
  }

  String _summary(Object? v) {
    if (v is Map || v is List) {
      final s = jsonEncode(v);
      return s.length > 200 ? '${s.substring(0, 200)}...' : s;
    }
    return v?.toString() ?? '';
  }

  Widget _buildEmptyState(String message, IconData icon) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 64, color: SuokeDesignTokens.textSub(context)),
          const SizedBox(height: 16),
          Text(message,
              style: TextStyle(
                  color: SuokeDesignTokens.textSub(context), fontSize: 13)),
        ],
      ),
    );
  }
}
