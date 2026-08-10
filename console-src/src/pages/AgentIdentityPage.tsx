/**
 * AgentIdentityPage — GB/Z 185 智能体身份卡（v1.9.0 预研，元数据预埋）
 *
 * 结构：Scaffold > AppBar(Agent 身份卡) > 支持身份码的 Agent 列表 > 选中 Agent 的
 *      28 位 AID 身份卡 + ACDL 能力描述（GB/Z 185.4 JSON）
 * API（对齐 app/api/agent_identity.py，flag: gbz185_agent_card_enabled，默认 False）：
 *   GET /api/agents/identity          支持身份码的 Agent 列表（{ agents, total }）
 *   GET /api/agents/identity/{name}   单个 Agent 身份卡（28 位 AID + ACDL）
 *
 * flag 未启用时端点返回 404「GBZ185 身份卡未启用」，页面诚实提示，不伪造数据。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { AgentIdentityCard, AgentIdentityListResponse } from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

export default function AgentIdentityPage() {
  const navigate = useNavigate();
  const [selectedName, setSelectedName] = useState<string | null>(null);

  // 支持身份码的 Agent 列表
  const {
    data: list,
    loading,
    error,
    reload,
  } = useAsync<AgentIdentityListResponse | null>(async () => {
    const r = await apiClient.listAgentIdentityCards<AgentIdentityListResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  // 选中 Agent 的身份卡（28 位 AID + ACDL）
  const {
    data: card,
    loading: cardLoading,
    error: cardError,
    reload: reloadCard,
  } = useAsync<AgentIdentityCard | null>(async () => {
    if (!selectedName) return null;
    const r = await apiClient.getAgentIdentityCard<AgentIdentityCard>(selectedName);
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [selectedName]);

  const agents = list?.agents ?? [];

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-agent-identity-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🪪 Agent 身份卡（GB/Z 185）</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {loading && (
            <div className="wb-state" data-testid="wb-agent-identity-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载身份卡列表…</div>
            </div>
          )}

          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-agent-identity-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={reload}
                type="button"
              >
                重试
              </button>
            </div>
          )}

          {!loading && !error && agents.length === 0 && (
            <div className="wb-state" data-testid="wb-agent-identity-empty">
              <div className="wb-state__icon">🪪</div>
              <div>暂无支持 GB/Z 185 身份码的 Agent</div>
            </div>
          )}

          {!loading && !error && agents.length > 0 && (
            <div data-testid="wb-agent-identity-content">
              <div className="wb-section-label">
                支持身份码的 Agent（{agents.length}）
              </div>
              {agents.map((agent, i) => (
                <button
                  key={agent.name}
                  type="button"
                  className="wb-smart-card"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    cursor: 'pointer',
                    border:
                      selectedName === agent.name
                        ? '1px solid var(--accent)'
                        : undefined,
                  }}
                  onClick={() => setSelectedName(agent.name)}
                  data-testid={`wb-agent-identity-item--${i}`}
                >
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{agent.name}</div>
                    <span className="wb-status-chip wb-status-chip--muted">
                      类型码 {agent.type_code}
                    </span>
                    <span className="wb-status-chip wb-status-chip--accent">
                      安全分级 L{agent.security_level}
                    </span>
                  </div>
                </button>
              ))}

              {/* 身份卡详情 */}
              {selectedName && (
                <div style={{ marginTop: 16 }}>
                  <div className="wb-section-label">
                    {selectedName} 身份卡（28 位 AID + ACDL）
                  </div>
                  {cardLoading && (
                    <div className="wb-state" data-testid="wb-agent-identity-card-loading">
                      <div className="wb-state__icon">⏳</div>
                      <div>生成身份卡…</div>
                    </div>
                  )}
                  {cardError && !cardLoading && (
                    <div className="wb-state wb-state--error" data-testid="wb-agent-identity-card-error">
                      <div className="wb-state__icon">⚠</div>
                      <div>{cardError}</div>
                      <button
                        className="wb-theme-option wb-theme-option--active"
                        onClick={reloadCard}
                        type="button"
                      >
                        重试
                      </button>
                    </div>
                  )}
                  {card && !cardLoading && (
                    <div className="wb-smart-card" data-testid="wb-agent-identity-card">
                      <div className="wb-smart-card__head">
                        <div className="wb-smart-card__room">{card.agent_name}</div>
                        <span className="wb-status-chip wb-status-chip--success">
                          ACDL {card.acdl.acdl_version}
                        </span>
                      </div>
                      <div className="wb-smart-card__meta">
                        <span>🆔 AID（28 位）</span>
                      </div>
                      <div
                        style={{
                          fontFamily: 'var(--font-mono, monospace)',
                          fontSize: 'var(--font-size-sm)',
                          wordBreak: 'break-all',
                          background: 'var(--bg-muted, rgba(107,105,120,0.1))',
                          borderRadius: 8,
                          padding: '8px 10px',
                          marginTop: 6,
                        }}
                        data-testid="wb-agent-identity-aid"
                      >
                        {card.aid}
                      </div>
                      <div className="wb-smart-card__meta" style={{ marginTop: 10 }}>
                        <span>💡 能力（{card.acdl.agent.capabilities.length}）</span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          flexWrap: 'wrap',
                          gap: 6,
                          marginTop: 6,
                        }}
                      >
                        {card.acdl.agent.capabilities.map((cap) => (
                          <span key={cap} className="wb-status-chip wb-status-chip--info">
                            {cap}
                          </span>
                        ))}
                      </div>
                      <div className="wb-smart-card__meta" style={{ marginTop: 10 }}>
                        <span>📡 接口（GB/Z 185.4 interface）</span>
                      </div>
                      <pre
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-all',
                          margin: '6px 0 0',
                        }}
                      >
                        {JSON.stringify(card.acdl.agent.interface, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
