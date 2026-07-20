import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../main.dart' show ThemeState;
import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';
import '../services/agent_router.dart';
import '../services/api.dart';
import '../services/project_context.dart';
import '../services/sse_service.dart';
import '../services/voice_realtime_service.dart';
import '../services/websocket_service.dart';
import '../widgets/chat_message_card.dart';
import '../widgets/emoji_picker.dart';

class AIChatPage extends StatefulWidget {
  final String? projectId;
  final ProjectContext? projectContext;

  const AIChatPage({super.key, this.projectId, this.projectContext});

  @override
  State<AIChatPage> createState() => _AIChatPageState();
}

class _AIChatPageState extends State<AIChatPage> {
  final _msgCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final List<ChatMessage> _messages = [];
  final SseService _sse = SseService();
  final VoiceRealtimeService _voice = VoiceRealtimeService();
  final WebSocketService _ws = WebSocketService();
  String _selectedAgent = 'master';
  bool _isLoading = false;
  bool _isVoiceMode = false;
  String? _currentProjectId;
  String? _currentSessionId;

  StreamSubscription<SseEvent>? _sseSub;
  VoidCallback? _wsUnsubscribe;

  late final List<AgentInfo> _agents;

  /// 快览导航项（对齐 Web 端 .quick-nav）
  static const _quickNavItems = [
    ('主页', '#'),
    ('项目详情', 'project-detail'),
    ('物料管理', 'materials'),
    ('设置', 'settings'),
  ];

  static const _sessionKey = 'agent_session_id';

  @override
  void initState() {
    super.initState();
    _agents = AgentInfo.standardAgents;
    _connectWebSocket();
    _restoreSessionId();
  }

