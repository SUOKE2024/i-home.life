import 'package:flutter/material.dart';
import '../services/api.dart';

class AIChatPage extends StatefulWidget {
  const AIChatPage({super.key});

  @override
  State<AIChatPage> createState() => _AIChatPageState();
}

class _AIChatPageState extends State<AIChatPage> {
  final _msgCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  final List<Map<String, String>> _messages = [];
  String _agent = 'orchestrator';

  final _agents = {
    'orchestrator': ('◈', '总控'),
    'designer': ('✦', '设计'),
    'budget': ('◎', '预算'),
    'procurement': ('▦', '采购'),
    'construction': ('▥', '施工'),
  };

  @override
  void initState() {
    super.initState();
    _messages.add({'role': 'agent', 'text': '您好！我是索克家居 AI 总控 Agent。我可以帮您进行设计规划、预算管理、物料采购、施工管理。请告诉我您的需求。'});
  }

  void _addMsg(String role, String text) {
    setState(() => _messages.add({'role': role, 'text': text}));
    Future.delayed(const Duration(milliseconds: 100), () {
      _scrollCtrl.animateTo(_scrollCtrl.position.maxScrollExtent, duration: const Duration(milliseconds: 300), curve: Curves.easeOut);
    });
  }

  Future<void> _send() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty) return;
    _msgCtrl.clear();
    _addMsg('user', text);

    try {
      final api = ApiClient();
      final Map<String, String> endpointMap = {
        'designer': '/agents/design',
        'budget': '/agents/budget',
        'procurement': '/agents/procurement',
        'construction': '/agents/construction',
      };
      final endpoint = endpointMap[_agent] ?? '/agents/chat';
      final res = await api.post(endpoint, {'message': text, 'agent_type': _agent});
      final reply = (res['reply'] ?? res['full_reply'] ?? res['summary'] ?? res.toString()) as String;
      _addMsg('agent', reply);
    } catch (e) {
      _addMsg('agent', '抱歉，AI 服务暂时不可用: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 助手', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: _agents.entries.map((e) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 4),
                child: ChoiceChip(
                  label: Text('${e.value.$1} ${e.value.$2}'),
                  selected: _agent == e.key,
                  onSelected: (_) => setState(() => _agent = e.key),
                  selectedColor: const Color(0xFFC9973B).withValues(alpha: 0.2),
                  labelStyle: TextStyle(
                    color: _agent == e.key ? const Color(0xFFC9973B) : const Color(0xFF8A8894),
                    fontSize: 12,
                  ),
                  side: BorderSide(
                    color: _agent == e.key ? const Color(0xFFC9973B) : const Color(0xFF2A2A45),
                  ),
                ),
              )).toList(),
            ),
          ),
          Expanded(
            child: ListView.builder(
              controller: _scrollCtrl,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              itemCount: _messages.length,
              itemBuilder: (ctx, i) {
                final m = _messages[i];
                final isUser = m['role'] == 'user';
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                    decoration: BoxDecoration(
                      color: isUser ? const Color(0xFFC9973B).withValues(alpha: 0.12) : const Color(0xFF1A1A2A),
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(16),
                        topRight: const Radius.circular(16),
                        bottomLeft: isUser ? const Radius.circular(16) : const Radius.circular(4),
                        bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(16),
                      ),
                      border: Border.all(color: isUser ? const Color(0xFFC9973B).withValues(alpha: 0.2) : const Color(0xFF1E1E32)),
                    ),
                    child: Text(m['text']!, style: const TextStyle(fontSize: 14, color: Color(0xFFE8E6E1), height: 1.5)),
                  ),
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: const BoxDecoration(
              color: Color(0xFF12121D),
              border: Border(top: BorderSide(color: Color(0xFF1E1E32))),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _msgCtrl,
                    decoration: const InputDecoration(
                      hintText: '输入你的装修需求...',
                      border: InputBorder.none,
                    ),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send, color: Color(0xFFC9973B)),
                  onPressed: _send,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
