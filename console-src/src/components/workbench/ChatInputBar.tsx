/**
 * ChatInputBar — 对齐 ai_chat_page.dart:1464-1570 _buildInputBar
 *
 * 5 元素布局：附件(38px 圆形) + input(pill 圆角 Expanded) + emoji(38px) + 语音(38px，激活 accent) + 发送(accent 圆形)
 * 容器 cardBgSemi + 顶部 border；输入框 placeholder "说点什么…"
 */

import { useState, type KeyboardEvent } from 'react';

export interface ChatInputBarProps {
  onSend: (text: string) => void;
  onAttach?: () => void;
  onEmoji?: () => void;
  onVoice?: () => void;
  onVoiceTasks?: () => void;
  disabled?: boolean;
  isVoiceMode?: boolean;
  placeholder?: string;
}

export default function ChatInputBar({
  onSend,
  onAttach,
  onEmoji,
  onVoice,
  onVoiceTasks,
  disabled,
  isVoiceMode,
  placeholder = '说点什么…',
}: ChatInputBarProps) {
  const [text, setText] = useState('');

  const send = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="wb-input-bar" data-testid="wb-input-bar">
      <button
        className="wb-input-btn"
        onClick={onAttach}
        aria-label="添加附件"
        type="button"
        data-testid="wb-input-attach"
      >
        ＋
      </button>
      <input
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
        className="wb-input-btn"
        onClick={onEmoji}
        aria-label="表情"
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
    </div>
  );
}
