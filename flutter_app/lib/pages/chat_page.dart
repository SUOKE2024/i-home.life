import 'package:flutter/material.dart';
import '../services/api.dart';
import '../models/chat_message.dart';
import '../widgets/loading_skeleton.dart';
import '../widgets/error_retry.dart';
import '../widgets/chat_message_card.dart';

/// IM 协作聊天页面 (F40) — 消息/聊天室/@提及/已读
class ChatPage extends StatefulWidget {
  final String projectId;
  const ChatPage({super.key, required this.projectId});

  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiClient _api = ApiClient();
  final TextEditingController _msgCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();

  List<dynamic> _rooms = [];
  List<ChatMessage> _messages = [];
  Map<String, dynamic>? _currentRoom;
  bool _loading = false;
  String? _error;
  int _unreadCount = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadRooms();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _msgCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadRooms() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final result = await _api.getList('/chat/rooms/${widget.projectId}');
    if (result.isSuccess) {
      _rooms = result.data;
      if (_rooms.isNotEmpty && _currentRoom == null) {
        _currentRoom = _rooms.first;
        await _loadMessages(_currentRoom!['id']);
      }
    } else {
      _error = '加载聊天室失败';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadMessages(String roomId) async {
    final result = await _api.getList('/chat/messages/$roomId');
    if (result.isSuccess) {
      final msgs = (result.data as List)
          .map((m) => ChatMessage.fromJson(m))
          .toList();
      setState(() => _messages = msgs);
      _scrollToBottom();
    }
  }

  Future<void> _sendMessage() async {
    final text = _msgCtrl.text.trim();
    if (text.isEmpty || _currentRoom == null) return;

    _msgCtrl.clear();
    final result = await _api.post('/chat/messages', {
      'room_id': _currentRoom!['id'],
      'content': text,
      'type': 'text',
    });
    if (result.isSuccess) {
      await _loadMessages(_currentRoom!['id']);
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('发送失败：${result.error}')),
        );
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _selectRoom(Map<String, dynamic> room) {
    setState(() => _currentRoom = room);
    _loadMessages(room['id']);
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Text('协作聊天'),
            const SizedBox(width: 8),
            if (_currentRoom != null) ...[
              const Icon(Icons.chevron_right, size: 18),
              Text(_currentRoom!['name'] ?? '', style: const TextStyle(fontSize: 16)),
            ],
          ],
        ),
        bottom: TabBar(
          controller: _tabController,
          onTap: (i) {
            if (i == 0) _loadRooms();
          },
          tabs: [
            Tab(text: '聊天${_unreadCount > 0 ? ' ($_unreadCount)' : ''}'),
            const Tab(text: '聊天室'),
          ],
        ),
      ),
      body: _loading
          ? const LoadingSkeleton(itemCount: 3, itemHeight: 80)
          : _error != null
              ? ErrorRetryWidget(message: _error!, onRetry: _loadRooms)
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildChatView(colors),
                    _buildRoomList(colors),
                  ],
                ),
    );
  }

  Widget _buildChatView(ColorScheme colors) {
    if (_currentRoom == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.chat_bubble_outline, size: 48, color: colors.onSurfaceVariant),
            const SizedBox(height: 12),
            Text('请选择聊天室', style: TextStyle(color: colors.onSurfaceVariant)),
          ],
        ),
      );
    }

    return Column(
      children: [
        Expanded(
          child: _messages.isEmpty
              ? Center(child: Text('暂无消息', style: TextStyle(color: colors.onSurfaceVariant)))
              : ListView.builder(
                  controller: _scrollCtrl,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  itemCount: _messages.length,
                  itemBuilder: (_, i) => ChatMessageCard(message: _messages[i]),
                ),
        ),
        _buildInputBar(colors),
      ],
    );
  }

  Widget _buildRoomList(ColorScheme colors) {
    if (_rooms.isEmpty) {
      return Center(child: Text('暂无聊天室', style: TextStyle(color: colors.onSurfaceVariant)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _rooms.length,
      itemBuilder: (_, i) {
        final room = _rooms[i];
        final isActive = _currentRoom != null && _currentRoom!['id'] == room['id'];
        return Container(
          margin: const EdgeInsets.only(bottom: 6),
          decoration: BoxDecoration(
            color: isActive ? colors.primary.withValues(alpha: 0.08) : null,
            borderRadius: BorderRadius.circular(8),
          ),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: colors.primary.withValues(alpha: 0.15),
              child: Text(room['type'] == 'group' ? '群' : '1', style: TextStyle(color: colors.primary, fontSize: 14)),
            ),
            title: Text(room['name'] ?? '聊天室', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(room['last_message'] ?? '暂无消息',
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: TextStyle(color: colors.onSurfaceVariant, fontSize: 12)),
            trailing: room['unread'] != null && (room['unread'] as int) > 0
                ? CircleAvatar(
                    radius: 10,
                    backgroundColor: Colors.red,
                    child: Text('${room['unread']}', style: const TextStyle(fontSize: 10, color: Colors.white)),
                  )
                : null,
            onTap: () => _selectRoom(room),
          ),
        );
      },
    );
  }

  Widget _buildInputBar(ColorScheme colors) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: BoxDecoration(
        color: colors.surface,
        border: Border(top: BorderSide(color: colors.outlineVariant, width: 0.5)),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _msgCtrl,
                minLines: 1,
                maxLines: 4,
                decoration: InputDecoration(
                  hintText: '输入消息...',
                  hintStyle: TextStyle(color: colors.onSurfaceVariant, fontSize: 14),
                  filled: true,
                  fillColor: colors.surfaceVariant,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  isDense: true,
                ),
                style: const TextStyle(fontSize: 14),
                onSubmitted: (_) => _sendMessage(),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              onPressed: _sendMessage,
              icon: Icon(Icons.send_rounded, color: colors.primary),
            ),
          ],
        ),
      ),
    );
  }
}
