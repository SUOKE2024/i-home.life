/* ============================================
 * 索克家居 · 落地页聊天演示剧本
 * 4 角色专属剧本 + 纯前端 mock
 * ============================================ */

const DemoNarrative = {
  // ── 角色配置 ──
  roles: {
    owner: {
      title: '索克家居 · 阳光花园 3 栋 201',
      subtitle: '8 AI 团队 7×24 自主运转 · 业主视角',
      dateLabel: '2026-07-13 · 阳光花园 3 栋 201 项目启动',
      ctaText: '输入手机号，让 AI 团队开始服务你家',
      ctaBody: '上面这条审批，就是业主每天唯一需要做的事。登录后，AI 团队开始服务你家的装修。',
      brandTitle: '这就是 8 AI 团队 7×24 自主运转的样子',
      brandBody: '量房、设计、预算、比价——全部自动完成。人类业主只需在关键节点审批，其余时间交给 AI。',
      inputPlaceholder: '试试问：我家 120㎡ 要多少钱？',
    },
    designer: {
      title: '索克家居 · 设计师协作台',
      subtitle: 'AI 设计 Agent 协助你 30 分钟出 3 套方案',
      dateLabel: '2026-07-13 · 新设计任务到达',
      ctaText: '登录接单，让 AI 帮你出图',
      ctaBody: '登录后，AI 设计 Agent 协助你量房、出图、算预算，30 分钟交付 3 套方案。',
      brandTitle: 'AI 设计 Agent 是你的超级助手',
      brandBody: '从量房复核到效果图生成，从预算估算到施工图深化——AI 协助你完成 80% 重复工作，你专注创意。',
      inputPlaceholder: '试试问：怎么接设计任务？',
    },
    supplier: {
      title: '索克家居 · 供应商工作台',
      subtitle: 'AI 采购 Agent 自动匹配询价订单',
      dateLabel: '2026-07-13 · 新采购询价到达',
      ctaText: '登录管理产品与订单',
      ctaBody: '登录后，发布你的产品，AI 采购 Agent 自动匹配询价，订单自动找你，担保支付保障回款。',
      brandTitle: 'AI 采购 Agent 让订单自动找你',
      brandBody: '发布产品后，AI 自动匹配业主需求，自动比价，自动下单。担保支付 + 物流追踪，全流程透明。',
      inputPlaceholder: '试试问：怎么接到订单？',
    },
    foreman: {
      title: '索克家居 · 工长施工台',
      subtitle: 'AI 施工+质检 Agent 协助你管理工地',
      dateLabel: '2026-07-13 · 水电阶段开工',
      ctaText: '登录接单，让 AI 帮你管工地',
      ctaBody: '登录后，AI 施工 Agent 帮你排工序，质检 Agent 帮你验收，结算 Agent 帮你对账回款。',
      brandTitle: 'AI 施工+质检 Agent 是你的工地管家',
      brandBody: '工序排期、现场拍照、隐蔽工程验收、进度款结算——AI 协助你管理工地每个环节，不漏项不返工。',
      inputPlaceholder: '试试问：怎么接施工任务？',
    },
  },

  // ── 4 套剧本 ──
  scripts: {
    // ==================== 业主剧本 ====================
    owner: [
      { type: 'system', content: '── 2026-07-13 · 阳光花园 3 栋 201 项目启动 ──' },
      {
        type: 'text', agent: 'master', timestamp: '2026-07-13T09:00:00',
        content: '项目已创建，8 AI 团队就位。我将统筹全链路，你只需在关键节点审批。',
        collaboration: [
          { agent: 'design', action: '开始量房' },
          { agent: 'budget', action: '编制预算' },
          { agent: 'procurement', action: '询价' },
          { agent: 'construction', action: '待命' },
        ],
      },
      {
        type: 'task_card', agent: 'design', timestamp: '2026-07-13T09:02:00',
        payload: {
          title: '今日任务 · 量房复核',
          tasks: [
            { name: '量房复核 120.5㎡', status: 'done' },
            { name: '水电点位图绘制', status: 'in_progress' },
            { name: '户型优化建议', status: 'pending' },
          ],
        },
      },
      {
        type: 'text', agent: 'design', timestamp: '2026-07-13T09:15:00',
        content: '📐 量房完成，实测 120.5㎡，与户型图一致。建议北卧改书房，主卫干湿分离，厨房动线 U 型布局更高效。',
      },
      {
        type: 'budget', agent: 'budget', timestamp: '2026-07-13T09:30:00',
        payload: { total: 60000, spent: 18500, remaining: 41500, note: '基础装修 ¥18,500 已支出（水电+瓦工材料），主材采购中' },
      },
      {
        type: 'quote', agent: 'procurement', timestamp: '2026-07-13T10:00:00',
        payload: {
          product: '客厅地砖 800×800 全瓷化',
          quotes: [
            { supplier: '东鹏', price: 85 },
            { supplier: '马可波罗', price: 92, recommended: true },
            { supplier: '诺贝尔', price: 110 },
          ],
          recommendation: '马可波罗（性价比 + 耐磨系数 PEI-4）',
        },
      },
      {
        type: 'bom', agent: 'procurement', timestamp: '2026-07-13T10:10:00',
        payload: {
          title: 'BOM 物料清单 · 主材采购',
          project_id: 'demo-owner-001',
          items: [
            { material: { name: '东鹏 800×800 全瓷化地砖', sku: 'DP-8008', category: { name: '瓷砖' }, unit: '㎡' }, quantity: 80, total_price: 7360 },
            { material: { name: '立邦净味全效乳胶漆', sku: 'NB-Q5L', category: { name: '涂料' }, unit: '桶' }, quantity: 6, total_price: 2880 },
            { material: { name: '圣象多层实木地板', sku: 'SX-ML12', category: { name: '地板' }, unit: '㎡' }, quantity: 45, total_price: 6750 },
            { material: { name: '九牧淋浴花洒套装', sku: 'JM-HS200', category: { name: '卫浴' }, unit: '套' }, quantity: 2, total_price: 3200 },
            { material: { name: '欧普LED筒灯 7W', sku: 'OP-TD7', category: { name: '灯具' }, unit: '个' }, quantity: 24, total_price: 1200 },
          ],
          total_price: 21390,
        },
      },
      {
        type: 'narrative', timestamp: '2026-07-13T10:05:00',
        payload: {
          variant: 'brand', tag: '品牌主张',
          title: '这就是 8 AI 团队 7×24 自主运转的样子',
          body: '量房、设计、预算、比价——全部自动完成。人类业主只需在关键节点审批，其余时间交给 AI。',
          agents: ['master', 'design', 'budget', 'procurement', 'construction', 'quality', 'settlement', 'support'],
        },
      },
      {
        type: 'task_card', agent: 'construction', timestamp: '2026-07-13T14:00:00',
        payload: {
          title: '本周施工计划',
          tasks: [
            { name: '水电开槽', status: 'done' },
            { name: '管线敷设', status: 'in_progress' },
            { name: '防水验收', status: 'pending' },
          ],
        },
      },
      {
        type: 'text', agent: 'quality', timestamp: '2026-07-13T16:30:00',
        content: '✅ 水电隐蔽工程验收通过。管线横平竖直，打压测试 0.8MPa 保压 30 分钟无渗漏，符合 GB 50242 标准。',
      },
      {
        type: 'payment', agent: 'settlement', timestamp: '2026-07-13T17:00:00',
        payload: {
          total_paid: 18000, total_amount: 60000,
          stages: [
            { stage_code: 'deposit', paid_amount: 18000, total_amount: 18000, status: 'paid' },
            { stage_code: 'progress', paid_amount: 0, total_amount: 18000, status: 'pending' },
            { stage_code: 'final', paid_amount: 0, total_amount: 18000, status: 'pending' },
            { stage_code: 'warranty', paid_amount: 0, total_amount: 6000, status: 'pending' },
          ],
        },
      },
      {
        type: 'approval', agent: 'master', timestamp: '2026-07-13T17:30:00',
        payload: {
          id: 'demo-approval-1', title: '主卧飘窗是否拆除？',
          problem: '飘窗为非承重结构，可拆除以增加 1.2㎡ 使用面积',
          impact_cost: 800, impact_days: 1,
          detail: '设计 Agent 建议拆除改为收纳柜；预算 Agent 已询价，拆除 + 修复 ¥800。',
          mention: '业主',
        },
      },
      {
        type: 'narrative', timestamp: '2026-07-13T17:35:00',
        payload: {
          variant: 'cta', tag: '继续体验',
          title: '人类仅在关键节点审批',
          body: '上面这条审批，就是业主每天唯一需要做的事。登录后，AI 团队开始服务你家的装修。',
          cta_text: '输入手机号，让 AI 团队开始服务', cta_action: 'lead',
        },
      },
    ],

    // ==================== 设计师剧本 ====================
    designer: [
      { type: 'system', content: '── 2026-07-13 · 新设计任务到达 ──' },
      {
        type: 'text', agent: 'master', timestamp: '2026-07-13T09:00:00',
        content: '阳光花园 3 栋 201 需要全屋设计方案，120.5㎡，业主要求北欧风。设计师你好，有 1 个任务待申领。',
        collaboration: [{ agent: 'design', action: '待申领' }],
      },
      {
        type: 'task_claim', agent: 'master', timestamp: '2026-07-13T09:05:00',
        payload: {
          title: '全屋设计方案', claim_role: 'designer',
          description: '120.5㎡ 三室两厅，北欧风，预算 ¥60,000 内，3 套方案比选',
          project_name: '阳光花园 3 栋 201',
          claim_deadline: '2026-07-14 18:00',
          candidates: [
            { user_id: 'u1', user_name: '你（李设计师）', composite_score: 92, rating_score: 4.8, score_breakdown: { points: 1580, experience_years: 6, completed_projects: 42 } },
            { user_id: 'u2', user_name: '王设计师', composite_score: 87, rating_score: 4.6, score_breakdown: { points: 1320, experience_years: 5, completed_projects: 35 } },
            { user_id: 'u3', user_name: '张设计师', composite_score: 81, rating_score: 4.5, score_breakdown: { points: 980, experience_years: 3, completed_projects: 18 } },
          ],
        },
      },
      {
        type: 'text', agent: 'design', timestamp: '2026-07-13T09:10:00',
        content: '📐 已申领任务。AI 辅助分析户型：北卧采光不足建议改书房，主卫可做干湿分离，厨房 U 型布局高效。3 套方案生成中…',
      },
      {
        type: 'document', agent: 'design', timestamp: '2026-07-13T09:40:00',
        payload: { name: '效果图方案 A · 北欧极简.pdf', size: '8.2 MB', url: '#' },
      },
      {
        type: 'budget', agent: 'budget', timestamp: '2026-07-13T09:45:00',
        payload: { total: 58000, spent: 0, remaining: 58000, note: '方案 A 预算估算：主材 ¥32,000 + 辅材 ¥12,000 + 人工 ¥14,000' },
      },
      {
        type: 'narrative', timestamp: '2026-07-13T09:50:00',
        payload: {
          variant: 'brand', tag: '设计师视角',
          title: 'AI 设计 Agent 是你的超级助手',
          body: '从量房复核到效果图生成，从预算估算到施工图深化——AI 协助你完成 80% 重复工作，你专注创意。',
          agents: ['design', 'budget', 'quality'],
        },
      },
      {
        type: 'text', agent: 'master', timestamp: '2026-07-13T14:00:00',
        content: '业主反馈：方案 A 通过，请深化施工图。',
      },
      {
        type: 'text', agent: 'design', timestamp: '2026-07-13T16:00:00',
        content: '📐 施工图已出（含水电点位图 + 家具布置图 + 灯光方案），已 @施工 Agent 准备开工。',
        collaboration: [{ agent: 'construction', action: '准备开工' }],
      },
      {
        type: 'text', agent: 'quality', timestamp: '2026-07-13T16:30:00',
        content: '✅ 设计图纸复核通过。水电点位无冲突，承重墙标注正确，符合规范。',
      },
      {
        type: 'milestone_settlement', agent: 'settlement', timestamp: '2026-07-13T17:00:00',
        payload: {
          milestone_name: '设计阶段结算', contract_amount: 6000, payment_ratio: 1,
          base_payable: 6000, total_payable: 6000, description: '设计费全款，已扣除平台服务费 5%',
        },
      },
      {
        type: 'narrative', timestamp: '2026-07-13T17:05:00',
        payload: {
          variant: 'cta', tag: '继续体验',
          title: '30 分钟出 3 套方案，6 年经验变 6 天产能',
          body: '登录后，AI 设计 Agent 协助你量房、出图、算预算，接更多项目，赚更多积分。',
          cta_text: '登录接单，让 AI 帮你出图', cta_action: 'lead',
        },
      },
    ],

    // ==================== 供应商剧本 ====================
    supplier: [
      { type: 'system', content: '── 2026-07-13 · 新采购询价到达 ──' },
      {
        type: 'text', agent: 'master', timestamp: '2026-07-13T09:00:00',
        content: '阳光花园项目需要客厅地砖 80㎡，已 @采购 Agent 向 3 家供应商询价。',
        collaboration: [{ agent: 'procurement', action: '询价中' }],
      },
      {
        type: 'text', agent: 'procurement', timestamp: '2026-07-13T09:10:00',
        content: '🛒 已向 3 家供应商询价。你发布的产品"东鹏 800×800 全瓷化地砖"在询价列表中，报价 ¥85/㎡。',
      },
      {
        type: 'product_card', agent: 'procurement', timestamp: '2026-07-13T09:15:00',
        payload: {
          name: '东鹏 800×800 全瓷化地砖', category: '瓷砖/地砖',
          price_range: '¥85/㎡', description: '全瓷化 PEI-4 耐磨，防滑 R10，适用于客厅/卧室',
          tags: ['北欧风', '耐磨', '防滑', '现货'],
          supplier_name: '你的店铺',
        },
      },
      {
        type: 'quote', agent: 'procurement', timestamp: '2026-07-13T09:30:00',
        payload: {
          product: '客厅地砖 800×800 全瓷化 80㎡',
          quotes: [
            { supplier: '东鹏（你）', price: 85, recommended: true },
            { supplier: '马可波罗', price: 92 },
            { supplier: '诺贝尔', price: 110 },
          ],
          recommendation: '东鹏（性价比最高 + 现货 + 担保支付）',
        },
      },
      {
        type: 'narrative', timestamp: '2026-07-13T09:35:00',
        payload: {
          variant: 'brand', tag: '供应商视角',
          title: 'AI 采购 Agent 让订单自动找你',
          body: '发布产品后，AI 自动匹配业主需求，自动比价，自动下单。担保支付 + 物流追踪，全流程透明。',
          agents: ['procurement', 'settlement'],
        },
      },
      {
        type: 'text', agent: 'procurement', timestamp: '2026-07-13T10:00:00',
        content: '恭喜！你的报价被选中。请确认供货能力与交期，系统将生成正式订单。',
      },
      {
        type: 'procurement_order', agent: 'procurement', timestamp: '2026-07-13T10:30:00',
        payload: {
          id: 'po-abc12345', supplier_name: '你的店铺',
          lines: [{ material_name: '东鹏 800×800 全瓷化地砖', quantity: 80, total_price: 6800 }],
          total_amount: 6800, status: 'confirmed', note: '请在 3 天内发货',
        },
      },
      {
        type: 'escrow', agent: 'procurement', timestamp: '2026-07-13T11:00:00',
        payload: { escrow_no: 'ESC-2026-001', total_amount: 6800, escrow_fee: 68, status: 'buyer_paid' },
      },
      {
        type: 'logistics', agent: 'procurement', timestamp: '2026-07-13T14:00:00',
        payload: {
          tracking_no: 'SF1234567890', carrier: 'sf_express', status: 'in_transit',
          ship_from: '佛山仓储中心', ship_to: '上海阳光花园',
          tracking_history: [
            { location: '佛山', description: '已发货' },
            { location: '上海中转站', description: '运输中' },
          ],
        },
      },
      {
        type: 'text', agent: 'procurement', timestamp: '2026-07-15T10:00:00',
        content: '✅ 货已签收，担保支付已释放 ¥6,800 到你账户。本次交易完成，积分 +68。',
      },
      {
        type: 'narrative', timestamp: '2026-07-15T10:05:00',
        payload: {
          variant: 'cta', tag: '继续体验',
          title: '发布一次产品，订单持续找你',
          body: '登录后管理你的产品库，AI 采购 Agent 自动匹配业主需求，担保支付保障回款。',
          cta_text: '登录管理产品与订单', cta_action: 'lead',
        },
      },
    ],

    // ==================== 工长剧本 ====================
    foreman: [
      { type: 'system', content: '── 2026-07-13 · 水电阶段开工 ──' },
      {
        type: 'text', agent: 'master', timestamp: '2026-07-13T09:00:00',
        content: '阳光花园项目水电阶段开工，已 @施工 Agent 分配任务给你。',
        collaboration: [{ agent: 'construction', action: '开工' }],
      },
      {
        type: 'task_card', agent: 'construction', timestamp: '2026-07-13T09:05:00',
        payload: {
          title: '本周施工任务 · 水电阶段',
          tasks: [
            { name: '水电开槽 120㎡', status: 'done' },
            { name: '管线敷设', status: 'in_progress' },
            { name: '防水验收', status: 'pending' },
          ],
        },
      },
      {
        type: 'text', agent: 'construction', timestamp: '2026-07-13T12:00:00',
        content: '🔨 水电开槽完成。请上传现场照片，质检 Agent 将自动验收。',
      },
      {
        type: 'photo', agent: 'construction', timestamp: '2026-07-13T12:10:00', is_self: true,
        payload: {
          note: '客厅开槽完成，管线横平竖直',
          photos: [
            { url: 'assets/images/wallpaper/IMG_2640.webp', caption: '客厅开槽' },
            { url: 'assets/images/wallpaper/IMG_2641.webp', caption: '卧室开槽' },
            { url: 'assets/images/wallpaper/IMG_2642.webp', caption: '厨房开槽' },
          ],
        },
      },
      {
        type: 'text', agent: 'quality', timestamp: '2026-07-13T14:00:00',
        content: '✅ 水电隐蔽工程验收通过。管线横平竖直，打压测试 0.8MPa 保压 30 分钟无渗漏，符合 GB 50242 标准。可继续管线敷设。',
      },
      {
        type: 'narrative', timestamp: '2026-07-13T14:10:00',
        payload: {
          variant: 'brand', tag: '工长视角',
          title: 'AI 施工+质检 Agent 是你的工地管家',
          body: '工序排期、现场拍照、隐蔽工程验收、进度款结算——AI 协助你管理工地每个环节，不漏项不返工。',
          agents: ['construction', 'quality', 'settlement'],
        },
      },
      {
        type: 'text', agent: 'construction', timestamp: '2026-07-14T16:00:00',
        content: '管线敷设完成，进度 80%。防水施工中，预计明日可预约验收。',
      },
      {
        type: 'approval', agent: 'master', timestamp: '2026-07-15T09:00:00',
        payload: {
          id: 'demo-approval-foreman-1', title: '防水验收预约确认',
          problem: '卫生间防水已完成，需业主到场验收',
          impact_days: 0,
          detail: '施工 Agent 建议预约周三下午 14:00 验收，业主需确认时间。质检 Agent 将同步到场。',
          mention: '业主',
        },
      },
      {
        type: 'text', agent: 'quality', timestamp: '2026-07-15T14:30:00',
        content: '✅ 防水验收通过。闭水试验 48 小时无渗漏，符合规范。可进入瓦工阶段。',
      },
      {
        type: 'payment', agent: 'settlement', timestamp: '2026-07-15T17:00:00',
        payload: {
          total_paid: 18000, total_amount: 60000,
          stages: [
            { stage_code: 'deposit', paid_amount: 18000, total_amount: 18000, status: 'paid' },
            { stage_code: 'progress', paid_amount: 0, total_amount: 18000, status: 'pending' },
            { stage_code: 'final', paid_amount: 0, total_amount: 18000, status: 'pending' },
            { stage_code: 'warranty', paid_amount: 0, total_amount: 6000, status: 'pending' },
          ],
        },
      },
      {
        type: 'narrative', timestamp: '2026-07-15T17:05:00',
        payload: {
          variant: 'cta', tag: '继续体验',
          title: 'AI 帮你排工序、管验收、对回款',
          body: '登录后接更多项目，AI 施工 Agent 帮你排期，质检 Agent 帮你验收，结算 Agent 帮你对账回款。',
          cta_text: '登录接单，让 AI 帮你管工地', cta_action: 'lead',
        },
      },
    ],
  },

  // ── 角色定制演示回复 ──
  demoReplies: {
    owner: {
      budget: { type: 'text', agent: 'budget', content: '演示回复：120㎡ 家装预算建议预留 ¥500-800/㎡，即 ¥60,000-96,000（含主材+辅材+人工）。登录后我可基于真实建材库给你精确到每一项的报价 →' },
      design: { type: 'text', agent: 'design', content: '演示回复：北欧、日式、新中式是当下主流风格。登录后上传户型图，我 30 分钟内出三套效果图方案，含家具布置+灯光设计 →' },
      construction: { type: 'text', agent: 'construction', content: '演示回复：120㎡ 标准工期 60-75 天。水电 7 天、瓦工 15 天、木工 10 天、油漆 7 天、安装 5 天。登录后可看每日施工播报 + 现场照片 →' },
      procurement: { type: 'text', agent: 'procurement', content: '演示回复：主材采购建议提前 20 天下单，避免工期等待。登录后采购 Agent 自动比价 3 家以上供应商，含物流追踪 + 担保支付 →' },
      quality: { type: 'text', agent: 'quality', content: '演示回复：水电验收重点查管线横平竖直、打压测试 30 分钟无渗漏。登录后质检 Agent 每个节点自动验收，偏差超 3cm 自动预警 →' },
      settlement: { type: 'text', agent: 'settlement', content: '演示回复：装修结算建议分 4 期：首付 30%、水电完工 30%、木工完工 20%、尾款 20%。登录后结算 Agent 自动对账 + 异常扣款建议 →' },
      master: { type: 'text', agent: 'master', content: '演示回复：我是总控 Agent，统筹 8 个 AI 协作。试试问"预算""设计""施工""采购"——每个 Agent 都会给你专业回复 →' },
    },
    designer: {
      budget: { type: 'text', agent: 'budget', content: '演示回复：设计方案预算估算是你的加分项。登录后 AI 协助你实时算价，方案报价更精准，业主通过率更高 →' },
      design: { type: 'text', agent: 'design', content: '演示回复：登录后 AI 协助你量房、出效果图、算预算，30 分钟交付 3 套方案。你的经验 + AI 效率 = 更多接单 →' },
      construction: { type: 'text', agent: 'construction', content: '演示回复：施工图深化后，施工 Agent 自动接收。登录后你可追踪施工进度，确保设计落地不变形 →' },
      procurement: { type: 'text', agent: 'procurement', content: '演示回复：设计方案中的主材，采购 Agent 自动询价 3 家供应商。登录后你的方案直接关联真实建材库与实时报价 →' },
      quality: { type: 'text', agent: 'quality', content: '演示回复：质检 Agent 复核你的设计图纸，水电点位无冲突才允许施工。登录后图纸一次过审，减少返工 →' },
      settlement: { type: 'text', agent: 'settlement', content: '演示回复：设计费结算分阶段：方案通过 50% + 施工图交付 50%。登录后结算 Agent 自动对账，积分即时到账 →' },
      master: { type: 'text', agent: 'master', content: '演示回复：我是总控 Agent，会自动派设计任务给你。试试问"设计""预算""采购"了解 AI 如何协助你 →' },
    },
    supplier: {
      budget: { type: 'text', agent: 'budget', content: '演示回复：供应商关注的是回款。登录后担保支付保障你的货款，签收即释放，不拖欠 →' },
      design: { type: 'text', agent: 'design', content: '演示回复：设计 Agent 选材时会优先匹配你的产品库。登录后完善产品标签，提高被选率 →' },
      construction: { type: 'text', agent: 'construction', content: '演示回复：施工进度影响你的发货时机。登录后施工 Agent 自动通知你备货与发货节点 →' },
      procurement: { type: 'text', agent: 'procurement', content: '演示回复：登录后发布产品，AI 采购 Agent 自动匹配业主需求。订单自动找你，含比价+下单+物流+担保支付全流程 →' },
      quality: { type: 'text', agent: 'quality', content: '演示回复：质检 Agent 验收你的材料。登录后产品质量达标自动通过，减少退换货纠纷 →' },
      settlement: { type: 'text', agent: 'settlement', content: '演示回复：担保支付状态机：买家付款→你发货→签收释放。登录后结算 Agent 自动对账，货款 T+0 到账 →' },
      master: { type: 'text', agent: 'master', content: '演示回复：我是总控 Agent，会自动把采购需求匹配给你。试试问"采购""结算"了解订单流程 →' },
    },
    foreman: {
      budget: { type: 'text', agent: 'budget', content: '演示回复：工长关注进度款回款。登录后每阶段验收通过，结算 Agent 自动触发业主付款，不催款不拖欠 →' },
      design: { type: 'text', agent: 'design', content: '演示回复：施工图由设计 Agent 出具，你按图施工。登录后图纸在线查看，疑问可 @设计 Agent 实时沟通 →' },
      construction: { type: 'text', agent: 'construction', content: '演示回复：登录后 AI 施工 Agent 帮你排工序、分配工人、追踪进度。每日拍照播报，业主远程可视 →' },
      procurement: { type: 'text', agent: 'procurement', content: '演示回复：主材到货时间影响你的施工排期。登录后采购 Agent 自动同步物流状态，材料到了再排工 →' },
      quality: { type: 'text', agent: 'quality', content: '演示回复：登录后质检 Agent 每个节点自动验收，偏差超 3cm 预警。验收通过才进入下一道工序，不返工 →' },
      settlement: { type: 'text', agent: 'settlement', content: '演示回复：进度款分 4 期：首付 30%+水电 30%+木工 20%+尾款 20%。登录后结算 Agent 自动对账，进度款即时到账 →' },
      master: { type: 'text', agent: 'master', content: '演示回复：我是总控 Agent，会自动派施工任务给你。试试问"施工""质检""结算"了解 AI 如何协助你 →' },
    },
  },

  // ── 首屏消息数（性能优先：控制 LCP） ──
  firstScreenCount: 6,
  // ── 自动播放间隔（ms） ──
  playInterval: 1500,

  // ── 平台实时数据卡片（动态生成，增强信任） ──
  _getPlatformStats() {
    // 基于当前时间生成稳定的今日数据(每小时波动一次)
    const hour = new Date().getHours();
    const seed = new Date().getDate() * 24 + hour;
    const rand = (min, max) => Math.floor(min + (seed * 7 + min * 13) % (max - min));
    return {
      type: 'narrative', timestamp: new Date().toISOString(),
      payload: {
        variant: 'stat', tag: '平台实时数据', display_name: '🏠 索克家居',
        title: '今日平台动态',
        stat_value: `${rand(28, 56)} 个项目开工`,
        stat_label: `${rand(180, 320)} 个 AI 任务自动完成 · 节省 ¥${rand(8, 15)}万`,
        body: '8 个 AI 智能体 7×24 自治运营，量房/设计/预算/比价/施工/质检/结算/客服全链路自动化。人类仅在关键节点审批。',
      },
    };
  },

  // ── 播放状态 ──
  state: { currentIndex: 0, isPlaying: false, hasPaused: false, timer: null, role: 'owner' },

  // ── DOM 引用 ──
  dom: { list: null, controls: null, playBtn: null, replayBtn: null, skipBtn: null, input: null, sendBtn: null, chips: null, leadDialog: null, titleEl: null, subtitleEl: null },

  // ── 初始化 ──
  init() {
    this.dom.list = document.getElementById('demo-message-list');
    this.dom.controls = document.getElementById('demo-controls');
    this.dom.playBtn = document.getElementById('demo-play-btn');
    this.dom.replayBtn = document.getElementById('demo-replay-btn');
    this.dom.skipBtn = document.getElementById('demo-skip-btn');
    this.dom.input = document.getElementById('demo-chat-input');
    this.dom.sendBtn = document.getElementById('demo-send-btn');
    this.dom.chips = document.getElementById('demo-quick-chips');
    this.dom.leadDialog = document.getElementById('lead-dialog');
    this.dom.titleEl = document.getElementById('chat-title');
    this.dom.subtitleEl = document.getElementById('chat-subtitle');

    if (!this.dom.list) return;

    // 解析角色参数
    const params = new URLSearchParams(window.location.search);
    this.state.role = params.get('role') || 'owner';
    if (!this.roles[this.state.role]) this.state.role = 'owner';

    // 应用角色配置到 UI
    this._applyRoleConfig(this.state.role);

    this._bindEvents();
    this._startPlaceholderRotation();

    // 尊重 prefers-reduced-motion
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion) {
      this._showControls();
      this._renderDateSeparator(this.roles[this.state.role].dateLabel);
      this._appendMessage(this._getScript()[0]);
      this.state.currentIndex = 1;
    } else {
      setTimeout(() => this.play(), 800);
    }
  },

  // ── 应用角色配置到 UI ──
  _applyRoleConfig(role) {
    const cfg = this.roles[role];
    if (!cfg) return;
    if (this.dom.titleEl) this.dom.titleEl.textContent = cfg.title;
    if (this.dom.subtitleEl) this.dom.subtitleEl.textContent = cfg.subtitle;
    if (this.dom.input) this.dom.input.placeholder = cfg.inputPlaceholder;
    // 更新快捷问题
    this._updateQuickChips(role);
  },

  // ── 更新快捷问题 ──
  _updateQuickChips(role) {
    if (!this.dom.chips) return;
    const chipsMap = {
      owner: [
        '我家 120㎡ 要多少钱？', '看看设计效果图', '施工进度怎样？', '采购怎么比价？',
      ],
      designer: [
        '怎么接设计任务？', 'AI 怎么帮我出图？', '设计费怎么算？', '图纸怎么过审？',
      ],
      supplier: [
        '怎么接到订单？', '担保支付怎么用？', '产品怎么发布？', '货款多久到账？',
      ],
      foreman: [
        '怎么接施工任务？', '质检怎么验收？', '进度款怎么结？', '现场照片怎么传？',
      ],
    };
    const chips = chipsMap[role] || chipsMap.owner;
    this.dom.chips.innerHTML = chips.map(q =>
      `<button class="quick-chip" data-question="${this._escapeAttr(q)}" type="button">${this._escape(q)}</button>`
    ).join('');
  },

  // ── 获取当前剧本（注入平台实时数据卡到 system 消息之后） ──
  _getScript() {
    const base = this.scripts[this.state.role] || this.scripts.owner;
    if (!this._scriptCache || this._scriptCacheRole !== this.state.role) {
      const stats = this._getPlatformStats();
      const result = base.slice(0, 1)
        .concat([stats])
        .concat(base.slice(1));
      this._scriptCache = result;
      this._scriptCacheRole = this.state.role;
    }
    return this._scriptCache;
  },

  // ── 播放控制 ──
  play() {
    if (this.state.isPlaying) return;
    if (this.state.currentIndex >= this._getScript().length) { this._onPlaybackEnd(); return; }
    this.state.isPlaying = true;
    this._updatePlayBtn('pause');
    this._playNext();
  },
  pause() {
    this.state.isPlaying = false;
    if (this.state.timer) { clearTimeout(this.state.timer); this.state.timer = null; }
    if (this._typewriterTimer) { clearTimeout(this._typewriterTimer); this._typewriterTimer = null; }
    this._updatePlayBtn('play');
  },
  replay() {
    this.pause();
    this.state.currentIndex = 0;
    this.state.hasPaused = false;
    this.dom.list.innerHTML = '';
    this.play();
  },
  skip() {
    this.pause();
    while (this.state.currentIndex < this._getScript().length) {
      this._appendMessage(this._getScript()[this.state.currentIndex]);
      this.state.currentIndex++;
    }
    this._onPlaybackEnd();
  },
  _playNext() {
    if (!this.state.isPlaying) return;
    const script = this._getScript();
    if (this.state.currentIndex >= script.length) { this._onPlaybackEnd(); return; }

    const msg = script[this.state.currentIndex];
    if (msg.type === 'system' && this.state.currentIndex === 0) {
      this._renderDateSeparator(this.roles[this.state.role].dateLabel);
    }
    this._appendMessage(msg);
    this.state.currentIndex++;

    if (this.state.currentIndex === this.firstScreenCount && !this.state.hasPaused) {
      this.state.hasPaused = true;
      this.pause();
      this._showControls();
      this._showQuickChips();
      return;
    }
    this.state.timer = setTimeout(() => this._playNext(), this.playInterval);
  },
  _onPlaybackEnd() {
    this.state.isPlaying = false;
    this._updatePlayBtn('done');
    this._showControls();
    this._showQuickChips();
  },

  // ── 消息渲染 ──
  _appendMessage(msg) {
    const html = MessageRenderers.render(msg, this.state.role);
    if (!html) return;
    this.dom.list.insertAdjacentHTML('beforeend', html);
    this._scrollToBottom();
  },
  _renderDateSeparator(label) {
    const sep = document.createElement('div');
    sep.className = 'date-separator';
    sep.innerHTML = `<span>${label}</span>`;
    this.dom.list.appendChild(sep);
  },
  _scrollToBottom() {
    this.dom.list.scrollTop = this.dom.list.scrollHeight;
  },

  // ── 控制条 ──
  _showControls() {
    if (this.dom.controls) {
      this.dom.controls.classList.add('visible');
      this.dom.controls.setAttribute('aria-hidden', 'false');
    }
  },
  _updatePlayBtn(state) {
    if (!this.dom.playBtn) return;
    const icons = { play: '▶', pause: '⏸', done: '✓' };
    const labels = { play: '继续播放', pause: '暂停', done: '播放完毕' };
    this.dom.playBtn.textContent = icons[state] || '▶';
    this.dom.playBtn.setAttribute('aria-label', labels[state] || '播放');
  },
  _showQuickChips() {
    if (this.dom.chips && !this.dom.chips.classList.contains('visible')) {
      this.dom.chips.classList.add('visible');
    }
  },

  // ── placeholder 轮播 ──
  _startPlaceholderRotation() {
    if (!this.dom.input) return;
    const rolePlaceholders = {
      owner: ['试试问：我家 120㎡ 要多少钱？', '试试问：看看设计效果图', '试试问：施工进度怎样？', '试试问：采购怎么比价？'],
      designer: ['试试问：怎么接设计任务？', '试试问：AI 怎么帮我出图？', '试试问：设计费怎么算？'],
      supplier: ['试试问：怎么接到订单？', '试试问：担保支付怎么用？', '试试问：货款多久到账？'],
      foreman: ['试试问：怎么接施工任务？', '试试问：质检怎么验收？', '试试问：进度款怎么结？'],
    };
    const placeholders = rolePlaceholders[this.state.role] || rolePlaceholders.owner;
    let idx = 0;
    setInterval(() => {
      if (document.activeElement === this.dom.input) return;
      idx = (idx + 1) % placeholders.length;
      this.dom.input.placeholder = placeholders[idx];
    }, 3500);
  },

  // ── 访客交互：演示回复（打字机效果） ──
  handleUserInput(text) {
    if (!text || !text.trim()) return;
    const trimmed = text.trim();
    this._appendMessage({ type: 'text', is_self: true, timestamp: new Date().toISOString(), content: trimmed });

    const route = AgentRouter.route(trimmed);
    const reply = this._getDemoReply(route.agent, trimmed);

    // 尊重 prefers-reduced-motion：跳过打字机效果
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduceMotion || reply.type !== 'text') {
      setTimeout(() => { this._appendMessage(reply); }, 600);
      return;
    }

    // 打字机效果：先显示输入指示器，再逐字显示
    setTimeout(() => { this._typewriterRender(reply); }, 600);
  },
  _typewriterRender(msg) {
    const html = MessageRenderers.render(msg, this.state.role);
    if (!html) return;

    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    const msgEl = wrapper.firstElementChild;
    if (!msgEl) {
      this.dom.list.insertAdjacentHTML('beforeend', html);
      this._scrollToBottom();
      return;
    }

    const bubble = msgEl.querySelector('.msg-bubble');
    if (!bubble) {
      this.dom.list.appendChild(msgEl);
      this._scrollToBottom();
      return;
    }

    const fullText = bubble.textContent;
    bubble.textContent = '';
    bubble.classList.add('typing');
    this.dom.list.appendChild(msgEl);
    this._scrollToBottom();

    // 输入指示器停留 400ms，然后逐字显示
    let i = 0;
    const speed = 25;
    const typeNext = () => {
      if (i < fullText.length) {
        bubble.textContent = fullText.slice(0, i + 1);
        i++;
        this._scrollToBottom();
        this._typewriterTimer = setTimeout(typeNext, speed);
      } else {
        bubble.classList.remove('typing');
      }
    };
    this._typewriterTimer = setTimeout(typeNext, 400);
  },
  _getDemoReply(agent) {
    const roleReplies = this.demoReplies[this.state.role] || this.demoReplies.owner;
    let reply = roleReplies[agent] || roleReplies.master;
    reply = Object.assign({}, reply, { timestamp: new Date().toISOString() });
    return reply;
  },

  // ── 留资弹窗 ──
  openLeadDialog() {
    if (this.dom.leadDialog) {
      this.dom.leadDialog.classList.add('open');
      this.dom.leadDialog.setAttribute('aria-hidden', 'false');
      const phoneInput = this.dom.leadDialog.querySelector('#lead-phone');
      if (phoneInput) setTimeout(() => phoneInput.focus(), 100);
    }
  },
  closeLeadDialog() {
    if (this.dom.leadDialog) {
      this.dom.leadDialog.classList.remove('open');
      this.dom.leadDialog.setAttribute('aria-hidden', 'true');
    }
  },
  submitLead(phone) {
    this.closeLeadDialog();
    window.location.href = `login.html?role=${encodeURIComponent(this.state.role)}&phone=${encodeURIComponent(phone)}`;
  },

  // ── 事件绑定 ──
  _bindEvents() {
    if (this.dom.playBtn) {
      this.dom.playBtn.addEventListener('click', () => {
        if (this.state.isPlaying) this.pause();
        else if (this.state.currentIndex >= this._getScript().length) this.replay();
        else this.play();
      });
    }
    if (this.dom.replayBtn) this.dom.replayBtn.addEventListener('click', () => this.replay());
    if (this.dom.skipBtn) this.dom.skipBtn.addEventListener('click', () => this.skip());

    if (this.dom.input) {
      this.dom.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this._sendInput(); }
      });
    }
    if (this.dom.sendBtn) this.dom.sendBtn.addEventListener('click', () => this._sendInput());

    if (this.dom.chips) {
      this.dom.chips.addEventListener('click', (e) => {
        const chip = e.target.closest('.quick-chip');
        if (chip) {
          const text = chip.dataset.question;
          if (text && this.dom.input) { this.dom.input.value = text; this._sendInput(); }
        }
      });
    }

    // 营销 CTA（事件委托）
    document.addEventListener('click', (e) => {
      const cta = e.target.closest('[data-narrative-cta]');
      if (cta) {
        const action = cta.dataset.narrativeCta;
        if (action === 'lead') this.openLeadDialog();
        else if (action === 'login') window.location.href = `login.html?role=${encodeURIComponent(this.state.role)}`;
      }
    });

    // 留资弹窗
    if (this.dom.leadDialog) {
      const closeBtn = this.dom.leadDialog.querySelector('#lead-close');
      const form = this.dom.leadDialog.querySelector('#lead-form');
      if (closeBtn) closeBtn.addEventListener('click', () => this.closeLeadDialog());
      this.dom.leadDialog.addEventListener('click', (e) => {
        if (e.target === this.dom.leadDialog) this.closeLeadDialog();
      });
      if (form) {
        form.addEventListener('submit', (e) => {
          e.preventDefault();
          const phone = form.querySelector('#lead-phone').value.trim();
          if (/^1\d{10}$/.test(phone)) this.submitLead(phone);
          else {
            const err = form.querySelector('#lead-error');
            if (err) { err.textContent = '请输入正确的 11 位手机号'; err.hidden = false; }
          }
        });
      }
    }

    // ESC 关闭弹窗
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.dom.leadDialog && this.dom.leadDialog.classList.contains('open')) this.closeLeadDialog();
    });
  },
  _sendInput() {
    if (!this.dom.input) return;
    const text = this.dom.input.value.trim();
    if (!text) return;
    this.dom.input.value = '';
    this.handleUserInput(text);
  },

  // ── 工具 ──
  _escape(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  },
  _escapeAttr(s) { return this._escape(s); },
};

window.DemoNarrative = DemoNarrative;
