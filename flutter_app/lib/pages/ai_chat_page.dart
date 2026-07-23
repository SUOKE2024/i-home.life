import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/chat_message.dart';
import '../theme/suoke_theme.dart';
import '../services/agent_router.dart';
import '../services/api.dart';
import '../services/project_context.dart';
import '../services/sse_service.dart';
import '../services/sensor_service.dart';
import '../services/voice_realtime_service.dart';
import '../services/websocket_service.dart';
import '../widgets/chat_message_card.dart';
import '../widgets/emoji_picker.dart';
import 'ar_scan_page.dart';
import 'settings_page.dart';

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

  // 思考步骤追踪
  final List<String> _activeThinkingSteps = [];
  String _currentProcessingAgent = 'master';

  // ── 头像状态 ──
  static const _customAvatarKey = 'custom_avatar_path';
  static const _avatarCount = 109;
  String? _avatarAssetPath;
  String? _customAvatarPath;

  StreamSubscription<SseEvent>? _sseSub;
  VoidCallback? _wsUnsubscribe;

  static const _sessionKey = 'agent_session_id';

  @override
  void initState() {
    super.initState();
    _initAvatar();
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
    // 不在此处清除 session，允许用户导航后回来继续对话
    // 只有显式「新对话」或「切换项目」才清除
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

  /// v1.1.26: 将最后一条 Agent 文本消息替换为卡片类型消息
  ///
  /// 当后端 SSE meta 事件携带 message_type（如 ar_scan_trigger）时，
  /// 流式文本推送完成后，将文本消息替换为对应的可交互卡片。
  void _replaceLastAgentWithCard(
    String messageType,
    String content,
    String agent,
    Map<String, dynamic>? payload,
  ) {
    final cardType = ChatMessage.fromString(messageType);
    if (cardType == ChatMessageType.text) return; // 无法识别的类型不替换
    setState(() {
      for (int i = _messages.length - 1; i >= 0; i--) {
        final m = _messages[i];
        if (!m.isSelf && m.type == ChatMessageType.text) {
          _messages[i] = m.copyWith(
            type: cardType,
            content: content,
            agent: agent,
            payload: payload,
          );
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
    // v1.1.26: 记录 meta 事件中的卡片类型，done 时替换为卡片消息
    String? cardMessageType;
    Map<String, dynamic>? cardPayload;
    // v1.1.29: 追踪思考步骤
    _activeThinkingSteps.clear();
    _currentProcessingAgent = targetAgent;

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
                final newAgent = _backendToAgent(event.agentType!);
                if (newAgent != currentAgent) {
                  // v1.1.29: Agent 交接可视化
                  _activeThinkingSteps.add('交接至 ${AgentInfo.getByKey(newAgent).name}');
                }
                currentAgent = newAgent;
                _currentProcessingAgent = newAgent;
              }
              // v1.1.26: 记录卡片类型，done 时渲染为卡片
              if (event.messageType != null && event.messageType != 'text') {
                cardMessageType = event.messageType;
                cardPayload = event.cardPayload;
              }
            case SseEventType.token:
              fullContent += event.content ?? '';
              _updateLastAgentMessage(fullContent, agent: currentAgent);
            case SseEventType.thinking_step:
              // v1.1.29: 记录 Agent 思考步骤
              if (event.content != null && event.content!.isNotEmpty) {
                _activeThinkingSteps.add(event.content!);
                if (event.agentType != null) {
                  _currentProcessingAgent = _backendToAgent(event.agentType!);
                }
                setState(() {}); // 刷新 thinking indicator
              }
            case SseEventType.done:
              if (event.content != null && event.content!.isNotEmpty) {
                _updateLastAgentMessage(event.content!, agent: currentAgent);
              }
              // v1.1.26: 如果 meta 标记了卡片类型，替换最后一条消息为卡片
              if (cardMessageType != null && fullContent.isNotEmpty) {
                _replaceLastAgentWithCard(cardMessageType!, fullContent, currentAgent, cardPayload);
              }
              // v1.1.29: 将思考步骤挂载到最后一条消息
              if (_activeThinkingSteps.isNotEmpty && _messages.isNotEmpty) {
                final lastIdx = _messages.length - 1;
                _messages[lastIdx] = _messages[lastIdx].copyWith(
                  thinkingSteps: List<String>.from(_activeThinkingSteps),
                  confidence: route.confidence > 0.49 ? route.confidence : null,
                );
              }
              setState(() => _isLoading = false);
            case SseEventType.error:
              _updateLastAgentMessage(
                '抱歉，AI 服务暂时不可用: ${event.content ?? '未知错误'}',
                agent: currentAgent,
              );
              // v1.1.29: 增强错误恢复指引
              _handleAgentError(event.content ?? '未知错误', currentAgent);
              setState(() => _isLoading = false);
          }
        },
        onError: (e) {
          _updateLastAgentMessage('抱歉，AI 服务暂时不可用: ${e.toString().length > 80 ? e.toString().substring(0, 80) + '...' : e}', agent: 'master');
          _handleAgentError(e.toString(), 'master');
          setState(() => _isLoading = false);
        },
        onDone: () {
          setState(() => _isLoading = false);
        },
      );
    } catch (e) {
      _updateLastAgentMessage('抱歉，AI 服务暂时不可用: $e', agent: 'master');
      _handleAgentError(e.toString(), 'master');
      setState(() => _isLoading = false);
    }
  }

  /// 项目户型选项
  static const _houseTypes = ['公寓', '别墅', '平层', '复式/LOFT', '商铺', '办公楼', '自定义'];

  /// 创建项目弹窗 — 含户型选择、位置定位、通讯方式
  Future<void> _showCreateProjectDialog(ProjectContext pc) async {
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final contactNameCtrl = TextEditingController();
    final contactPhoneCtrl = TextEditingController();
    final addressCtrl = TextEditingController();
    String selectedHouseType = _houseTypes.first;
    final customHouseTypeCtrl = TextEditingController();
    bool showCustomHouseType = false;
    double? latitude, longitude;
    bool locating = false;

    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setDialogState) => AlertDialog(
            title: const Text('创建项目'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 项目名称
                  TextField(
                    controller: nameCtrl,
                    decoration: const InputDecoration(
                      labelText: '项目名称 *',
                      hintText: '例如：我的新家装修',
                    ),
                    autofocus: true,
                  ),
                  const SizedBox(height: 12),
                  // 项目描述
                  TextField(
                    controller: descCtrl,
                    decoration: const InputDecoration(
                      labelText: '项目描述（可选）',
                      hintText: '描述您的项目',
                    ),
                    maxLines: 2,
                  ),
                  const SizedBox(height: 16),
                  // ── 户型选择 ──
                  const Text('户型选择', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    value: selectedHouseType,
                    decoration: const InputDecoration(
                      labelText: '户型',
                      contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    ),
                    items: _houseTypes.map((t) => DropdownMenuItem(value: t, child: Text(t))).toList(),
                    onChanged: (v) {
                      if (v != null) {
                        setDialogState(() {
                          selectedHouseType = v;
                          showCustomHouseType = v == '自定义';
                        });
                      }
                    },
                  ),
                  if (showCustomHouseType) ...[
                    const SizedBox(height: 8),
                    TextField(
                      controller: customHouseTypeCtrl,
                      decoration: const InputDecoration(
                        labelText: '自定义户型',
                        hintText: '请输入户型描述',
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  // ── 位置 / 定位 ──
                  const Text('项目位置', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: addressCtrl,
                          decoration: const InputDecoration(
                            labelText: '地址',
                            hintText: '输入地址或使用定位',
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      SizedBox(
                        height: 48,
                        child: ElevatedButton(
                          onPressed: locating
                              ? null
                              : () async {
                                  setDialogState(() => locating = true);
                                  final sensor = SensorService();
                                  final loc = await sensor.getCurrentLocation();
                                  if (loc != null) {
                                    latitude = loc['latitude'] as double;
                                    longitude = loc['longitude'] as double;
                                    if (addressCtrl.text.isEmpty) {
                                      addressCtrl.text = '$latitude, $longitude';
                                    }
                                  }
                                  setDialogState(() => locating = false);
                                },
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                          ),
                          child: locating
                              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                              : const Icon(Icons.my_location, size: 20),
                        ),
                      ),
                    ],
                  ),
                  if (latitude != null && longitude != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      '已定位: $latitude, $longitude',
                      style: const TextStyle(fontSize: 11, color: SuokeDesignTokens.textSecondary),
                    ),
                  ],
                  const SizedBox(height: 16),
                  // ── 通讯方式 ──
                  const Text('通讯方式', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                  const SizedBox(height: 8),
                  TextField(
                    controller: contactNameCtrl,
                    decoration: const InputDecoration(
                      labelText: '联系人姓名（可选）',
                      hintText: '请输入联系人姓名',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: contactPhoneCtrl,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: '联系电话（可选）',
                      hintText: '请输入联系电话',
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: () {
                  final houseTypeValue = showCustomHouseType
                      ? customHouseTypeCtrl.text.trim()
                      : selectedHouseType;
                  Navigator.pop(ctx, <String, dynamic>{
                    'name': nameCtrl.text.trim(),
                    'description': descCtrl.text.trim(),
                    'house_type': houseTypeValue,
                    'address': addressCtrl.text.trim(),
                    'latitude': latitude,
                    'longitude': longitude,
                    'contact_name': contactNameCtrl.text.trim(),
                    'contact_phone': contactPhoneCtrl.text.trim(),
                  });
                },
                child: const Text('创建'),
              ),
            ],
          ),
        );
      },
    );
    if (result == null || (result['name'] ?? '').toString().trim().isEmpty) return;

    final api = ApiClient();
    final r = await api.post('/projects', result);
    if (r.isSuccess && mounted) {
      await pc.loadProjects();
      // 自动选中新创建的项目
      final projects = pc.projects;
      if (projects.isNotEmpty) {
        final newProject = projects.last;
        final newId = newProject['id'] as String?;
        if (newId != null) {
          await pc.switchProject(newId);
          setState(() {
            _currentProjectId = newId;
            _messages.clear();
            _messages.add(ChatMessage.agentText(
              text: '欢迎使用索克家居！我是 AI 总控 Agent，请告诉我您的需求。',
              agent: 'master',
            ));
          });
          _connectWebSocket();
        }
      }
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(r.error ?? '创建项目失败')),
      );
    }
  }

  String _agentToBackend(String agentKey) {
    // 与后端 app/services/agent_registry.py 同步
    const map = {
      'master': 'orchestrator', 'design': 'design', 'budget': 'budget',
      'procurement': 'procurement', 'construction': 'construction',
      'quality': 'qa_inspector', 'settlement': 'settlement', 'support': 'concierge',
      'admin': 'admin',
      'kitchen': 'kitchen', 'bathroom': 'bathroom',
      'mep': 'mep', 'appliance': 'appliance',
      'furniture_catalog': 'furniture_catalog',
      'door_window_waterproof': 'door_window_waterproof',
      'lighting': 'lighting', 'structural': 'structural',
      'smart_home': 'smart_home', 'custom_furniture': 'custom_furniture',
      'soft_furnishing': 'soft_furnishing', 'hard_decoration': 'hard_decoration',
      'ar_measurement': 'ar_measurement', 'vr_panorama': 'vr_panorama',
      'ai_render': 'ai_render', 'takeoff': 'takeoff',
      'floorplans': 'floorplans', 'files': 'files',
      'products': 'products', 'identity': 'identity',
      'voice': 'voice', 'notifications': 'notifications',
      'ifc_export': 'ifc_export', 'scene_automation': 'scene_automation',
      'tasks': 'tasks', 'change_orders': 'change_orders',
      'crews': 'crews', 'points': 'points',
      'cad_import': 'cad_import', 'sketch_to_3d': 'sketch_to_3d',
    };
    return map[agentKey] ?? agentKey;
  }

  String _backendToAgent(String backendType) {
    const map = {
      'orchestrator': 'master', 'design': 'design', 'budget': 'budget',
      'procurement': 'procurement', 'construction': 'construction',
      'qa_inspector': 'quality', 'settlement': 'settlement', 'concierge': 'support',
      'admin': 'admin',
      'kitchen': 'kitchen', 'bathroom': 'bathroom',
      'mep': 'mep', 'appliance': 'appliance',
      'furniture_catalog': 'furniture_catalog',
      'door_window_waterproof': 'door_window_waterproof',
      'lighting': 'lighting', 'structural': 'structural',
      'smart_home': 'smart_home', 'custom_furniture': 'custom_furniture',
      'soft_furnishing': 'soft_furnishing', 'hard_decoration': 'hard_decoration',
      'ar_measurement': 'ar_measurement', 'vr_panorama': 'vr_panorama',
      'ai_render': 'ai_render', 'takeoff': 'takeoff',
      'floorplans': 'floorplans', 'files': 'files',
      'products': 'products', 'identity': 'identity',
      'voice': 'voice', 'notifications': 'notifications',
      'ifc_export': 'ifc_export', 'scene_automation': 'scene_automation',
      'tasks': 'tasks', 'change_orders': 'change_orders',
      'crews': 'crews', 'points': 'points',
      'cad_import': 'cad_import', 'sketch_to_3d': 'sketch_to_3d',
    };
    return map[backendType] ?? backendType;
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
      backgroundColor: isDark ? SuokeDesignTokens.bgDeep : SuokeDesignTokens.lightBg,
      body: SafeArea(
        bottom: false,
        child: Stack(
          children: [
            Column(
              children: [
                // ── 聊天头部（半透明 + 底部边框） ──
                _buildChatHeader(pc, projects, title),
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
          ],
        ),
      ),
    );
  }

  /// 聊天头部（半透明玻璃效果）
  Widget _buildChatHeader(ProjectContext pc, List<Map<String, dynamic>> projects, String title) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: isDark ? SuokeDesignTokens.cardBgSemi : Colors.white.withValues(alpha: 0.95),
        border: Border(bottom: BorderSide(color: isDark ? SuokeDesignTokens.border : SuokeDesignTokens.lightBorder)),
      ),
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top > 0 ? 0 : 8,
      ),
      child: Row(
        children: [
          // 项目选择器（点击可切换）
          if (projects.isNotEmpty)
            Expanded(
              child: _buildProjectDropdown(pc, title),
            )
          else
            Expanded(
              child: Padding(
                padding: const EdgeInsets.only(left: 16),
                child: GestureDetector(
                  onTap: () => _showCreateProjectDialog(pc),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text('索克家居',
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: SuokeDesignTokens.fontSizeLg,
                                color: SuokeDesignTokens.textPrimary,
                              )),
                          const SizedBox(width: 6),
                          Icon(Icons.add_circle_outline,
                              size: 18,
                              color: SuokeDesignTokens.accent),
                        ],
                      ),
                      Text('点击创建项目 开始使用',
                          style: TextStyle(
                            fontSize: SuokeDesignTokens.fontSizeXs,
                            color: SuokeDesignTokens.accent,
                          )),
                    ],
                  ),
                ),
              ),
            ),
          const SizedBox(width: 8),
          // 用户头像
          _buildAvatar(),
        ],
      ),
    );
  }

  /// 用户头像：点击打开设置，长按从相册更换
  Widget _buildAvatar() {
    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const SettingsPage()),
        );
      },
      onLongPress: _pickCustomAvatar,
      child: Container(
        width: 36,
        height: 36,
        margin: const EdgeInsets.only(right: 12),
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: SuokeDesignTokens.border, width: 1.5),
        ),
        child: ClipOval(
          child: _customAvatarPath != null
              ? Image.file(
                  File(_customAvatarPath!),
                  width: 36,
                  height: 36,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => _buildAvatarFallback(),
                )
              : _avatarAssetPath != null
                  ? Image.asset(
                      _avatarAssetPath!,
                      width: 36,
                      height: 36,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _buildAvatarFallback(),
                    )
                  : _buildAvatarFallback(),
        ),
      ),
    );
  }

  /// 头像加载失败 / 等待中 fallback
  Widget _buildAvatarFallback() {
    return Container(
      color: SuokeDesignTokens.accent.withValues(alpha: 0.2),
      child: Icon(Icons.person, size: 20, color: SuokeDesignTokens.accent),
    );
  }

  /// 从相册自定义头像
  Future<void> _pickCustomAvatar() async {
    final picker = ImagePicker();
    final picked = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 80,
      maxWidth: 256,
      maxHeight: 256,
    );
    if (picked == null) return;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_customAvatarKey, picked.path);
    setState(() {
      _customAvatarPath = picked.path;
      _avatarAssetPath = null;
    });
  }

  /// 初始化头像：已有自定义则加载，否则随机选一个
  Future<void> _initAvatar() async {
    final prefs = await SharedPreferences.getInstance();
    final customPath = prefs.getString(_customAvatarKey);
    if (customPath != null) {
      setState(() => _customAvatarPath = customPath);
      return;
    }
    // 每次登录随机加载
    final index = Random().nextInt(_avatarCount) + 1;
    setState(() {
      _avatarAssetPath = 'assets/images/avatars/hand-drawn-profiles/$index.webp';
    });
  }

  Widget _buildProjectDropdown(ProjectContext pc, String currentTitle) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return PopupMenuButton<String>(
      offset: const Offset(0, 44),
      color: isDark ? SuokeDesignTokens.cardBg : SuokeDesignTokens.lightCard,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
        side: BorderSide(color: isDark ? SuokeDesignTokens.border : SuokeDesignTokens.lightBorder),
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
                Text('${AgentInfo.standardAgents.length} AI Agent 群策群力',
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

  Widget _buildMessageList() {
    if (_messages.isEmpty) {
      return _buildWelcomeScreen();
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;
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
      backgroundColor: isDark ? SuokeDesignTokens.cardBg : SuokeDesignTokens.lightCard,
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final borderColor = isDark ? SuokeDesignTokens.border : SuokeDesignTokens.lightBorder;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Expanded(child: Divider(color: borderColor)),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(
                color: isDark ? SuokeDesignTokens.cardBgSemi : Colors.white.withValues(alpha: 0.95),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(label,
                  style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: SuokeDesignTokens.fontSizeXs)),
            ),
          ),
          Expanded(child: Divider(color: borderColor)),
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

  // ── 思考中指示器（v1.1.29: 展示 Agent 实时处理步骤） ──

  Widget _buildThinkingIndicator() {
    final processingAgentInfo = AgentInfo.getByKey(_currentProcessingAgent);
    final lastStep = _activeThinkingSteps.isNotEmpty ? _activeThinkingSteps.last : null;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
      color: isDark ? SuokeDesignTokens.cardBgSemi : Colors.white.withValues(alpha: 0.95),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // 当前 Agent 标识 + 动画点
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: processingAgentInfo.color,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '${processingAgentInfo.emoji} ${processingAgentInfo.name} Agent',
                style: TextStyle(
                  fontSize: SuokeDesignTokens.fontSizeSm,
                  color: processingAgentInfo.color,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 8),
              _buildAnimatedDots(),
            ],
          ),
          // 最新思考步骤
          if (lastStep != null) ...[
            const SizedBox(height: 6),
            Row(
              children: [
                const SizedBox(width: 16),
                Icon(Icons.subdirectory_arrow_right, size: 14, color: SuokeDesignTokens.textMuted),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    lastStep,
                    style: TextStyle(
                      fontSize: SuokeDesignTokens.fontSizeXs,
                      color: SuokeDesignTokens.textSecondary,
                      height: 1.3,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
          // 步骤历史（折叠显示最近 3 条）
          if (_activeThinkingSteps.length > 1) ...[
            const SizedBox(height: 4),
            GestureDetector(
              onTap: () => _showThinkingStepsSheet(),
              child: Row(
                children: [
                  const SizedBox(width: 16),
                  Text(
                    '${_activeThinkingSteps.length} 个步骤',
                    style: TextStyle(fontSize: 10, color: SuokeDesignTokens.accent),
                  ),
                  Icon(Icons.keyboard_arrow_down, size: 14, color: SuokeDesignTokens.accent),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 动画中的三个点
  Widget _buildAnimatedDots() {
    return SizedBox(
      width: 24,
      height: 12,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: List.generate(3, (i) {
          return TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.3, end: 1.0),
            duration: const Duration(milliseconds: 600),
            builder: (context, value, child) {
              return Opacity(
                opacity: value,
                child: Container(
                  width: 4,
                  height: 4,
                  decoration: BoxDecoration(
                    color: SuokeDesignTokens.textMuted,
                    shape: BoxShape.circle,
                  ),
                ),
              );
            },
          );
        }),
      ),
    );
  }

  void _showThinkingStepsSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: SuokeDesignTokens.cardBg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(SuokeDesignTokens.radiusLg)),
        side: const BorderSide(color: SuokeDesignTokens.border),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.psychology_outlined, color: SuokeDesignTokens.accent, size: 20),
                  const SizedBox(width: 8),
                  Text('Agent 思考过程',
                    style: TextStyle(
                      fontSize: SuokeDesignTokens.fontSizeMd,
                      fontWeight: FontWeight.w700,
                      color: SuokeDesignTokens.textPrimary,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              ...List.generate(_activeThinkingSteps.length, (i) {
                final step = _activeThinkingSteps[i];
                final isLast = i == _activeThinkingSteps.length - 1;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Column(
                        children: [
                          Container(
                            width: 24,
                            height: 24,
                            decoration: BoxDecoration(
                              color: isLast ? SuokeDesignTokens.accent : SuokeDesignTokens.success,
                              shape: BoxShape.circle,
                            ),
                            child: Icon(
                              isLast ? Icons.more_horiz : Icons.check,
                              size: 14,
                              color: Colors.black,
                            ),
                          ),
                          if (!isLast)
                            Container(
                              width: 2,
                              height: 28,
                              color: SuokeDesignTokens.border,
                            ),
                        ],
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          step,
                          style: TextStyle(
                            fontSize: SuokeDesignTokens.fontSizeSm,
                            color: isLast ? SuokeDesignTokens.textPrimary : SuokeDesignTokens.textSecondary,
                            fontWeight: isLast ? FontWeight.w600 : FontWeight.normal,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }

  /// v1.1.29: 增强错误恢复 — 提供重试/切换 Agent 等恢复建议
  void _handleAgentError(String errorMsg, String failedAgent) {
    final agentName = AgentInfo.getByKey(failedAgent).name;
    final isRateLimit = errorMsg.contains('rate') || errorMsg.contains('limit') || errorMsg.contains('429');
    final isTimeout = errorMsg.contains('timeout') || errorMsg.contains('timed out');

    String suggestion;
    if (isRateLimit) {
      suggestion = '请求频率过高，$agentName Agent 暂时限流，请稍后再试。';
    } else if (isTimeout) {
      suggestion = '$agentName Agent 响应超时，可能是网络问题或服务繁忙。';
    } else {
      suggestion = '$agentName Agent 遇到暂时性问题。';
    }

    _addMessage(ChatMessage.agentText(
      text: '$suggestion\n\n'
          '💡 您可以：\n'
          '• 稍等片刻后重新发送\n'
          '• 尝试切换到「总控」Agent 重新提问\n'
          '• 检查网络连接后重试',
      agent: 'master',
    ));
  }

  /// 旧版思考中指示器（保留作为 fallback）
  Widget _buildThinkingIndicatorLegacy() {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      color: isDark ? SuokeDesignTokens.cardBgSemi : Colors.white.withValues(alpha: 0.95),
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
    final cs = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final inputBg = isDark ? SuokeDesignTokens.inputBg : cs.surfaceContainerHighest;
    final borderColor = isDark ? SuokeDesignTokens.border : SuokeDesignTokens.lightBorder;
    final containerBg = isDark ? SuokeDesignTokens.cardBgSemi : Colors.white.withValues(alpha: 0.95);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: containerBg,
        border: Border(top: BorderSide(color: borderColor)),
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
                  color: inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: borderColor),
                ),
                child: Icon(Icons.add, color: SuokeDesignTokens.textSecondary, size: 22),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: borderColor),
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
                  color: inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: borderColor),
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
                  color: _isVoiceMode ? SuokeDesignTokens.accent : inputBg,
                  borderRadius: BorderRadius.circular(SuokeDesignTokens.radiusPill),
                  border: Border.all(color: _isVoiceMode ? SuokeDesignTokens.accent : borderColor),
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    showModalBottomSheet(
      context: context,
      backgroundColor: isDark ? SuokeDesignTokens.cardBg : SuokeDesignTokens.lightCard,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(SuokeDesignTokens.radiusLg)),
        side: BorderSide(color: isDark ? SuokeDesignTokens.border : SuokeDesignTokens.lightBorder),
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
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ARScanPage(projectId: _currentProjectId ?? ''),
        ),
      );
    }
  }

  /// 触发语音输入
  Future<void> _triggerVoiceInput() async {
    final token = ApiClient().token;
    if (token == null) {
      _addMessage(ChatMessage.system(text: '请先登录后再使用语音输入'));
      return;
    }
    setState(() => _isVoiceMode = true);
    try {
      await _voice.connect(token: token);
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

  // ── 欢迎页面 ──

  Widget _buildWelcomeScreen() {
    final agentCount = AgentInfo.standardAgents.length;
    final coreCount = 8; // master, design, budget, procurement, construction, quality, settlement, support
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final suggestions = [
      (emoji: '💰', text: '查看预算情况', agent: 'budget'),
      (emoji: '📐', text: '我的设计方案', agent: 'design'),
      (emoji: '🔨', text: '施工进度如何', agent: 'construction'),
      (emoji: '🛒', text: '需要采购什么', agent: 'procurement'),
      (emoji: '🍳', text: '厨房布局建议', agent: 'kitchen'),
      (emoji: '🛁', text: '卫浴设计咨询', agent: 'bathroom'),
    ];

    return RefreshIndicator(
      color: SuokeDesignTokens.accent,
      backgroundColor: isDark ? SuokeDesignTokens.cardBg : SuokeDesignTokens.lightCard,
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
                Text('$coreCount 位核心 Agent + ${agentCount - coreCount} 位专项 Agent',
                    style: TextStyle(color: SuokeDesignTokens.textSecondary, fontSize: 13)),
                Text('7×24 全天候在线',
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
                        child: Text('或直接输入提问',
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
    final isDark = Theme.of(context).brightness == Brightness.dark;
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
          color: isDark ? SuokeDesignTokens.cardBgSemi : Colors.white.withValues(alpha: 0.95),
          borderRadius: BorderRadius.circular(SuokeDesignTokens.radius),
          border: Border.all(color: isDark ? SuokeDesignTokens.border : SuokeDesignTokens.lightBorder),
        ),
        child: Text(
          '$emoji  $text',
          style: TextStyle(color: isDark ? SuokeDesignTokens.textPrimary : SuokeDesignTokens.lightTextPrimary, fontSize: 15),
        ),
      ),
    );
  }
}