  Future<void> _restoreSessionId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _currentSessionId = prefs.getString(_sessionKey);
      // 若有已保存会话，加载历史消息
      if (_currentSessionId != null) {
        _loadSessionMessages();
      }
    } catch (_) {
      // SharedPreferences 不可用，忽略
    }
  }

  Future<void> _loadSessionMessages() async {
    if (_currentSessionId == null) return;
    try {
      final result = await ApiClient().getAgentSession(_currentSessionId!);
      if (result.isSuccess && result.data != null) {
        final data = result.data as Map<String, dynamic>;
        final msgs = (data['messages'] as List<dynamic>?) ?? [];
        if (msgs.isNotEmpty) {
          setState(() {
            _messages.clear();
            for (final m in msgs) {
              final role = (m['role'] ?? '').toString();
              final content = (m['content'] ?? '').toString();
              final agentType = (m['agent_type'] ?? '').toString();
              if (role == 'user') {
                _messages.add(ChatMessage.userText(text: content));
              } else {
                final agentKey = _backendToAgent(agentType);
                _messages.add(ChatMessage.agentText(text: content, agent: agentKey));
              }
            }
          });
        }
      }
    } catch (_) {
      // 网络/解析失败忽略，保留空消息列表
    }
  }

  Future<void> _persistSessionId(String? sessionId) async {
    _currentSessionId = sessionId;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (sessionId != null) {
        await prefs.setString(_sessionKey, sessionId);
      } else {
        await prefs.remove(_sessionKey);
      }
    } catch (_) {
      // SharedPreferences 不可用，忽略
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final pc = context.read<ProjectContext>();
    final pid = widget.projectId ?? widget.projectContext?.currentProjectId ?? pc.currentProjectId;
    if (pid != _currentProjectId) {
      _currentProjectId = pid;
      _connectWebSocket();
      if (pc.projects.isEmpty) {
        pc.loadProjects();
      }
    }
  }

  @override
  void dispose() {
    _msgCtrl.dispose();
    _scrollCtrl.dispose();
    _sseSub?.cancel();
    _wsUnsubscribe?.call();
    _ws.close();
    _voice.disconnect();
    _persistSessionId(null);
    super.dispose();
  }

  // ── 语音模式 ──

  void _toggleVoiceMode() {
    setState(() => _isVoiceMode = !_isVoiceMode);
    if (_isVoiceMode) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('语音模式已开启 — 说出问题，AI Agent 实时回复'),
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  // ── WebSocket 连接 ──

  Future<void> _connectWebSocket() async {
    final token = ApiClient().token;
    final pid = _currentProjectId;
    if (token == null || pid == null) return;

    _wsUnsubscribe?.call();
    _ws.close();

    try {
      await _ws.connect(pasetoToken: token, projectId: pid);
      _wsUnsubscribe = _ws.on('chat.message', _handleIncomingIM);
    } catch (_) {}
  }

  void _handleIncomingIM(dynamic data) {
    if (data is! Map<String, dynamic>) return;
    final msgId = data['id'] as String?;
    if (msgId != null && _ws.hasRendered(msgId)) return;
    if (msgId != null) _ws.markRendered(msgId);

    final senderName = data['sender_name'] as String?;
    final content = data['content'] as String? ?? '';
    final senderRole = data['sender_role'] as String? ?? '';

    const roleToAgent = {
      'homeowner': 'master', 'owner': 'master', 'admin': 'master',
      'designer': 'design',
      'contractor': 'construction', 'foreman': 'construction',
      'supplier': 'procurement',
    };
    final agentKey = roleToAgent[senderRole] ?? 'master';

    _addMessage(ChatMessage(
      type: ChatMessageType.text,
      agent: agentKey,
      displayName: senderName,
      isSelf: false,
      content: content,
      timestamp: DateTime.now(),
    ));
  }

  // ── 消息操作 ──

  void _addMessage(ChatMessage msg) {
    setState(() => _messages.add(msg));
    _scrollToBottom();
  }

  void _updateLastAgentMessage(String content, {String? agent}) {
    setState(() {
      for (int i = _messages.length - 1; i >= 0; i--) {
        final m = _messages[i];
        if (!m.isSelf && m.type == ChatMessageType.text) {
          _messages[i] = m.copyWith(content: content, agent: agent ?? m.agent);
          break;
        }
      }
    });
    _scrollToBottom();
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 120), () {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  // ── 发送消息 ──

  Future<void> _send() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty || _isLoading) return;
    _msgCtrl.clear();

    final route = AgentRouter.route(text);
    final targetAgent = route.needsClarify ? _selectedAgent : route.agent;
    final backendAgent = _agentToBackend(targetAgent);

    _addMessage(ChatMessage.userText(text: text));

    setState(() => _isLoading = true);

    final placeholder = ChatMessage.agentText(text: '', agent: targetAgent);
    _addMessage(placeholder);

    final history = <Map<String, dynamic>>[];
    final recentMsgs = _messages.length > 20
        ? _messages.sublist(_messages.length - 21, _messages.length - 1)
        : _messages.sublist(0, _messages.length - 1);
    for (final m in recentMsgs) {
      if (m.type != ChatMessageType.text) continue;
      history.add({
        'role': m.isSelf ? 'user' : 'assistant',
        'content': (m.content ?? '').length > 500
            ? m.content!.substring(0, 500)
            : (m.content ?? ''),
        'agent_type': m.agent ?? '',
      });
    }

    String fullContent = '';
    String currentAgent = targetAgent;

    try {
      _sseSub?.cancel();
      final stream = _sse.streamChat(
        text,
        agentType: backendAgent,
        projectId: _currentProjectId,
        history: history,
        sessionId: _currentSessionId,
      );

      _sseSub = stream.listen(
        (event) {
          if (event.sessionId != null) {
            _persistSessionId(event.sessionId);
          }
          switch (event.type) {
            case SseEventType.meta:
              if (event.agentType != null) {
                currentAgent = _backendToAgent(event.agentType!);
              }
            case SseEventType.token:
              fullContent += event.content ?? '';
              _updateLastAgentMessage(fullContent, agent: currentAgent);
            case SseEventType.done:
              if (event.content != null && event.content!.isNotEmpty) {
                _updateLastAgentMessage(event.content!, agent: currentAgent);
              }
              setState(() => _isLoading = false);
          }
        },
        onError: (e) {
          _updateLastAgentMessage('抱歉，AI 服务暂时不可用: ${e.toString().length > 80 ? e.toString().substring(0, 80) + '...' : e}', agent: 'master');
          setState(() => _isLoading = false);
        },
        onDone: () {
          setState(() => _isLoading = false);
        },
      );
    } catch (e) {
      _updateLastAgentMessage('抱歉，AI 服务暂时不可用: $e', agent: 'master');
      setState(() => _isLoading = false);
    }
  }

  void _showSessionList() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => _SessionListSheet(
        onSelect: (sessionId) {
          Navigator.pop(ctx);
          _persistSessionId(sessionId);
          _loadSessionMessages();
        },
        onNewChat: () {
          Navigator.pop(ctx);
          _persistSessionId(null);
          setState(() {
            _messages.clear();
            _messages.add(ChatMessage.agentText(
              text: '新对话开始。我是索克家居 AI 总控 Agent，请告诉我您的需求。',
              agent: 'master',
            ));
          });
        },
        currentSessionId: _currentSessionId,
      ),
    );
  }

  String _agentToBackend(String agentKey) {
    const map = {
      'master': 'orchestrator', 'design': 'design', 'budget': 'budget',
      'procurement': 'procurement', 'construction': 'construction',
      'quality': 'qa_inspector', 'settlement': 'settlement', 'support': 'concierge',
    };
    return map[agentKey] ?? 'orchestrator';
  }

  String _backendToAgent(String backendType) {
    const map = {
      'orchestrator': 'master', 'design': 'design', 'budget': 'budget',
      'procurement': 'procurement', 'construction': 'construction',
      'qa_inspector': 'quality', 'settlement': 'settlement', 'concierge': 'support',
    };
    return map[backendType] ?? 'master';
  }

  void _handleApproval(String decision, Map<String, dynamic> payload) {
    final changeId = payload['id']?.toString();
    if (changeId == null || changeId.isEmpty) return;

    _addMessage(ChatMessage.userText(
      text: decision == 'approve' ? '已同意该审批' : '已要求整改',
    ));

    ApiClient().approveChangeOrder(changeId, decision).then((result) {
      if (result.isSuccess) {
        _addMessage(ChatMessage.agentText(
          text: decision == 'approve' ? '变更单已批准。' : '变更单已驳回，等待整改。',
          agent: 'master',
        ));
      } else {
        _addMessage(ChatMessage.agentText(
          text: '操作失败，请稍后重试。',
          agent: 'master',
        ));
      }
    });
  }

  void _handleCardAction(String action, Map<String, dynamic> payload) {
    final api = ApiClient();
    final pid = payload['project_id']?.toString() ?? _currentProjectId;

    switch (action) {
      case 'confirm_settlement':
        if (pid == null) return;
        _addMessage(ChatMessage.userText(text: '确认结算中…'));
        api.confirmSettlement(pid).then((result) {
          if (result.isSuccess) {
            _addMessage(ChatMessage.agentText(
              text: '结算单已确认，应付金额已锁定。',
              agent: 'settlement',
            ));
          } else {
            _addMessage(ChatMessage.agentText(
              text: '结算确认失败：${result.error}',
              agent: 'settlement',
            ));
          }
        });
      case 'approve_review':
        if (pid == null) return;
        _addMessage(ChatMessage.userText(text: '通过复核中…'));
        api.approveSettlementReview(pid).then((result) {
          if (result.isSuccess) {
            _addMessage(ChatMessage.agentText(
              text: '人工复核已通过，可继续确认结算。',
              agent: 'settlement',
            ));
          } else {
            _addMessage(ChatMessage.agentText(
              text: '复核操作失败：${result.error}',
              agent: 'settlement',
            ));
          }
        });
      case 'select_candidate':
        final candidateId = payload['candidate_id']?.toString();
        final taskId = payload['task_id']?.toString();
        _addMessage(ChatMessage.userText(text: '已选择候选人 $candidateId 处理任务 $taskId'));
        _addMessage(ChatMessage.agentText(
          text: '任务已分配给候选人，等待对方确认。',
          agent: 'master',
        ));
      // v1.1.22: 硬件传感器触发回调
      case 'open_camera':
        _addMessage(ChatMessage.system(text: '📷 正在打开相机…'));
        _triggerCamera(payload);
      case 'start_ar_scan':
        _addMessage(ChatMessage.system(text: '🔬 正在启动 AR 扫描…'));
        _triggerARScan(payload);
      case 'start_voice_input':
        _addMessage(ChatMessage.system(text: '🎤 正在启动语音输入…'));
        _triggerVoiceInput();
      case 'play_audio':
        final url = payload['url']?.toString();
        if (url != null) _playAudio(url);
      case 'download':
        final url = payload['url']?.toString();
        if (url != null) _downloadFile(url);
      case 'open_url':
        final url = payload['url']?.toString();
        if (url != null) _openUrl(url);
      case 'publish_product':
        _addMessage(ChatMessage.userText(text: '确认上架产品…'));
      default:
        _addMessage(ChatMessage.system(text: '操作: $action'));
    }
  }

  void _handleCopy(String text) {
    Clipboard.setData(ClipboardData(text: text));
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('已复制', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
          backgroundColor: SuokeDesignTokens.cardBg,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
            side: const BorderSide(color: SuokeDesignTokens.border),
          ),
          duration: const Duration(seconds: 1),
        ),
      );
    }
  }

  void _handleReply(ChatMessage msg) {
    final text = msg.content ?? '';
    _msgCtrl.text = '> 引用: $text\n';
    _msgCtrl.selection = TextSelection.collapsed(offset: _msgCtrl.text.length);
    FocusScope.of(context).requestFocus();
  }

  // ═══════════════════════════════════════════
  // UI
  // ═══════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    final pc = context.watch<ProjectContext>();
    final projects = pc.projects;
    final currentName = projects
        .where((p) => (p['id'] ?? '').toString() == _currentProjectId)
        .map((p) => (p['name'] ?? '选择项目').toString())
        .toList();
    final title = currentName.isNotEmpty ? currentName.first : '索克家居';

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: SuokeDesignTokens.bgDeep,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // ── 聊天头部（对齐 Web chat-header：半透明 + 底部边框） ──
            _buildChatHeader(pc, projects, title, isDark),
            // ── Agent 选择栏 ──
            _buildAgentChips(),
            // ── 快览导航（对齐 Web .quick-nav） ──
            _buildQuickNav(),
            // ── 消息流 ──
            Expanded(
              child: _buildMessageList(),
            ),
            // ── 思考中指示器 ──
            if (_isLoading)
              _buildThinkingIndicator(),
            // ── 输入栏 ──
            _buildInputBar(),
          ],
        ),
      ),
    );
  }

  /// 聊天头部（半透明玻璃效果，对齐 Web chat-header）
  Widget _buildChatHeader(ProjectContext pc, List<Map<String, dynamic>> projects, String title, bool isDark) {
    return Container(
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBgSemi,
        border: const Border(bottom: BorderSide(color: SuokeDesignTokens.border)),
      ),
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top > 0 ? 0 : 8,
      ),
      child: Row(
        children: [
          // 项目选择器（点击可切换）
          if (projects.length > 1)
            Expanded(
              child: _buildProjectDropdown(pc, title),
            )
          else
            Expanded(
              child: Padding(
                padding: const EdgeInsets.only(left: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(title,
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: SuokeDesignTokens.fontSizeLg,
                          color: SuokeDesignTokens.textPrimary,
                        )),
                    Text('8 AI 群策群力',
                        style: TextStyle(
                          fontSize: SuokeDesignTokens.fontSizeXs,
                          color: SuokeDesignTokens.textSecondary,
                        )),
                  ],
                ),
              ),
            ),
          // 会话历史
          GestureDetector(
            onTap: _showSessionList,
            child: Container(
              width: 36,
              height: 36,
              margin: const EdgeInsets.only(right: 4),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.bgDeep,
                borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
                border: Border.all(color: SuokeDesignTokens.border),
              ),
              child: Icon(
                Icons.history,
                size: 18,
                color: SuokeDesignTokens.textSecondary,
              ),
            ),
          ),
          // 主题切换
          GestureDetector(
            onTap: () => context.read<ThemeState>().toggle(),
            child: Container(
              width: 36,
              height: 36,
              margin: const EdgeInsets.only(right: 8),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.bgDeep,
                borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusSm),
                border: Border.all(color: SuokeDesignTokens.border),
              ),
              child: Icon(
                isDark ? Icons.light_mode : Icons.dark_mode,
                size: 18,
                color: SuokeDesignTokens.accent,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProjectDropdown(ProjectContext pc, String currentTitle) {
    return PopupMenuButton<String>(
      offset: const Offset(0, 44),
      color: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
        side: const BorderSide(color: SuokeDesignTokens.border),
      ),
      child: Padding(
        padding: const EdgeInsets.only(left: 16),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Flexible(
                      child: Text(currentTitle,
                          style: TextStyle(fontWeight: FontWeight.w700, fontSize: SuokeDesignTokens.fontSizeLg, color: SuokeDesignTokens.textPrimary),
                          overflow: TextOverflow.ellipsis),
                    ),
                    Icon(Icons.arrow_drop_down, color: SuokeDesignTokens.textSecondary, size: 20),
                  ],
                ),
                Text('8 AI 群策群力',
                    style: TextStyle(fontSize: SuokeDesignTokens.fontSizeXs, color: SuokeDesignTokens.textSecondary)),
              ],
            ),
          ],
        ),
      ),
      onSelected: (pid) {
        _persistSessionId(null);
        pc.switchProject(pid);
        setState(() {
          _currentProjectId = pid;
          _messages.clear();
          _messages.add(ChatMessage.agentText(
            text: '已切换到新项目。我是索克家居 AI 总控 Agent，请告诉我您的需求。',
            agent: 'master',
          ));
        });
        _connectWebSocket();
      },
      itemBuilder: (_) => pc.projects.map((p) {
        final pid = (p['id'] ?? '').toString();
        final name = (p['name'] ?? '未命名').toString();
        final status = p['status']?.toString() ?? '';
        final isSelected = pid == _currentProjectId;
        return PopupMenuItem<String>(
          value: pid,
          child: Row(
            children: [
              if (isSelected)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(Icons.check, color: SuokeDesignTokens.accent, size: 16),
                ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name,
                        style: TextStyle(
                            color: isSelected ? SuokeDesignTokens.accent : SuokeDesignTokens.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 13)),
                    if (status.isNotEmpty)
                      Text(status,
                          style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 10)),
                  ],
                ),
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  /// 快览导航栏（对齐 Web 端 .quick-nav）
  Widget _buildQuickNav() {
    if (_currentProjectId == null || _currentProjectId!.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBgSemi,
        border: const Border(
          bottom: BorderSide(color: SuokeDesignTokens.border, width: 1),
        ),
      ),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        itemCount: _quickNavItems.length,
        separatorBuilder: (_, __) => const SizedBox(width: 4),
        itemBuilder: (context, index) {
          final item = _quickNavItems[index];
          return GestureDetector(
            onTap: () => _handleQuickNav(item.$2),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: SuokeDesignTokens.border.withValues(alpha: 0.6)),
              ),
              child: Text(
                item.$1,
                style: TextStyle(
                  fontSize: 12,
                  color: SuokeDesignTokens.textSecondary,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  void _handleQuickNav(String target) {
    final pid = _currentProjectId;
    if (pid == null) return;

    Widget? page;
    switch (target) {
      case 'project-detail':
        // 需要在 Navigator 中打开
        break;
      case 'materials':
        // 同样需要 Navigator
        break;
      case 'settings':
        // 打开设置
        break;
    }
    // 快览导航的业务跳转逻辑可根据需要扩展
  }

  Widget _buildMessageList() {
    if (_messages.isEmpty) {
      return _buildWelcomeScreen();
    }

    final items = <Widget>[];
    String? lastDate;

    for (int i = 0; i < _messages.length; i++) {
      final msg = _messages[i];
      final dateStr = _fmtDate(msg.timestamp);

      if (dateStr != lastDate) {
        lastDate = dateStr;
        items.add(
          _buildDateSeparator(dateStr),
        );
      }

      items.add(
        ChatMessageCard(
          key: ValueKey(msg.id ?? 'msg_$i'),
          message: msg,
          onApprovalAction: _handleApproval,
          onCardAction: _handleCardAction,
          onCopy: _handleCopy,
          onReply: _handleReply,
        ),
      );
    }

    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      backgroundColor: SuokeDesignTokens.cardBg,
      onRefresh: _refreshMessages,
      child: ListView.builder(
        controller: _scrollCtrl,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: items.length,
        itemBuilder: (ctx, i) => items[i],
      ),
    );
  }

  /// 日期分隔线（对齐 Web .date-separator）
  Widget _buildDateSeparator(String label) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          const Expanded(child: Divider(color: SuokeDesignTokens.border)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: SuokeDesignTokens.cardBgSemi,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(label,
                  style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: SuokeDesignTokens.fontSizeXs)),
            ),
          ),
          const Expanded(child: Divider(color: SuokeDesignTokens.border)),
        ],
      ),
    );
  }

  Future<void> _refreshMessages() async {
    final pc = context.read<ProjectContext>();
    final pid = _currentProjectId ?? pc.currentProjectId;
    if (pid == null) return;

    // 若有活跃会话，从服务端加载历史消息
    if (_currentSessionId != null) {
      await _loadSessionMessages();
      return;
    }

    // 无活跃会话：显示默认欢迎消息
    setState(() {
      _messages.clear();
      _messages.add(ChatMessage.agentText(
        text: '已刷新。我是索克家居 AI 总控 Agent，请告诉我您的需求。',
        agent: 'master',
      ));
    });
    _connectWebSocket();
  }

  String _fmtDate(DateTime? dt) {
    if (dt == null) return '';
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final msgDate = DateTime(dt.year, dt.month, dt.day);
    if (msgDate == today) return '今天';
    if (msgDate == today.subtract(const Duration(days: 1))) return '昨天';
    return '${dt.month}月${dt.day}日';
  }

  // ── 思考中指示器 ──

  Widget _buildThinkingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      color: SuokeDesignTokens.cardBgSemi,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(SuokeDesignTokens.accent),
            ),
          ),
          const SizedBox(width: 8),
          Text('思考中…',
              style: TextStyle(fontSize: SuokeDesignTokens.fontSizeSm, color: SuokeDesignTokens.textSecondary)),
        ],
      ),
    );
  }

  // ── emoji 选择器 ──

  void _showEmojiPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => EmojiPicker(
        onEmojiSelected: (emoji) {
          final text = _msgCtrl.text;
          final sel = _msgCtrl.selection;
          final start = sel.baseOffset.clamp(0, text.length);
          final end = sel.extentOffset.clamp(0, text.length);
          _msgCtrl.text = text.substring(0, start) + emoji + text.substring(end);
          final newPos = start + emoji.length;
          _msgCtrl.selection = TextSelection.collapsed(offset: newPos);
        },
      ),
    );
  }

  /// 输入栏（对齐 Web chat-input-bar）
  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBgSemi,
        border: const Border(top: BorderSide(color: SuokeDesignTokens.border)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            // 附件按钮
            GestureDetector(
              onTap: _showAttachmentSheet,
              child: Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: SuokeDesignTokens.inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: SuokeDesignTokens.border),
                ),
                child: Icon(Icons.add, color: SuokeDesignTokens.textSecondary, size: 22),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: SuokeDesignTokens.inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: SuokeDesignTokens.border),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: TextField(
                  controller: _msgCtrl,
                  enabled: !_isLoading,
                  style: TextStyle(fontSize: SuokeDesignTokens.fontSizeMd, color: SuokeDesignTokens.textPrimary),
                  decoration: InputDecoration(
                    hintText: '说点什么…',
                    hintStyle: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: SuokeDesignTokens.fontSizeMd),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  onSubmitted: (_) => _send(),
                  textInputAction: TextInputAction.send,
                ),
              ),
            ),
            const SizedBox(width: 8),
            // emoji 按钮
            GestureDetector(
              onTap: _showEmojiPicker,
              child: Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: SuokeDesignTokens.inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: SuokeDesignTokens.border),
                ),
                child: Icon(Icons.emoji_emotions_outlined, color: SuokeDesignTokens.textSecondary, size: 22),
              ),
            ),
            const SizedBox(width: 8),
            // 语音按钮
            GestureDetector(
              onTap: _toggleVoiceMode,
              child: Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: _isVoiceMode ? SuokeDesignTokens.accent : SuokeDesignTokens.inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: _isVoiceMode ? SuokeDesignTokens.accent : SuokeDesignTokens.border),
                ),
                child: Icon(
                  Icons.mic,
                  color: _isVoiceMode ? Colors.black : SuokeDesignTokens.textSecondary,
                  size: 22,
                ),
              ),
            ),
            const SizedBox(width: 8),
            // 发送按钮
            Container(
              decoration: const BoxDecoration(
                color: SuokeDesignTokens.accent,
                shape: BoxShape.circle,
              ),
              child: IconButton(
                icon: const Icon(Icons.send_rounded, color: Colors.black, size: 20),
                onPressed: _isLoading ? null : _send,
                splashRadius: 22,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showAttachmentSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(SuokeDesignTokens.radiusLg)),
        side: const BorderSide(color: SuokeDesignTokens.border),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: Icon(Icons.camera_alt_outlined, color: SuokeDesignTokens.textPrimary),
                title: Text('拍照', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
                subtitle: Text('拍摄现场照片', style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 12)),
                onTap: () { Navigator.pop(ctx); _pickImage(ImageSource.camera); },
              ),
              ListTile(
                leading: Icon(Icons.photo_library_outlined, color: SuokeDesignTokens.textPrimary),
                title: Text('相册', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
                subtitle: Text('从相册选择图片', style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 12)),
                onTap: () { Navigator.pop(ctx); _pickImage(ImageSource.gallery); },
              ),
              ListTile(
                leading: Icon(Icons.attach_file_outlined, color: SuokeDesignTokens.textPrimary),
                title: Text('文件', style: TextStyle(color: SuokeDesignTokens.textPrimary)),
                subtitle: Text('选择文档或图纸', style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 12)),
                onTap: () { Navigator.pop(ctx); _pickFile(); },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(source: source, imageQuality: 85);
      if (picked == null || !mounted) return;

      _addMessage(ChatMessage(
        type: ChatMessageType.photo,
        isSelf: true,
        timestamp: DateTime.now(),
        payload: {
          'photos': [{'url': picked.path, 'caption': '现场照片'}],
          'note': '上传中…',
        },
      ));

      final pid = _currentProjectId;
      await ApiClient().uploadFile('/files/upload', filePath: picked.path, projectId: pid);
    } catch (_) {}
  }

  Future<void> _pickFile() async {
    try {
      final result = await FilePicker.pickFiles();
      if (result == null || result.files.isEmpty || !mounted) return;
      final file = result.files.first;
      if (file.path == null) return;

      final sizeStr = file.size > 1024 * 1024
          ? '${(file.size / (1024 * 1024)).toStringAsFixed(1)} MB'
          : '${(file.size / 1024).toStringAsFixed(0)} KB';

      _addMessage(ChatMessage(
        type: ChatMessageType.document,
        isSelf: true,
        timestamp: DateTime.now(),
        payload: {'name': file.name, 'size': sizeStr, 'url': '#'},
      ));

      final pid = _currentProjectId;
      await ApiClient().uploadFile('/files/upload', filePath: file.path!, projectId: pid);
    } catch (_) {}
  }

  // ── v1.1.22: 硬件传感器触发方法 ──

  /// 触发相机拍照
  Future<void> _triggerCamera(Map<String, dynamic> payload) async {
    try {
      final picker = ImagePicker();
      final photo = await picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );
      if (photo != null) {
        _addMessage(ChatMessage(
          type: ChatMessageType.photo,
          isSelf: true,
          timestamp: DateTime.now(),
          payload: {
            'photos': [{'url': photo.path, 'caption': '现场拍摄'}],
            'note': '📷 现场照片',
          },
        ));
        // 上传到后端
        final pid = _currentProjectId;
        if (pid != null) {
          await ApiClient().uploadFile(
            '/files/upload',
            filePath: photo.path,
            projectId: pid,
          );
        }
      }
    } on PlatformException catch (e) {
      _addMessage(ChatMessage.system(text: '相机不可用: ${e.message}'));
    } catch (_) {
      _addMessage(ChatMessage.system(text: '打开相机失败，请检查权限'));
    }
  }

  /// 触发 AR 空间扫描
  Future<void> _triggerARScan(Map<String, dynamic> payload) async {
    _addMessage(ChatMessage.agentText(
      text: '正在跳转到 AR 扫描页面…\n\n'
          '支持功能：\n'
          '• RoomPlan 全屋扫描（LiDAR 设备）\n'
          '• 视觉 SLAM 空间建模\n'
          '• 激光测距辅助校准\n'
          '• 墙面特征自动识别',
      agent: 'ar_measurement',
    ));
    // 跳转到 AR 扫描页面
    if (mounted) {
      Navigator.of(context).pushNamed('/ar-scan', arguments: {
        'project_id': _currentProjectId,
        ...payload,
      });
    }
  }

  /// 触发语音输入
  Future<void> _triggerVoiceInput() async {
    setState(() => _isVoiceMode = true);
    try {
      await _voice.connect();
      _addMessage(ChatMessage.system(text: '🎤 语音输入已启动，请说话…'));
      // VoiceRealtimeService 会通过回调处理 ASR 结果
    } catch (e) {
      setState(() => _isVoiceMode = false);
      _addMessage(ChatMessage.system(text: '语音输入启动失败: $e'));
    }
  }

  /// 播放音频
  Future<void> _playAudio(String url) async {
    _addMessage(ChatMessage.system(text: '🔊 正在播放音频…'));
    // 实际播放逻辑由上层实现
  }

  /// 下载文件
  Future<void> _downloadFile(String url) async {
    _addMessage(ChatMessage.system(text: '📥 正在下载文件…'));
  }

  /// 打开外部 URL
  Future<void> _openUrl(String url) async {
    _addMessage(ChatMessage.system(text: '🔗 正在打开链接…'));
  }

  Widget _buildAgentChips() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: SuokeDesignTokens.cardBgSemi,
        border: const Border(bottom: BorderSide(color: SuokeDesignTokens.border)),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: _agents.map((agent) {
            final isSelected = _selectedAgent == agent.key;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: GestureDetector(
                onTap: () => setState(() => _selectedAgent = agent.key),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                  decoration: BoxDecoration(
                    color: isSelected ? agent.color.withValues(alpha: 0.15) : SuokeDesignTokens.bgDeep,
                    borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                    border: Border.all(
                      color: isSelected ? agent.color : SuokeDesignTokens.border,
                      width: isSelected ? 1.5 : 1,
                    ),
                  ),
                  child: Text(
                    '${agent.emoji} ${agent.name}',
                    style: TextStyle(
                      fontSize: SuokeDesignTokens.fontSizeSm,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      color: isSelected ? agent.color : SuokeDesignTokens.textSecondary,
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  // ── 欢迎页面 ──

  Widget _buildWelcomeScreen() {
    final suggestions = [
      (emoji: '💰', text: '查看预算情况'),
      (emoji: '📐', text: '我的设计方案'),
      (emoji: '🔨', text: '施工进度如何'),
      (emoji: '🛒', text: '需要采购什么'),
    ];

    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      backgroundColor: SuokeDesignTokens.cardBg,
      onRefresh: _refreshMessages,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const SizedBox(height: 72),
                const Text('🏠', style: TextStyle(fontSize: 48)),
                const SizedBox(height: 16),
                Text('索克家居',
                    style: TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 24, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text('AI 智能装修助手',
                    style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 16)),
                const SizedBox(height: 6),
                Text('9 个 AI Agent 7×24',
                    style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
                Text('在线服务',
                    style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
                const SizedBox(height: 32),
                for (final s in suggestions) ...[
                  _buildSuggestionChip(s.emoji, s.text),
                  const SizedBox(height: 10),
                ],
                const SizedBox(height: 32),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Row(
                    children: [
                      const Expanded(child: Divider(color: SuokeDesignTokens.border)),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text('或直接输入',
                            style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: SuokeDesignTokens.fontSizeSm)),
                      ),
                      const Expanded(child: Divider(color: SuokeDesignTokens.border)),
                    ],
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSuggestionChip(String emoji, String text) {
    return GestureDetector(
      onTap: () {
        _msgCtrl.text = text;
        _msgCtrl.selection = TextSelection.fromPosition(
          TextPosition(offset: text.length),
        );
      },
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
        decoration: BoxDecoration(
          color: SuokeDesignTokens.cardBgSemi,
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
          border: Border.all(color: SuokeDesignTokens.border),
        ),
        child: Text(
          '$emoji  $text',
          style: TextStyle(color: SuokeDesignTokens.textPrimary, fontSize: 15),
        ),
      ),
    );
  }
}

/// 会话列表弹窗组件
class _SessionListSheet extends StatefulWidget {
  final void Function(String sessionId) onSelect;
  final VoidCallback onNewChat;
  final String? currentSessionId;

  const _SessionListSheet({
    required this.onSelect,
    required this.onNewChat,
    this.currentSessionId,
  });

  @override
  State<_SessionListSheet> createState() => _SessionListSheetState();
}

class _SessionListSheetState extends State<_SessionListSheet> {
  List<dynamic> _sessions = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadSessions();
  }

  Future<void> _loadSessions() async {
    try {
      final result = await ApiClient().listAgentSessions();
      if (result.isSuccess && result.data != null) {
        setState(() {
          _sessions = (result.data as List<dynamic>?) ?? [];
          _loading = false;
        });
      } else {
        setState(() => _loading = false);
      }
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.6),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 标题栏
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 12, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('会话历史',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                GestureDetector(
                  onTap: widget.onNewChat,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: SuokeDesignTokens.accent.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text('+ 新对话',
                        style: TextStyle(fontSize: 13, color: SuokeDesignTokens.accent)),
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          // 列表
          Flexible(
            child: _loading
                ? const Padding(
                    padding: EdgeInsets.all(40),
                    child: Center(child: CircularProgressIndicator()),
                  )
                : _sessions.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.all(40),
                        child: Text('暂无历史会话', style: TextStyle(color: SuokeDesignTokens.textSecondary)),
                      )
                    : ListView.builder(
                        shrinkWrap: true,
                        itemCount: _sessions.length,
                        itemBuilder: (ctx, idx) {
                          final s = _sessions[idx] as Map<String, dynamic>;
                          final isActive = s['id']?.toString() == widget.currentSessionId;
                          return _buildSessionItem(s, isActive);
                        },
                      ),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildSessionItem(Map<String, dynamic> session, bool isActive) {
    final title = (session['title'] ?? '新的对话').toString();
    final agentType = (session['primary_agent_type'] ?? '').toString();
    final msgCount = session['message_count'] ?? 0;
    final updatedAt = session['updated_at']?.toString() ?? '';

    // agent_type → 显示名
    const agentNames = {
      'designer': '设计师', 'budget': '预算师', 'procurement': '采购师',
      'construction': '施工员', 'qa_inspector': '监理师', 'settlement': '结算师',
      'concierge': '客服', 'content_publisher': '内容', 'orchestrator': '总控',
    };
    final agentLabel = agentNames[agentType] ?? agentType;

    return GestureDetector(
      onTap: () => widget.onSelect(session['id']?.toString() ?? ''),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: isActive ? SuokeDesignTokens.accent.withOpacity(0.05) : null,
          border: Border(bottom: BorderSide(color: SuokeDesignTokens.border.withOpacity(0.5))),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: isActive ? SuokeDesignTokens.accent : SuokeDesignTokens.textPrimary)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      if (agentLabel.isNotEmpty) ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: SuokeDesignTokens.bgDeep,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(agentLabel,
                              style: const TextStyle(fontSize: 10, color: SuokeDesignTokens.textSecondary)),
                        ),
                        const SizedBox(width: 6),
                      ],
                      Text('$msgCount 条消息',
                          style: const TextStyle(fontSize: 11, color: SuokeDesignTokens.textMuted)),
                    ],
                  ),
                ],
              ),
            ),
            if (isActive)
              Icon(Icons.check_circle, size: 18, color: SuokeDesignTokens.accent),
          ],
        ),
      ),
    );
  }
}
