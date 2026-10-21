import React, { useState } from 'react';
import { View, Text, ScrollView, Input, Button } from '@tarojs/components';
import styles from './index.module.scss';

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
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

const REPLY_RULES: Array<{ keywords: string[]; reply: string }> = [
  {
    keywords: ['进度', '项目', '施工', '交付'],
    reply:
      '在「项目」页可查看全部改造项目的六阶段进度（设计 → 预算 → 采购 → 施工 → 质检 → 结算）。进入项目详情可看到下一节点、施工方与最近更新时间，数据按现场记录同步。'
  },
  {
    keywords: ['补贴', '适老', '政策', '资格'],
    reply:
      '「康养」页的补贴预估按套餐一口价的典型区间测算，未内置地方官方目录，也不判定个人资格；结果仅供参考，签约前请向当地主管部门核实申报口径。'
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

const fallbackReply =
  '当前为本地演示问答，尚未接入真实 AI 服务。可先问我项目进度、适老补贴预估、设备接入或空间健康分，涉及签约与资格认定的事项请以合同和主管部门口径为准。';

const replyOf = (question: string): string => {
  const hit = REPLY_RULES.find((rule) => rule.keywords.some((keyword) => question.includes(keyword)));
  return hit ? hit.reply : fallbackReply;
};

let messageSeq = 1;

const AiConsultPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: messageSeq++,
      role: 'assistant',
      text: '您好，我是索克家居 AI 管家（本地演示）。可以先问我交付进度、适老改造、设备接入或空间健康分。'
    }
  ]);
  const [draft, setDraft] = useState<string>('');
  const [anchorId, setAnchorId] = useState<string>('msg-1');

  const appendMessage = (message: ChatMessage) => {
    setMessages((prev) => [...prev, message]);
    setAnchorId(`msg-${message.id}`);
  };

  const handleSend = (text?: string) => {
    const question = (text ?? draft).trim();
    if (!question) return;
    console.info('[AiConsultPage] 提问', question);
    appendMessage({ id: messageSeq++, role: 'user', text: question });
    setDraft('');
    setTimeout(() => {
      appendMessage({ id: messageSeq++, role: 'assistant', text: replyOf(question) });
    }, 240);
  };

  const handleQuickQuestion = (item: QuickQuestion) => {
    handleSend(item.label);
  };

  return (
    <View className={styles.page}>
      <View className={styles.demoBanner}>
        <Text className={styles.demoBannerText}>
          演示模式：当前为本地示例问答，未接入真实 AI 服务；回复不构成诊断、补贴资格或合同承诺。
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
                    <Text className={styles.demoTagText}>本地示例</Text>
                  </View>
                </View>
                <Text className={styles.assistantText}>{message.text}</Text>
              </View>
            ) : (
              <View className={styles.userBubble}>
                <Text className={styles.userText}>{message.text}</Text>
              </View>
            )}
          </View>
        ))}
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
        <Button className={styles.sendButton} onClick={() => handleSend()}>
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
