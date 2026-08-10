/**
 * A2APage — A2A (Agent-to-Agent) 协议（基于 Google A2A v1.0 规范）
 *
 * 结构：Scaffold > AppBar(A2A 协议) > 已注册 Agent 列表 > 下发任务表单 > 任务状态查询
 * API（对齐 app/api/a2a.py，前缀 /a2a；任务下发/查询受 a2a_enabled flag 控制）：
 *   GET  /api/a2a/agents              列出已注册 Agent（{ agents, count }）
 *   POST /api/a2a/tasks/send          下发任务（flag 关闭返回 503「A2A 协议未启用」）
 *   GET  /api/a2a/tasks/{id}          任务详情（含 result/error）
 *   GET  /api/a2a/tasks/{id}/status   任务状态（{ task_id, state }）
 *
 * state: submitted | working | completed | failed；flag 未启用时页面诚实提示。
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type {
  A2AAgentListResponse,
  A2ATaskResponse,
  A2ATaskStatusResponse,
} from '../types/domain';

/** 404/503 多为灰度 flag 未启用，追加诚实提示（保留后端真实 error 文案） */
function flagGuardMessage(status: number, error?: string): string {
  if (status === 404 || status === 503) {
    return `功能未启用（灰度 flag 默认关闭）：${error ?? `HTTP ${status}`}`;
  }
  return error ?? `HTTP ${status}`;
}

const STATE_META: Record<string, { label: string; tone: string }> = {
  submitted: { label: '已提交', tone: 'wb-status-chip--muted' },
  working: { label: '执行中', tone: 'wb-status-chip--info' },
  completed: { label: '已完成', tone: 'wb-status-chip--success' },
  failed: { label: '失败', tone: 'wb-status-chip--danger' },
};

