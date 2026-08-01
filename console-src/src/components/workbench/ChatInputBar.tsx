/**
 * ChatInputBar — 对齐 ai_chat_page.dart:1464-1570 _buildInputBar
 *
 * 布局：附件(38px 圆形) + input(pill 圆角 Expanded) + emoji(38px) + 语音(38px，激活 accent) + 语音任务(38px) + 发送(accent 圆形)
 * 容器 cardBgSemi + 顶部 border；输入框 placeholder "说点什么…"
 *
 * v1.3.1 补齐：
 * - emoji 选择器（EmojiPicker，光标处插入 + 最近常用 localStorage 持久化）
 * - 附件：隐藏 file input → onAttachFile(file)（项目感知上传由页面层处理）
 */

import { useRef, useState, type KeyboardEvent } from 'react';
import EmojiPicker from './EmojiPicker';

export interface ChatInputBarProps {
  onSend: (text: string) => void;
  /** v1.3.1: 附件文件选择回调（替代原 no-op onAttach） */
  onAttachFile?: (file: File) => void;
  onVoice?: () => void;
  onVoiceTasks?: () => void;
  disabled?: boolean;
  isVoiceMode?: boolean;
  placeholder?: string;
}

export default function ChatInputBar({
  onSend,
  onAttachFile,
  onVoice,
  onVoiceTasks,
  disabled,
  isVoiceMode,
  placeholder = '说点什么…',
}: ChatInputBarProps) {
  const [text, setText] = useState('');
  const [emojiOpen, setEmojiOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const send = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
    setEmojiOpen(false);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  /** 在光标处插入 emoji（无选区/无光标时追加到末尾），对齐 Flutter _showEmojiPicker */
  const insertEmoji = (emoji: string) => {
    const el = inputRef.current;
    const start = el?.selectionStart ?? text.length;
    const end = el?.selectionEnd ?? text.length;
    const next = text.slice(0, start) + emoji + text.slice(end);
    setText(next);
    // 光标移到插入点之后
    requestAnimationFrame(() => {
      if (el) {
        el.focus();
        const pos = start + emoji.length;
        try {
          el.setSelectionRange(pos, pos);
        } catch {
          // 非文本输入场景忽略
        }
      }
    });
  };

  return (
    <div className="wb-input-bar" data-testid="wb-input-bar">
      <input
        ref={fileRef}
        type="file"
        hidden
        data-testid="wb-input-file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file && onAttachFile) onAttachFile(file);
          e.target.value = '';
        }}
      />
      <button
        className="wb-input-btn"
        onClick={() => fileRef.current?.click()}
        aria-label="添加附件"
        title="添加附件"
        type="button"
        data-testid="wb-input-attach"
      >
        ＋
      </button>
      <input
        ref={inputRef}
        className="wb-input-field"
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        aria-label="输入消息"
        autoComplete="off"
        enterKeyHint="send"
        data-testid="wb-input-field"
      />
      <button
        className={`wb-input-btn ${emojiOpen ? 'wb-input-btn--voice-active' : ''}`}
        onClick={() => setEmojiOpen((v) => !v)}
        aria-label="表情"
        aria-pressed={emojiOpen}
        type="button"
        data-testid="wb-input-emoji"
      >
        😊
      </button>
      <button
        className={`wb-input-btn ${isVoiceMode ? 'wb-input-btn--voice-active' : ''}`}
        onClick={onVoice}
        aria-label="语音输入"
        aria-pressed={isVoiceMode}
        type="button"
        data-testid="wb-input-voice"
      >
        🎤
      </button>
      {onVoiceTasks && (
        <button
          className="wb-input-btn"
          onClick={onVoiceTasks}
          aria-label="语音任务"
          title="语音任务（后台智能体）"
          type="button"
          data-testid="wb-input-voice-tasks"
        >
          🎯
        </button>
      )}
      <button
        className="wb-input-send"
        onClick={send}
        disabled={disabled || !text.trim()}
        aria-label="发送"
        type="button"
        data-testid="wb-input-send"
      >
        ➤
      </button>
      {emojiOpen && (
        <EmojiPicker onSelect={insertEmoji} onClose={() => setEmojiOpen(false)} />
      )}
    </div>
  );
}
