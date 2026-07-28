/**
 * WorkbenchPage — 对齐 Flutter AIChatPage (ai_chat_page.dart:815-838)
 *
 * 布局：Stack > Column[ChatHeader, AgentSelector, MessageList(Expanded) | EmptyState, TypingIndicator(if loading), ChatInputBar]
 *
 * 状态：
 *   messages[] — 消息列表
 *   isLoading — 流式加载中
 *   selectedAgent — 当前选中 agent（默认 master）
 *   isVoiceMode — 语音模式
 *   voicePanelOpen — 语音任务面板开关
 *   currentSessionId — 会话 id（持久化到 localStorage）
 *   thinkingSteps[] — 当前思考步骤
 *
 * 交互：
 *   _send() — 调用 apiClient.streamChat，处理 SSE 事件增量更新最后一条 agent 消息
 *   _toggleVoiceMode / _openVoiceTasks
 *
 * SSE 事件处理对齐 ai_chat_page.dart:328-393：
 *   meta → 记录 agent 交接 + 卡片类型
 *   token → 增量拼接 content，更新最后一条 agent 消息
 *   thinking_step → 追加思考步骤
 *   done → 完成最后一条消息（含卡片替换 + 思考步骤挂载）
 *   error → 错误恢复
 */

import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../components/workbench/workbench.css';
import '../components/layout/layout.css';
import { SuokeLayout } from '../components/layout';
import ChatHeader from '../components/workbench/ChatHeader';
import MessageList from '../components/workbench/MessageList';
import ChatInputBar from '../components/workbench/ChatInputBar';
import AgentSelector from '../components/workbench/AgentSelector';
import TypingIndicator from '../components/workbench/TypingIndicator';
import VoiceTaskPanel from '../components/workbench/VoiceTaskPanel';
import EmptyState from '../components/EmptyState';
import { apiClient } from '../services/api-client';
import {
  route,
  backendToAgent,
  agentToBackend,
  getAgentInfo,
} from '../services/agent-router';
import {
  userTextMessage,
  agentTextMessage,
  type ChatMessage,
  type SseEvent,
} from '../types/chat';

const SESSION_KEY = 'agent_session_id';

// 空状态快捷输入（对齐 ai_chat_page.dart:1756-1762）
const SUGGESTIONS = [
  { emoji: '💰', text: '查看预算情况', agent: 'budget' },
  { emoji: '📐', text: '我的设计方案', agent: 'design' },
  { emoji: '🔨', text: '施工进度如何', agent: 'construction' },
  { emoji: '🛒', text: '需要采购什么', agent: 'procurement' },
  { emoji: '🍳', text: '厨房布局建议', agent: 'kitchen' },
  { emoji: '🛁', text: '卫浴设计咨询', agent: 'bathroom' },
];