export default function A2APage() {
  const navigate = useNavigate();

  // 下发任务表单
  const [selectedAgent, setSelectedAgent] = useState('');
  const [message, setMessage] = useState('');
  const [projectId, setProjectId] = useState('');
  const [sending, setSending] = useState(false);
  const [sentTask, setSentTask] = useState<A2ATaskResponse | null>(null);

  // 任务状态查询
  const [lookupId, setLookupId] = useState('');
  const [statusTaskId, setStatusTaskId] = useState<string | null>(null);

  const [opError, setOpError] = useState<string | null>(null);

  const {
    data: list,
    loading,
    error,
    reload,
  } = useAsync<A2AAgentListResponse | null>(async () => {
    const r = await apiClient.listA2AAgents<A2AAgentListResponse>();
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, []);

  const agents = list?.agents ?? [];

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedAgent || !message.trim()) {
      setOpError('请选择 Agent 并填写消息');
      return;
    }
    setSending(true);
    setOpError(null);
    setSentTask(null);
    try {
      const r = await apiClient.sendA2ATask<A2ATaskResponse>({
        agent_name: selectedAgent,
        message: message.trim(),
        project_id: projectId.trim() || null,
      });
      if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
      setSentTask(r.data);
      setStatusTaskId(null);
    } catch (err) {
      setOpError(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  }

  const {
    data: status,
    loading: statusLoading,
    error: statusError,
    reload: reloadStatus,
  } = useAsync<A2ATaskStatusResponse | null>(async () => {
    if (!statusTaskId) return null;
    const r = await apiClient.getA2ATaskStatus<A2ATaskStatusResponse>(statusTaskId);
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [statusTaskId]);

  const {
    data: taskDetail,
    loading: taskDetailLoading,
    error: taskDetailError,
    reload: reloadTaskDetail,
  } = useAsync<A2ATaskResponse | null>(async () => {
    if (!statusTaskId) return null;
    const r = await apiClient.getA2ATask<A2ATaskResponse>(statusTaskId);
    if (!r.isSuccess || !r.data) throw new Error(flagGuardMessage(r.status, r.error));
    return r.data;
  }, [statusTaskId]);

  function stateChip(state: string) {
    const meta = STATE_META[state] ?? { label: state, tone: 'wb-status-chip--muted' };
    return <span className={`wb-status-chip ${meta.tone}`}>{meta.label}</span>;
  }

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-a2a-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">🤝 A2A 协议</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {opError && (
            <div
              className="wb-create-form__error"
              style={{ marginBottom: 12 }}
              data-testid="wb-a2a-op-error"
            >
              ⚠ {opError}
            </div>
          )}

          {/* 已注册 Agent 列表 */}
          <div className="wb-section-label">已注册 Agent（{agents.length}）</div>
          {loading && (
            <div className="wb-state" data-testid="wb-a2a-agents-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载 Agent 列表…</div>
            </div>
          )}
          {error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-a2a-agents-error">
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
            <div className="wb-state" data-testid="wb-a2a-agents-empty">
              <div className="wb-state__icon">🤖</div>
              <div>暂无已注册 Agent</div>
            </div>
          )}
          {!loading && !error && agents.length > 0 && (
            <div data-testid="wb-a2a-agents-content">
              {agents.map((agent, i) => (
                <div key={agent.name} className="wb-smart-card" data-testid={`wb-a2a-agent--${i}`}>
                  <div className="wb-smart-card__head">
                    <div className="wb-smart-card__room">{agent.name}</div>
                    <span className="wb-status-chip wb-status-chip--muted">
                      {agent.class_name}
                    </span>
                  </div>
                  {agent.description && (
                    <div
                      style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)', marginTop: 4 }}
                    >
                      {agent.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* 下发任务 */}
          <div className="wb-create-form" style={{ marginTop: 20 }} data-testid="wb-a2a-send">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">📤</div>
              <div>
                <div className="wb-create-form__title">下发 A2A 任务</div>
                <div className="wb-create-form__subtitle">
                  受 a2a_enabled flag 控制，未启用时后端返回 503「A2A 协议未启用」
                </div>
              </div>
            </div>
            <form onSubmit={handleSend}>
              <div className="wb-create-form__body">
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-a2a-agent-select">
                    目标 Agent <span className="wb-create-form__required">*</span>
                  </label>
                  <select
                    id="wb-a2a-agent-select"
                    className="wb-input"
                    value={selectedAgent}
                    onChange={(e) => setSelectedAgent(e.target.value)}
                    data-testid="wb-a2a-agent-select"
                  >
                    <option value="">选择 Agent…</option>
                    {agents.map((agent) => (
                      <option key={agent.name} value={agent.name}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-a2a-message">
                    消息 <span className="wb-create-form__required">*</span>
                  </label>
                  <textarea
                    id="wb-a2a-message"
                    className="wb-input"
                    rows={3}
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="向该 Agent 发送的任务消息"
                    data-testid="wb-a2a-message-input"
                  />
                </div>
                <div className="wb-create-form__field">
                  <label className="wb-create-form__label" htmlFor="wb-a2a-project">
                    project_id（可选）
                  </label>
                  <input
                    id="wb-a2a-project"
                    className="wb-input"
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                    placeholder="项目维度任务时填写"
                    data-testid="wb-a2a-project-input"
                  />
                </div>
                <div className="wb-create-form__actions">
                  <button
                    className="wb-theme-option wb-theme-option--active"
                    type="submit"
                    disabled={sending}
                    data-testid="wb-a2a-send-btn"
                    style={{ width: '100%' }}
                  >
                    {sending ? '下发中…' : '📤 下发任务'}
                  </button>
                </div>
              </div>
            </form>
          </div>

          {/* 任务结果 */}
          {sentTask && (
            <div className="wb-smart-card" style={{ marginTop: 12 }} data-testid="wb-a2a-sent-task">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">任务 {sentTask.task_id}</div>
                {stateChip(sentTask.state)}
              </div>
              {typeof sentTask.result === 'string' && (
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--font-size-sm)', marginTop: 6 }}>
                  {sentTask.result}
                </div>
              )}
              {sentTask.error && (
                <div
                  style={{
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--danger)',
                    marginTop: 6,
                  }}
                >
                  ❌ {sentTask.error}
                </div>
              )}
              <div className="wb-create-form__actions" style={{ marginTop: 8 }}>
                <button
                  className="wb-theme-option"
                  type="button"
                  onClick={() => {
                    setStatusTaskId(sentTask.task_id);
                    setLookupId(sentTask.task_id);
                  }}
                  data-testid="wb-a2a-query-sent"
                >
                  🔍 查询详情
                </button>
              </div>
            </div>
          )}

          {/* 任务状态查询 */}
          <div className="wb-create-form" style={{ marginTop: 20 }} data-testid="wb-a2a-status">
            <div className="wb-create-form__head">
              <div className="wb-create-form__badge">🔍</div>
              <div>
                <div className="wb-create-form__title">任务状态 / 详情查询</div>
                <div className="wb-create-form__subtitle">
                  通过 task_id 查询任务状态与完整结果（受 a2a_enabled flag 控制）
                </div>
              </div>
            </div>
            <div className="wb-create-form__body">
              <div className="wb-create-form__field">
                <label className="wb-create-form__label" htmlFor="wb-a2a-taskid">
                  task_id
                </label>
                <input
                  id="wb-a2a-taskid"
                  className="wb-input"
                  value={lookupId}
                  onChange={(e) => setLookupId(e.target.value)}
                  placeholder="如 a2a_xxxxxxxxxxxx"
                  data-testid="wb-a2a-taskid-input"
                />
              </div>
              <div className="wb-create-form__actions">
                <button
                  className="wb-theme-option wb-theme-option--active"
                  type="button"
                  disabled={!lookupId.trim()}
                  onClick={() => setStatusTaskId(lookupId.trim())}
                  data-testid="wb-a2a-status-btn"
                  style={{ width: '100%' }}
                >
                  查询
                </button>
              </div>
            </div>
          </div>

          {statusLoading && (
            <div className="wb-state" data-testid="wb-a2a-status-loading">
              <div className="wb-state__icon">⏳</div>
              <div>查询任务状态…</div>
            </div>
          )}
          {(statusError || taskDetailError) && !statusLoading && (
            <div className="wb-state wb-state--error" data-testid="wb-a2a-status-error">
              <div className="wb-state__icon">⚠</div>
              <div>{statusError ?? taskDetailError}</div>
              <button
                className="wb-theme-option wb-theme-option--active"
                onClick={() => {
                  if (statusError) void reloadStatus();
                  if (taskDetailError) void reloadTaskDetail();
                }}
                type="button"
              >
                重试
              </button>
            </div>
          )}

          {status && !statusLoading && !statusError && (
            <div className="wb-smart-card" style={{ marginTop: 12 }} data-testid="wb-a2a-status-result">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">状态查询</div>
                {stateChip(status.state)}
              </div>
              <div className="wb-smart-card__meta" style={{ marginTop: 6 }}>
                <span>🆔 {status.task_id}</span>
              </div>
            </div>
          )}

          {taskDetail && !taskDetailLoading && !taskDetailError && (
            <div className="wb-smart-card" style={{ marginTop: 12 }} data-testid="wb-a2a-task-detail">
              <div className="wb-smart-card__head">
                <div className="wb-smart-card__room">任务详情 {taskDetail.task_id}</div>
                {stateChip(taskDetail.state)}
              </div>
              {typeof taskDetail.result === 'string' && (
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--font-size-sm)', marginTop: 6 }}>
                  {taskDetail.result}
                </div>
              )}
              {taskDetail.error && (
                <div
                  style={{
                    fontSize: 'var(--font-size-sm)',
                    color: 'var(--danger)',
                    marginTop: 6,
                  }}
                >
                  ❌ {taskDetail.error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
