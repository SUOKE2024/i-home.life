import React, { useState } from 'react';
import { View, Text, ScrollView, Input, Button } from '@tarojs/components';
import Taro from '@tarojs/taro';
import { aiApi, track } from '@/services/api';
import { ensureSession } from '@/services/session';
import styles from './index.module.scss';

type ReplyMode = 'ai' | 'kb' | 'local';

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  mode?: ReplyMode;
  sources?: Array<{ title: string; citation: string }>;
}

interface QuickQuestion {
  key: string;
  label: string;
}

const QUICK_QUESTIONS: QuickQuestion[] = [
  { key: 'progress', label: '项目进度怎么查？' },
  { key: 'subsidy', label: '适老改造补贴怎么估？' },
  { key: 'device', label: '设备接入要准备什么？' },
  { key: 'space', label: '空间健康分怎么算？' }
];

/**
 * 本地兜底问答：仅在「未登录 / 后端不可达」时使用，界面上必须标注「本地示例」，
 * 不得伪装成真实 AI 回复（合规口径：AI 生成内容需可辨识）。
 */
const REPLY_RULES: Array<{ keywords: string[]; reply: string }> = [
  {
    keywords: ['进度', '项目', '施工', '交付'],
    reply:
      '在「项目」页可查看全部改造项目的阶段进度（设计 → 预算 → 采购 → 施工 → 质检 → 结算）。进入项目详情可看到下一节点与最近更新时间，数据按现场记录同步。'
  },
  {
    keywords: ['补贴', '适老', '政策', '资格'],
    reply:
      '「康养」页的补贴预估按标准快装套餐一口价与政策档案比例测算，未内置地方官方目录，也不判定个人资格；结果仅供参考，签约前请向当地主管部门核实申报口径。'
  },
  {
    keywords: ['设备', '接入', '智控', '场景'],
    reply:
      '智能设备接入后，可在「智控」页查看设备状态与场景编排。就绪度按设备接入、感知覆盖、场景编排、合规就绪四维统计，只计算真实接入的数据。'
  },
  {
    keywords: ['健康分', '空间', '评分', '就绪'],
    reply:
      '空间健康分由四维就绪度汇总：设备接入 30 分、感知覆盖 25 分、场景编排 25 分、合规就绪 20 分。未接入的维度计 0 分，不做虚增。'
  }
];

const LOCAL_FALLBACK =
  '当前未连接到在线 AI 服务，我是本地示例问答。可以先问我项目进度、适老补贴预估、设备接入或空间健康分；涉及签约与资格认定的事项请以合同和主管部门口径为准。';

const localReplyOf = (question: string): string => {
  const hit = REPLY_RULES.find((rule) => rule.keywords.some((keyword) => question.includes(keyword)));
  return hit ? hit.reply : LOCAL_FALLBACK;
};

const MODE_TAG: Record<ReplyMode, string> = {
  ai: 'AI 生成',
  kb: '知识库引用',
  local: '本地示例'
};

let messageSeq = 1;

const AiConsultPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: messageSeq++,
      role: 'assistant',
      text: '您好，我是索克家居 AI 管家。可以问我交付进度、适老改造、设备接入或空间就绪度；也可直接描述您家的问题。',
      mode: 'ai'
    }
  ]);
  const [draft, setDraft] = useState<string>('');
  const [anchorId, setAnchorId] = useState<string>('msg-1');
  const [thinking, setThinking] = useState<boolean>(false);

  const appendMessage = (message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
    setAnchorId(`msg-${message.id}`);
  };

  /** 依次尝试：客服 Agent → 知识库问答 → 本地兜底，任一步成功即止 */
  const requestReply = async (
    question: string
  ): Promise<{ text: string; mode: ReplyMode; sources?: ChatMessage['sources'] }> => {
    const authenticated = await ensureSession();
    if (authenticated) {
      try {
        const res = await aiApi.concierge(question);
        if (res?.reply) return { text: res.reply, mode: 'ai' };
      } catch (err) {
        console.warn('[AiConsultPage] 客服 Agent 不可用，尝试知识库问答', err);
      }

      try {
        const res = await aiApi.search(question);
        if (res?.answer) {
          return {
            text: res.answer,
            mode: res.match_type === 'knowledge_base' ? 'kb' : 'ai',
            sources: (res.sources || []).map((item) => ({
              title: item.title || item.domain,
              citation: item.citation
            }))
          };
        }
      } catch (err) {
        console.warn('[AiConsultPage] 知识库问答不可用，使用本地兜底', err);
      }
    }

    return { text: localReplyOf(question), mode: 'local' };
  };

  const handleSend = async (text?: string) => {
    const question = (text ?? draft).trim();
    if (!question || thinking) return;
    console.info('[AiConsultPage] 提问', question);
    appendMessage({ id: messageSeq++, role: 'user', text: question });
    setDraft('');
    setThinking(true);
    Taro.showLoading({ title: 'AI 正在思考', mask: true });
    try {
      const reply = await requestReply(question);
      appendMessage({
        id: messageSeq++,
        role: 'assistant',
        text: reply.text,
        mode: reply.mode,
        sources: reply.sources
      });
      track('ai_consult', { mode: reply.mode });
    } catch (err) {
      console.error('[AiConsultPage] 回复生成失败', err);
      appendMessage({
        id: messageSeq++,
        role: 'assistant',
        text: '服务暂时不可用，请稍后重试。如涉及紧急健康情况，请立即联系医疗机构。',
        mode: 'local'
      });
    } finally {
      Taro.hideLoading();
      setThinking(false);
    }
  };

  const handleQuickQuestion = (item: QuickQuestion) => {
    handleSend(item.label);
  };

  return (
    <View className={styles.page}>
      <View className={styles.demoBanner}>
        <Text className={styles.demoBannerText}>
          回复由 AI 生成或引自知识库，仅供参考；不构成诊疗、补贴资格认定或合同承诺。
        </Text>
      </View>

      <ScrollView className={styles.messages} scrollY scrollIntoView={anchorId} scrollWithAnimation>
        {messages.map((message) => (
          <View
            key={message.id}
            id={`msg-${message.id}`}
            className={message.role === 'user' ? styles.userRow : styles.assistantRow}
          >
            {message.role === 'assistant' ? (
              <View className={styles.assistantBubble}>
                <View className={styles.assistantMeta}>
                  <Text className={styles.assistantName}>AI 管家</Text>
                  <View className={styles.demoTag}>
                    <Text className={styles.demoTagText}>
                      {MODE_TAG[message.mode || 'ai']}
                    </Text>
                  </View>
                </View>
                <Text className={styles.assistantText}>{message.text}</Text>
                {message.sources && message.sources.length > 0 ? (
                  <View className={styles.sourceList}>
                    {message.sources.map((source) => (
                      <Text key={source.citation || source.title} className={styles.sourceItem}>
                        来源：{source.title}
                        {source.citation ? ` · ${source.citation}` : ''}
                      </Text>
                    ))}
                  </View>
                ) : null}
              </View>
            ) : (
              <View className={styles.userBubble}>
                <Text className={styles.userText}>{message.text}</Text>
              </View>
            )}
          </View>
        ))}
        {thinking ? (
          <View className={styles.assistantRow}>
            <View className={styles.thinkingBubble}>
              <Text className={styles.thinkingText}>正在检索知识库并生成回复…</Text>
            </View>
          </View>
        ) : null}
      </ScrollView>

      <View className={styles.quickWrap}>
        {QUICK_QUESTIONS.map((item) => (
          <View key={item.key} className={styles.quickChip} onClick={() => handleQuickQuestion(item)}>
            <Text className={styles.quickChipText}>{item.label}</Text>
          </View>
        ))}
      </View>

      <View className={styles.inputBar}>
        <Input
          className={styles.input}
          value={draft}
          placeholder='输入您想咨询的问题'
          confirmType='send'
          onInput={(event) => setDraft(event.detail.value)}
          onConfirm={() => handleSend()}
        />
        <Button className={styles.sendButton} onClick={() => handleSend()} disabled={thinking}>
          发送
        </Button>
      </View>

      <Text className={styles.footerNote}>
        健康与补贴相关信息仅供参考，不替代专业诊疗与主管部门核定；紧急情况请及时联系医疗机构。
      </Text>
    </View>
  );
};

export default AiConsultPage;
