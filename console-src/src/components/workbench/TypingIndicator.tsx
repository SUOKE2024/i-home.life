/**
 * TypingIndicator — 对齐 ai_chat_page.dart:1199-1278 _buildThinkingIndicator
 *
 * 布局：agent emoji + name + 动画点 + 思考步骤（若有）
 */

import { getAgentInfo } from '../../services/agent-router';

export interface TypingIndicatorProps {
  agent: string;
  steps?: string[];
}

export default function TypingIndicator({ agent, steps }: TypingIndicatorProps) {
  const info = getAgentInfo(agent);
  const latestStep = steps && steps.length > 0 ? steps[steps.length - 1] : null;

  return (
    <div className="wb-typing" data-testid="wb-typing" role="status" aria-live="polite">
      <span style={{ color: info.color }}>
        {info.emoji} {info.name}
      </span>
      <span className="wb-typing__dots" aria-hidden="true">
        <span className="wb-typing__dot" />
        <span className="wb-typing__dot" />
        <span className="wb-typing__dot" />
      </span>
      {latestStep && (
        <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-xs)' }}>
          {latestStep}
        </span>
      )}
    </div>
  );
}
