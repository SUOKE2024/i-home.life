/**
 * AgentSelector — 9 核心 agent chips 横向滚动
 *
 * 对齐 suoke_theme.dart agentColor 8 色 + admin（accent）。
 * 批次 2 实现为 header 下紧凑 chips（横向滚动），批次 3 响应式化。
 */

import { CORE_AGENTS, getAgentInfo } from '../../services/agent-router';

export interface AgentSelectorProps {
  selected: string;
  onSelect: (agent: string) => void;
}

export default function AgentSelector({ selected, onSelect }: AgentSelectorProps) {
  // admin 追加在末尾（9 个）
  const agents = [...CORE_AGENTS, 'admin'];
  return (
    <div className="wb-agent-selector" data-testid="wb-agent-selector" role="tablist">
      {agents.map((key) => {
        const info = getAgentInfo(key);
        const isActive = key === selected;
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`wb-agent-chip ${isActive ? 'wb-agent-chip--active' : ''}`}
            onClick={() => onSelect(key)}
            data-testid={`wb-agent-chip--${key}`}
          >
            <span className="wb-agent-chip__emoji">{info.emoji}</span>
            <span>{info.name}</span>
          </button>
        );
      })}
    </div>
  );
}
