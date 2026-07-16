/* ============================================
 * 索克家居 · 自然语言 → Agent 路由器
 * 不使用 @，纯自然语言意图识别
 * ============================================ */

const AgentRouter = {
  // 关键词映射表
  patterns: [
    {
      agent: 'budget',
      label: '💰 预算',
      keywords: ['预算', '花了多少钱', '还剩多少', '支出', '费用', '超支', '成本', '价格', '多少钱', '报价', '账单', '付款', '支付'],
    },
    {
      agent: 'design',
      label: '📐 设计',
      keywords: ['设计', '方案', '图纸', '布局', '风格', '装修风格', '效果图', '改造', '改', '开放式', '打通', '隔断', 'CAD', '3D'],
    },
    {
      agent: 'construction',
      label: '🔨 施工',
      keywords: ['施工', '进度', '开工', '水电', '木工', '瓦工', '油漆', '泥工', '贴砖', '刷墙', '打孔', '拆', '今天干', '任务', '工序', '阶段'],
    },
    {
      agent: 'procurement',
      label: '🛒 采购',
      keywords: ['采购', '买', '订购', '下单', '物流', '到货', '发货', '什么时候到', '供应商', '比价', '地砖', '瓷砖', '地板', '涂料', '材料',
                 '发布产品', '上架', '我的产品', '修改产品', '下架', '库存', '报价', '改价格', '产品管理'],
    },
    {
      agent: 'quality',
      label: '✅ 质检',
      keywords: ['质检', '验收', '检查', '问题', '毛病', '整改', '返工', '合格', '不合格', '检测', '偏差', '偏差多少'],
    },
    {
      agent: 'settlement',
      label: '🧾 结算',
      keywords: ['结算', '对账', '尾款', '结清', '结账', '完工结算', '最终账单', '总账'],
    },
    {
      agent: 'support',
      label: '🎧 客服',
      keywords: ['客服', '帮助', '怎么用', '怎么操作', '联系', '投诉', '建议', '反馈', '问题反馈'],
    },
    {
      agent: 'master',
      label: '🏠 总控',
      keywords: ['总控', '统筹', '协调', '概况', '整体', '总结', '汇报', '状态', '什么时候完工', '还要多久'],
    },
    {
      agent: 'admin',
      label: '⚙️ 管理',
      keywords: ['用户管理', '角色管理', '权限管理', '平台统计', '管理员', '禁用用户',
                 '启用用户', '审核认证', '修改角色', '用户列表', '设为管理员',
                 '平台数据', '全部项目', '所有用户', '实名认证'],
    },
  ],

  // 路由
  route(text) {
    if (!text || typeof text !== 'string') {
      return { agent: 'master', confidence: 0, payload: null };
    }
    const lower = text.toLowerCase();
    const scores = {};

    for (const p of this.patterns) {
      scores[p.agent] = 0;
      for (const kw of p.keywords) {
        if (text.includes(kw) || lower.includes(kw.toLowerCase())) {
          scores[p.agent] += 1;
        }
      }
    }

    // 找最高分
    let bestAgent = 'master';
    let bestScore = 0;
    for (const [agent, score] of Object.entries(scores)) {
      if (score > bestScore) {
        bestScore = score;
        bestAgent = agent;
      }
    }

    // 置信度：匹配关键词数 / 文本长度的相对值
    const confidence = bestScore === 0 ? 0 : Math.min(1, bestScore / Math.max(1, Math.ceil(text.length / 20)));

    // 置信度低 → 总控 Agent 澄清
    if (confidence < 0.3 || bestScore === 0) {
      return {
        agent: 'master',
        confidence,
        payload: {
          clarify: true,
          message: '我理解你想了解一些信息。能更具体一些吗？比如想问预算、设计、施工进度还是其他？',
        },
      };
    }

    return {
      agent: bestAgent,
      confidence,
      payload: { original_text: text },
    };
  },

  // 获取 Agent 显示信息
  getAgentInfo(agentKey) {
    const map = {
      master:      { name: '总控',   emoji: '🏠', color: 'var(--agent-master)' },
      design:      { name: '设计',   emoji: '📐', color: 'var(--agent-design)' },
      budget:      { name: '预算',   emoji: '💰', color: 'var(--agent-budget)' },
      procurement:{ name: '采购',   emoji: '🛒', color: 'var(--agent-procurement)' },
      construction:{ name: '施工',   emoji: '🔨', color: 'var(--agent-construction)' },
      quality:     { name: '质检',   emoji: '✅', color: 'var(--agent-quality)' },
      settlement:  { name: '结算',   emoji: '🧾', color: 'var(--agent-settlement)' },
      support:     { name: '客服',   emoji: '🎧', color: 'var(--agent-support)' },
      admin:       { name: '管理',   emoji: '⚙️', color: 'var(--accent)' },
    };
    return map[agentKey] || map.master;
  },
};

// 暴露到全局
window.AgentRouter = AgentRouter;