export default function WorkbenchPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState('master');
  const [isVoiceMode, setIsVoiceMode] = useState(false);
  const [voicePanelOpen, setVoicePanelOpen] = useState(false);
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const [currentProcessingAgent, setCurrentProcessingAgent] = useState('master');

  // refs 避免闭包陷阱
  const sessionIdRef = useRef<string | null>(localStorage.getItem(SESSION_KEY));
  const messagesRef = useRef<ChatMessage[]>(messages);
  messagesRef.current = messages;

  /** 更新最后一条 agent 文本消息（对齐 ai_chat_page.dart:221-232） */
  const updateLastAgentMessage = useCallback(
    (content: string, agent?: string) => {
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          const m = next[i];
          if (m.role === 'agent' && (!m.cardType || m.cardType === 'text')) {
            next[i] = { ...m, content, agent: agent ?? m.agent };
            break;
          }
        }
        return next;
      });
    },
    [],
  );

  /** 将最后一条 agent 文本消息替换为卡片（对齐 ai_chat_page.dart:238-261） */
  const replaceLastAgentWithCard = useCallback(
    (cardType: string, content: string, agent: string, payload?: Record<string, unknown>) => {
      if (cardType === 'text') return;
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i--) {
          const m = next[i];
          if (m.role === 'agent' && (!m.cardType || m.cardType === 'text')) {
            next[i] = { ...m, cardType, content, agent, payload };
            break;
          }
        }
        return next;
      });
    },
    [],
  );

  /** 发送消息（对齐 ai_chat_page.dart:278-408 _send） */
  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const routeResult = route(text);
      const targetAgent = routeResult.needsClarify ? selectedAgent : routeResult.agent;
      const backendAgent = agentToBackend(targetAgent);

      // 添加用户消息 + agent 占位消息
      const userMsg = userTextMessage(text);
      const placeholder = agentTextMessage('', targetAgent);
      setMessages((prev) => [...prev, userMsg, placeholder]);

      setIsLoading(true);
      setThinkingSteps([]);
      setCurrentProcessingAgent(targetAgent);

      // 构造历史（最近 20 条文本消息）
      const recent = messagesRef.current.slice(-20);
      const history = recent
        .filter((m) => !m.cardType || m.cardType === 'text')
        .map((m) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: (m.content ?? '').slice(0, 500),
          agent_type: m.agent ?? '',
        }));

      let fullContent = '';
      let currentAgent = targetAgent;
      let cardMessageType: string | null = null;
      let cardPayload: Record<string, unknown> | undefined;
      const steps: string[] = [];

      try {
        const stream = apiClient.streamChat(text, {
          agentType: backendAgent,
          history,
          sessionId: sessionIdRef.current,
        });

        for await (const event of stream as AsyncIterable<SseEvent>) {
          if (event.sessionId) {
            sessionIdRef.current = event.sessionId;
            localStorage.setItem(SESSION_KEY, event.sessionId);
          }

          switch (event.type) {
            case 'meta': {
              if (event.agentType) {
                const newAgent = backendToAgent(event.agentType);
                if (newAgent !== currentAgent) {
                  steps.push(`交接至 ${getAgentInfo(newAgent).name}`);
                  setThinkingSteps([...steps]);
                }
                currentAgent = newAgent;
                setCurrentProcessingAgent(newAgent);
              }
              if (event.messageType && event.messageType !== 'text') {
                cardMessageType = event.messageType;
                cardPayload = event.cardPayload;
              }
              break;
            }
            case 'token': {
              fullContent += event.content ?? '';
              updateLastAgentMessage(fullContent, currentAgent);
              break;
            }
            case 'thinking_step': {
              if (event.content) {
                steps.push(event.content);
                setThinkingSteps([...steps]);
                if (event.agentType) {
                  const a = backendToAgent(event.agentType);
                  setCurrentProcessingAgent(a);
                }
              }
              break;
            }
            case 'done': {
              if (event.content) {
                updateLastAgentMessage(event.content, currentAgent);
                fullContent = event.content;
              }
              if (cardMessageType && fullContent) {
                replaceLastAgentWithCard(cardMessageType, fullContent, currentAgent, cardPayload);
              }
              // 挂载思考步骤到最后一条消息
              if (steps.length > 0) {
                setMessages((prev) => {
                  const next = [...prev];
                  const last = next[next.length - 1];
                  if (last) {
                    next[next.length - 1] = {
                      ...last,
                      thinkingSteps: [...steps],
                      confidence: routeResult.confidence > 0.49 ? routeResult.confidence : undefined,
                    };
                  }
                  return next;
                });
              }
              setIsLoading(false);
              break;
            }
            case 'error': {
              updateLastAgentMessage(
                `抱歉，AI 服务暂时不可用: ${event.content ?? '未知错误'}`,
                currentAgent,
              );
              setIsLoading(false);
              break;
            }
          }
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        const truncated = msg.length > 80 ? `${msg.slice(0, 80)}...` : msg;
        updateLastAgentMessage(`抱歉，AI 服务暂时不可用: ${truncated}`, 'master');
        setIsLoading(false);
      }
    },
    [isLoading, selectedAgent, updateLastAgentMessage, replaceLastAgentWithCard],
  );

  const toggleVoiceMode = useCallback(() => {
    setIsVoiceMode((v) => !v);
  }, []);

  const isEmpty = messages.length === 0;

  return (
    <SuokeLayout>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          background: 'var(--bg-deep)',
        }}
        data-testid="wb-page"
      >
      <ChatHeader
        title="索克家居"
        subtitle="AI 智能装修助手"
        onAvatarClick={() => navigate('/settings')}
        onVoiceTasksClick={() => setVoicePanelOpen(true)}
        onTitleClick={() => navigate('/projects')}
      />
      <AgentSelector selected={selectedAgent} onSelect={setSelectedAgent} />

      {isEmpty ? (
        <EmptyState
          title="索克家居"
          subtitle="AI 智能装修助手"
          hints={['8 位核心 Agent + 专项 Agent', '7×24 全天候在线']}
          suggestions={SUGGESTIONS.map((s) => ({
            emoji: s.emoji,
            text: s.text,
            onClick: () => send(s.text),
          }))}
          footer="或直接输入提问"
          testId="wb-empty"
        />
      ) : (
        <MessageList messages={messages} />
      )}

      {isLoading && (
        <TypingIndicator agent={currentProcessingAgent} steps={thinkingSteps} />
      )}

      <ChatInputBar
        onSend={send}
        onAttach={() => {
          /* 批次 4 接入附件 */
        }}
        onEmoji={() => {
          /* 批次 4 接入 emoji picker */
        }}
        onVoice={toggleVoiceMode}
        onVoiceTasks={() => setVoicePanelOpen(true)}
        disabled={isLoading}
        isVoiceMode={isVoiceMode}
      />

      <VoiceTaskPanel
        open={voicePanelOpen}
        onClose={() => setVoicePanelOpen(false)}
      />
      </div>
    </SuokeLayout>
  );
}
