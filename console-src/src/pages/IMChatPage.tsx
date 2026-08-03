/**
 * IMChatPage — F40 三方协作 IM 群（对齐 flutter_app/lib/pages/chat_page.dart）
 *
 * 结构：Scaffold > AppBar(协作聊天) > [项目选择器] > 聊天室头部（含 Agent 成员标注）
 *   + 消息流 + 发送框
 * API（app/api/chat.py）：
 *   GET  /api/chat/rooms/{projectId}（获取/创建聊天室）
 *   GET  /api/chat/rooms/{roomId}/agents（查询 Agent 群成员，F40 新增）
 *   GET  /api/chat/messages/{projectId}（消息列表，含 Agent 自动回复标注）
 *   POST /api/chat/messages（发送消息）
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './pages.css';
import { SuokeLayout } from '../components/layout';
import { useAsync } from '../hooks/useAsync';
import { apiClient } from '../services/api-client';
import type { ChatMessage, ChatRoom, ChatRoomAgents, Project } from '../types/domain';

function fmtTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function IMChatPage() {
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const { data: projects } = useAsync<Project[]>(async () => {
    const r = await apiClient.listProjects<Project[]>();
    return r.isSuccess && r.data ? r.data : [];
  }, []);

  useEffect(() => {
    if (!selectedProjectId && projects && projects.length > 0) {
      setSelectedProjectId(projects[0].id);
    }
  }, [projects, selectedProjectId]);

  // 聊天室（依赖项目，后端 get_or_create 保证存在）
  const { data: room, loading: roomLoading, error: roomError, reload: roomReload } =
    useAsync<ChatRoom | null>(
      async () => {
        if (!selectedProjectId) return null;
        const r = await apiClient.getChatRoom<ChatRoom>(selectedProjectId);
        if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载聊天室失败');
        return r.data;
      },
      [selectedProjectId],
    );

  // Agent 群成员（F40）
  const { data: roomAgents, reload: agentsReload } = useAsync<ChatRoomAgents | null>(
    async () => {
      if (!room) return null;
      const r = await apiClient.listRoomAgents<ChatRoomAgents>(room.id);
      return r.isSuccess && r.data ? r.data : null;
    },
    [room?.id],
  );

  // 消息流
  const { data: messages, loading: msgsLoading, error: msgsError, reload: msgsReload } =
    useAsync<ChatMessage[] | null>(
      async () => {
        if (!selectedProjectId) return null;
        const r = await apiClient.listChatMessages<ChatMessage[]>(selectedProjectId);
        if (!r.isSuccess || !r.data) throw new Error(r.error ?? '加载消息失败');
        return r.data;
      },
      [selectedProjectId, room?.id],
    );

  const send = async () => {
    const content = draft.trim();
    if (!content || !selectedProjectId || sending) return;
    setSending(true);
    setSendError(null);
    try {
      const r = await apiClient.sendChatMessage<ChatMessage>({
        project_id: selectedProjectId,
        content,
      });
      if (!r.isSuccess) {
        setSendError(r.error ?? '发送失败');
        return;
      }
      setDraft('');
      await msgsReload();
      await agentsReload();
    } finally {
      setSending(false);
    }
  };

  const loading = roomLoading || msgsLoading;
  const error = roomError ?? msgsError;
  const reload = () => {
    roomReload();
    msgsReload();
  };

  // 后端按 created_at desc 返回，聊天流需旧消息在上
  const displayMessages = messages ? [...messages].reverse() : [];

  return (
    <SuokeLayout>
      <div className="wb-page-shell" data-testid="wb-imchat-page">
        <div className="wb-page-header">
          <button
            className="wb-page-header__back"
            onClick={() => navigate('/')}
            aria-label="返回"
            type="button"
          >
            ‹
          </button>
          <div className="wb-page-header__title">💬 协作聊天</div>
        </div>

        <div className="wb-page-body wb-page-body--narrow">
          {/* 项目选择器 */}
          <div className="wb-project-picker">
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              aria-label="选择项目"
              data-testid="wb-imchat-project-select"
            >
              <option value="">选择项目…</option>
              {projects?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId && (
            <div className="wb-state" data-testid="wb-imchat-no-project">
              <div className="wb-state__icon">📋</div>
              <div>请先选择项目</div>
            </div>
          )}

          {selectedProjectId && loading && (
            <div className="wb-state" data-testid="wb-imchat-loading">
              <div className="wb-state__icon">⏳</div>
              <div>加载聊天室中…</div>
            </div>
          )}

          {selectedProjectId && error && !loading && (
            <div className="wb-state wb-state--error" data-testid="wb-imchat-error">
              <div className="wb-state__icon">⚠</div>
              <div>{error}</div>
              <button className="wb-theme-option wb-theme-option--active" onClick={reload}>
                重试
              </button>
            </div>
          )}

          {selectedProjectId && !loading && !error && room && (
            <div data-testid="wb-imchat-content">
              {/* 聊天室头部：名称 + Agent 成员标注 */}
              <div className="wb-smart-card">
                <div className="wb-smart-card__head">
                  <div className="wb-smart-card__room">{room.name}</div>
                  <span className="wb-status-chip wb-status-chip--accent">
                    {room.member_count ?? 0} 位成员
                  </span>
                </div>
                <div className="wb-crew-card__tags" style={{ marginTop: 8 }}>
                  {roomAgents && roomAgents.agent_members.length > 0 ? (
                    <>
                      <span
                        className="wb-status-chip wb-status-chip--info"
                        style={{ marginRight: 4 }}
                      >
                        🤖 AI 成员
                      </span>
                      {roomAgents.agent_members.map((agent) => (
                        <span className="wb-crew-tag" key={agent} data-testid="wb-imchat-agent">
                          🤖 {agent}
                        </span>
                      ))}
                    </>
                  ) : (
                    <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                      暂无 Agent 群成员，可通过工作台与 Agent 协作
                    </span>
                  )}
                </div>
              </div>

              {/* 消息流 */}
              <div className="wb-section-label">
                消息（{displayMessages.length}）
              </div>
              {displayMessages.length === 0 && (
                <div className="wb-state" data-testid="wb-imchat-empty">
                  <div className="wb-state__icon">💬</div>
                  <div>暂无消息，发送第一条协作消息吧</div>
                </div>
              )}
              {displayMessages.map((msg) => {
                const isAgent =
                  msg.sender_role === 'agent' || Boolean(msg.generated_by) || Boolean(msg.agent_mode);
                return (
                  <div
                    key={msg.id}
                    className="wb-budget-item"
                    style={{ flexDirection: 'column', alignItems: 'stretch', gap: 6 }}
                    data-testid="wb-imchat-message"
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 8,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                        <span className="wb-budget-item__name" style={{ fontSize: 14 }}>
                          {isAgent ? '🤖 ' : '👤 '}
                          {msg.sender_name}
                        </span>
                        <span
                          className={`wb-status-chip ${isAgent ? 'wb-status-chip--info' : 'wb-status-chip--muted'}`}
                        >
                          {isAgent ? 'Agent' : msg.sender_role || '用户'}
                        </span>
                        {msg.is_placeholder && (
                          <span className="wb-status-chip wb-status-chip--warning">占位回复</span>
                        )}
                      </div>
                      <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--text-muted)' }}>
                        {fmtTime(msg.created_at)}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--text-primary)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        lineHeight: 1.6,
                      }}
                    >
                      {msg.content}
                    </div>
                    {(msg.generated_by || msg.agent_mode) && (
                      <div
                        style={{
                          fontSize: 'var(--font-size-xs)',
                          color: 'var(--text-muted)',
                          borderTop: '1px dashed var(--border)',
                          paddingTop: 6,
                        }}
                      >
                        {msg.generated_by && <span>由 {msg.generated_by} 生成 · </span>}
                        {msg.agent_mode && <span>模式 {msg.agent_mode} · </span>}
                        {msg.engine && <span>引擎 {msg.engine}</span>}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* 发送框 */}
              <div style={{ marginTop: 16 }} data-testid="wb-imchat-input-bar">
                <textarea
                  className="wb-textarea"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="输入协作消息，按 Enter 发送（Shift+Enter 换行）"
                  aria-label="消息内容"
                  data-testid="wb-imchat-input"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                {sendError && (
                  <div
                    style={{
                      marginTop: 6,
                      fontSize: 'var(--font-size-sm)',
                      color: 'var(--danger)',
                    }}
                  >
                    ⚠ {sendError}
                  </div>
                )}
                <div style={{ marginTop: 8, textAlign: 'right' }}>
                  <button
                    type="button"
                    className="wb-theme-option wb-theme-option--active"
                    onClick={send}
                    disabled={sending || !draft.trim()}
                    data-testid="wb-imchat-send"
                  >
                    {sending ? '发送中…' : '📨 发送'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </SuokeLayout>
  );
}
