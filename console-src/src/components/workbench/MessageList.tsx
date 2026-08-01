/**
 * MessageList — 对齐 ai_chat_page.dart:1077-1136 ListView.builder
 *
 * 每条消息按 cardType 分发到 MessageBubble 或 MessageCard；
 * 连续同 sender 消息合并（isConsecutive 隐藏 meta）；
 * 自动滚动到底部。
 */

import { useEffect, useRef } from 'react';
import type { ChatMessage } from '../../types/chat';
import MessageBubble from './MessageBubble';
import MessageCard from './MessageCard';
import A2UICard from './A2UICard';

export interface MessageListProps {
  messages: ChatMessage[];
  onFeedback?: (msgId: string, feedback: 'like' | 'dislike') => void;
  onCardAction?: (action: string, payload?: unknown) => void;
}

export default function MessageList({ messages, onFeedback, onCardAction }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 滚动到底部（对齐 ai_chat_page.dart:263-273 _scrollToBottom）
    const t = setTimeout(() => {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }, 120);
    return () => clearTimeout(t);
  }, [messages.length]);

  // 计算连续消息标记
  const decorated = messages.map((m, i) => {
    const prev = i > 0 ? messages[i - 1] : null;
    const isConsecutive = !!prev && prev.role === m.role && (prev.agent ?? '') === (m.agent ?? '');
    return { ...m, isConsecutive };
  });

  return (
    <div className="wb-message-list" ref={containerRef} data-testid="wb-message-list">
      {decorated.map((m) => (
        <div key={m.id} className="wb-msg-block">
          {m.cardType && m.cardType !== 'text' ? (
            <MessageCard message={m} onAction={onCardAction} />
          ) : (
            <MessageBubble message={m} onFeedback={onFeedback} />
          )}
          {/* A2UI 结构化卡片（v1.3.1 接入，对齐 Flutter a2ui_renderer.dart） */}
          {m.a2uiCards && m.a2uiCards.length > 0 && (
            <div className="wb-msg__a2ui">
              {m.a2uiCards.map((card, i) => (
                <A2UICard key={i} card={card as Record<string, any>} />
              ))}
            </div>
          )}
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
