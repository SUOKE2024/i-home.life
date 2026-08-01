/**
 * EmojiPicker — 对齐 flutter_app/lib/widgets/emoji_picker.dart
 *
 * 5 分类：🕐 最近常用 / 😀 表情 / 👍 手势 / ❤️ 心形 / 🔨 装修
 * 最近使用的 emoji 通过 localStorage 持久化（最多 32 个）。
 */

import { useState } from 'react';

export interface EmojiPickerProps {
  onSelect: (emoji: string) => void;
  onClose: () => void;
}

const RECENT_KEY = 'wb_emoji_recent';

const CATEGORIES: Array<{ key: string; icon: string; label: string }> = [
  { key: 'recent', icon: '🕐', label: '最近常用' },
  { key: 'smileys', icon: '😀', label: '表情' },
  { key: 'gestures', icon: '👍', label: '手势' },
  { key: 'hearts', icon: '❤️', label: '心形' },
  { key: 'renovation', icon: '🔨', label: '装修' },
];

const EMOJI_DATA: Record<string, string[]> = {
  smileys: [
    '😀', '😃', '😄', '😁', '😆', '😅', '🤣', '😂', '🙂', '🙃',
    '😉', '😊', '😇', '🥰', '😍', '🤩', '😘', '😋', '😛', '😜',
    '🤪', '😝', '🤑', '🤗', '🤭', '🤫', '🤔', '🤐', '😐', '😑',
    '😶', '😏', '😒', '🙄', '😬', '😌', '😔', '😪', '😴', '😷',
    '🤒', '🤕', '🤢', '🤮', '🥵', '🥶', '🥴', '😵', '🤯', '🥳',
    '😎', '🤓', '😕', '😟', '🙁', '😮', '😯', '😲', '😳', '🥺',
    '😨', '😰', '😥', '😢', '😭', '😱', '😖', '😣', '😞', '😩',
    '😫', '😤', '😡', '😠', '🤬', '😈', '💀', '💩', '🤡', '👻',
  ],
  gestures: [
    '👍', '👎', '👌', '✌️', '🤞', '🤟', '🤘', '🤙',
    '👈', '👉', '👆', '👇', '☝️', '✋', '🤚', '🖐️',
    '🖖', '👋', '🤝', '👏', '🙌', '🙏', '🤲', '💪',
    '🤜', '🤛', '✊', '👊', '🫶', '🫰',
  ],
  hearts: [
    '❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💔',
    '❣️', '💕', '💞', '💓', '💗', '💖', '💘', '💝', '💯', '🔥',
    '⭐', '🌟', '✨', '⚡', '💢', '💥', '💫', '💦', '🎉', '🎊',
    '🎈', '🏆', '🎁',
  ],
  renovation: [
    '🏠', '🏡', '🛋️', '🛏️', '🚪', '🪟', '🚿', '🛁', '🚽', '🍳',
    '🔨', '🪚', '🪛', '🔩', '🔧', '⚒️', '🧱', '🪣', '🖌️', '🎨',
    '💡', '🔌', '🔋', '📐', '📏', '✏️', '📋', '🗂️', '📦', '🛒',
    '💰', '💳', '📅', '⏰', '✅', '⚠️', '❌', '📷', '🎥', '🤝',
  ],
};

function readRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((x) => typeof x === 'string').slice(0, 32) : [];
  } catch {
    return [];
  }
}

export default function EmojiPicker({ onSelect, onClose }: EmojiPickerProps) {
  const [category, setCategory] = useState('recent');
  const [recent, setRecent] = useState<string[]>(readRecent);

  const emojis = category === 'recent' ? recent : EMOJI_DATA[category] ?? [];

  function pick(emoji: string) {
    // 记录最近使用（去重置顶，最多 32）
    const next = [emoji, ...recent.filter((e) => e !== emoji)].slice(0, 32);
    setRecent(next);
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      // localStorage 不可用时静默跳过持久化
    }
    onSelect(emoji);
  }

  return (
    <div className="wb-emoji" role="dialog" aria-label="表情选择器" data-testid="wb-emoji-picker">
      <div className="wb-emoji__tabs" role="tablist">
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            type="button"
            role="tab"
            aria-selected={category === c.key}
            title={c.label}
            className={`wb-emoji__tab ${category === c.key ? 'wb-emoji__tab--active' : ''}`}
            onClick={() => setCategory(c.key)}
            data-testid={`wb-emoji-tab--${c.key}`}
          >
            {c.icon}
          </button>
        ))}
      </div>
      <div className="wb-emoji__grid">
        {emojis.length === 0 ? (
          <div className="wb-emoji__empty">暂无，先选一个表情吧</div>
        ) : (
          emojis.map((e) => (
            <button
              key={e}
              type="button"
              className="wb-emoji__cell"
              onClick={() => pick(e)}
              aria-label={`插入表情 ${e}`}
            >
              {e}
            </button>
          ))
        )}
      </div>
      <button type="button" className="wb-emoji__close" onClick={onClose} aria-label="关闭表情选择器">
        收起
      </button>
    </div>
  );
}
