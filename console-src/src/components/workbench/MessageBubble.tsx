/**
 * MessageBubble — 对齐 message-renderers.js:143-191 的 user/agent 文本气泡
 *
 * user 气泡：右对齐，bubbleUser 背景
 * agent 气泡：左对齐，bubbleAgent 背景 + agent 色 meta（emoji name Agent · time）
 * 连续消息（isConsecutive）隐藏 meta。
 */

import { getAgentInfo } from '../../services/agent-router';
import type { ChatMessage } from '../../types/chat';

export interface MessageBubbleProps {
  message: ChatMessage;
  onFeedback?: (msgId: string, feedback: 'like' | 'dislike') => void;
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const agentInfo = !isUser && message.agent ? getAgentInfo(message.agent) : null;
  const displayName =
    message.displayName ?? (isUser ? '我' : agentInfo ? `${agentInfo.emoji} ${agentInfo.name} Agent` : 'Agent');

  return (
    <div className={`wb-msg ${isUser ? 'wb-msg--user' : 'wb-msg--agent'}`}>
      {!message.isConsecutive && (
        <div className="wb-msg__meta">
          <strong
            className="wb-msg__meta-name"
            style={agentInfo ? { color: agentInfo.color } : undefined}
          >
            {displayName}
          </strong>
          {' · '}
          {formatTime(message.timestamp)}
        </div>
      )}
      <div className="wb-msg__bubble">{message.content}</div>
      {!isUser && message.agent && onFeedback && (
        <div className="wb-msg__feedback">
          {message.feedback ? (
            <span
              className="wb-feedback-btn wb-feedback-btn--sent"
              data-testid={`wb-feedback-sent--${message.feedback}`}
            >
              {message.feedback === 'like' ? '👍 已反馈' : '👎 已反馈'}
            </span>
          ) : (
            <>
              <button
                className="wb-feedback-btn"
                onClick={() => onFeedback(message.id, 'like')}
                aria-label="有帮助"
                type="button"
              >
                👍
              </button>
              <button
                className="wb-feedback-btn"
                onClick={() => onFeedback(message.id, 'dislike')}
                aria-label="没帮助"
                type="button"
              >
                👎
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
