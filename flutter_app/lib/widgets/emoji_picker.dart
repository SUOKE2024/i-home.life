import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../theme/suoke_theme.dart';

/// emoji 选择器 —— 与 Web 端 emoji 选择器对齐
///
/// 5 个分类：🕐 最近常用 / 😀 表情 / 👍 手势 / ❤️ 心形 / 🔨 装修
/// 最近使用的 emoji 通过 SharedPreferences 持久化（最多 32 个）。
class EmojiPicker extends StatefulWidget {
  final void Function(String emoji) onEmojiSelected;

  const EmojiPicker({super.key, required this.onEmojiSelected});

  @override
  State<EmojiPicker> createState() => _EmojiPickerState();
}

class _EmojiPickerState extends State<EmojiPicker> {
  String _category = 'recent';
  List<String> _recent = [];

  static const _bgDark = SuokeDesignTokens.bgDeep;
  static const _cardBg = SuokeDesignTokens.cardBg;
  static const _textSecondary = SuokeDesignTokens.textSecondary;
  static const _textMuted = SuokeDesignTokens.textMuted;
  static const _border = SuokeDesignTokens.border;
  static const _accent = SuokeDesignTokens.accent;

  static const Map<String, String> _categoryIcons = {
    'recent': '🕐',
    'smileys': '😀',
    'gestures': '👍',
    'hearts': '❤️',
    'renovation': '🔨',
  };

  static const Map<String, List<String>> _emojiData = {
    'smileys': [
      '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
      '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😋', '😛', '😜',
      '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔', '🤐', '😐', '😑',
      '😶', '😏', '😒', '🙄', '😬', '😌', '😔', '😪', '😴', '😷',
      '🤒', '🤕', '🤢', '🤮', '🥵', '🥶', '🥴', '😵', '🤯', '🥳',
      '😎', '🤓', '😕', '😟', '🙁', '😮', '😯', '😲', '😳', '🥺',
      '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣', '😞', '😩',
      '😫', '😤', '😡', '😠', '🤬', '😈', '💀', '💩', '🤡', '👻',
    ],
    'gestures': [
      '👍', '👎', '👌', '✌️', '🤞', '🤟', '🤘', '🤙',
      '👈', '👉', '👆', '👇', '☝️', '✋', '🤚', '🖐️',
      '🖖', '👋', '🤝', '👏', '🙌', '🙏', '🤲', '💪',
      '🤜', '🤛', '✊', '👊', '🫶', '🫰',
    ],
    'hearts': [
      '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔',
      '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💯', '🔥',
      '⭐', '🌟', '✨', '⚡', '💢', '💥', '💫', '💦', '🎉', '🎊',
      '🎈', '🏆', '🎁',
    ],
    'renovation': [
      '🏠', '🏗️', '🛏️', '🛋️', '🪑', '🚪', '🪟', '🛁',
      '🚿', '🚽', '🧱', '🔨', '🪛', '🔩', '🪚', '🧰',
      '🛠️', '⚒️', '📐', '📏', '✂️', '🧹', '🧽', '💡',
      '🔌', '🪔', '⚡', '🧴', '🪣', '🎨', '🖌️',
    ],
  };

  @override
  void initState() {
    super.initState();
    _loadRecent();
  }

  Future<void> _loadRecent() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final stored = prefs.getStringList('emoji_recent') ?? [];
      if (mounted) {
        setState(() {
          _recent = stored;
          // 首次加载时如果最近使用为空，自动切换到 smileys 分类
          if (_recent.isEmpty && _category == 'recent') {
            _category = 'smileys';
          }
        });
      }
    } catch (_) {}
  }

  Future<void> _addRecent(String emoji) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final recent = List<String>.from(_recent);
      recent.remove(emoji);
      recent.insert(0, emoji);
      final trimmed = recent.take(32).toList();
      await prefs.setStringList('emoji_recent', trimmed);
      if (mounted) setState(() => _recent = trimmed);
    } catch (_) {}
  }

  List<String> get _currentEmojis {
    if (_category == 'recent') return _recent;
    return _emojiData[_category] ?? [];
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 300,
      decoration: const BoxDecoration(
        color: _bgDark,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Column(
        children: [
          // 拖拽指示条
          Container(
            margin: const EdgeInsets.only(top: 8),
            width: 36,
            height: 4,
            decoration: BoxDecoration(
              color: _textMuted,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          // 分类标签
          Container(
            height: 48,
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: _categoryIcons.keys.map((cat) {
                final active = cat == _category;
                return GestureDetector(
                  onTap: () => setState(() => _category = cat),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    margin: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
                    decoration: BoxDecoration(
                      color: active ? _cardBg : Colors.transparent,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _categoryIcons[cat]!,
                      style: TextStyle(
                        fontSize: 20,
                        color: active ? _accent : _textSecondary,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
          const Divider(height: 1, color: _border),
          // emoji 网格
          Expanded(
            child: _currentEmojis.isEmpty
                ? const Center(
                    child: Text(
                      '还没有最近使用的表情，点击其他分类选择',
                      style: TextStyle(fontSize: 12, color: _textMuted),
                    ),
                  )
                : GridView.builder(
                    padding: const EdgeInsets.all(8),
                    gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 44,
                      childAspectRatio: 1,
                      crossAxisSpacing: 2,
                      mainAxisSpacing: 2,
                    ),
                    itemCount: _currentEmojis.length,
                    itemBuilder: (ctx, i) {
                      final emoji = _currentEmojis[i];
                      return GestureDetector(
                        onTap: () {
                          _addRecent(emoji);
                          widget.onEmojiSelected(emoji);
                        },
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Center(
                            child: Text(
                              emoji,
                              style: const TextStyle(fontSize: 22),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
