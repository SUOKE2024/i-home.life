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
    {
      agent: 'ar_measurement',
      label: '📏 AR 测量',
      keywords: ['AR', 'AR测量', '测量', '扫描', '量房', '激光', 'LiDAR', 'RoomPlan',
                 '测距', '丈量', '拍照测量', '三维扫描', '空间测量',
                 '面积测算', '户型测绘', '空间扫描', '距离测量', '3D扫描'],
    },
    {
      agent: 'floorplans',
      label: '📋 户型管理',
      keywords: ['户型', '平面图', '户型方案', '户型图', '户型管理', '我的户型', '保存户型', '楼层平面'],
    },
    {
      agent: 'structural',
      label: '🏗️ 土建结构',
      keywords: ['结构', '梁', '柱', '承重', '框架', '地基', '剪力墙', '楼板', '钢筋', '混凝土'],
    },
    {
      agent: 'lighting',
      label: '💡 灯光设计',
      keywords: ['灯光', '照明', '照度', '色温', '灯具', '射灯', '筒灯', '轨道灯', '氛围灯', '灯带'],
    },
    {
      agent: 'smart_home',
      label: '🤖 智能家居',
      keywords: ['智能家居', '智能', '自动化', '传感器', '窗帘电机', '智能灯', 'Matter', 'Zigbee', '智能开关', '智能插座', '温控', '门锁'],
    },
    {
      agent: 'scene_automation',
      label: '🔄 场景自动化',
      keywords: ['场景联动', '场景', '情景', '离家', '回家', '睡眠', '会客', '一键', '触发', '条件'],
    },
    {
      agent: 'custom_furniture',
      label: '🪚 定制家具',
      keywords: ['定制', '定做', '柜子', '衣柜', '橱柜', '书柜', '板材', '板材计算', '展开面积', '投影面积'],
    },
    {
      agent: 'tasks',
      label: '📝 任务协调',
      keywords: ['任务', '待办', '交办', '分派', '安排', '谁来做', '施工任务', '任务列表', '安排任务'],
    },
    {
      agent: 'change_orders',
      label: '📋 变更管理',
      keywords: ['变更', '改方案', '改设计', '变更单', '设计变更', '工程变更', '修改方案', '方案变更'],
    },
    {
      agent: 'crews',
      label: '👷 工程队',
      keywords: ['工程队', '班组', '施工队', '外包', '哪个队', '派工', '工队', '施工班组', '装修队'],
    },
    {
      agent: 'vr_panorama',
      label: '🥽 VR全景',
      keywords: ['VR', '全景', '虚拟', '360', '漫游', '沉浸', 'VR全景', '360度', '虚拟现实'],
    },
    {
      agent: 'ai_render',
      label: '🎨 AI渲染',
      keywords: ['渲染', '效果图', '出图', '配色', '色调', '3D渲染', '2D渲染', '渲染图', '风格迁移'],
    },
    {
      agent: 'sketch_to_3d',
      label: '✏️ 草图转3D',
      keywords: ['草图', '手绘', '转3D', '画图', '涂鸦', '手绘转', '草图转', '随手画'],
    },
    {
      agent: 'soft_furnishing',
      label: '🛋️ 软装设计',
      keywords: ['软装', '窗帘', '地毯', '抱枕', '装饰画', '挂画', '软装配饰', '布艺', '饰品', '摆件'],
    },
    {
      agent: 'hard_decoration',
      label: '🧱 硬装设计',
      keywords: ['硬装', '吊顶', '墙面装饰', '背景墙', '地面', '涂料', '墙纸', '石材', '大理石'],
    },
    {
      agent: 'takeoff',
      label: '📊 工程量计算',
      keywords: ['工程量', '算量', '材料清单', '用量计算', '工程量清单', '材料用量', '辅料计算', '清单计算'],
    },
    {
      agent: 'points',
      label: '⭐ 积分商城',
      keywords: ['积分', '会员', '等级', '兑换', '奖励', '累计', '积分商城', '积分兑换', '成长值', '权益'],
    },
    {
      agent: 'cad_import',
      label: '📐 CAD导入',
      keywords: ['CAD导入', '导入CAD', 'DXF', 'DWG', 'CAD文件', '导入图纸', '上传CAD', 'CAD图纸'],
    },
    {
      agent: 'kitchen',
      label: '🍳 厨房',
      keywords: ['厨房', '厨房设计', '橱柜', '三件套', '油烟机', '灶具', '操作台', '厨房动线', '黄金三角', '厨房水电', '厨房布局', '岛台', '中岛'],
    },
    {
      agent: 'bathroom',
      label: '🛁 卫浴',
      keywords: ['卫生间', '浴室', '卫浴', '马桶', '淋浴', '花洒', '浴缸', '干湿分离', '三分离', '浴室柜', '台盆', '地漏', '坡度'],
    },
    {
      agent: 'mep',
      label: '🔧 水电暖通',
      keywords: ['水电点位', '暖通', '空调', '新风', '地暖', '暖气', 'MEP', '强弱电', '配电箱', '插座布置', '开关布置', '给排水', '管道', '冷热水'],
    },
    {
      agent: 'appliance',
      label: '📺 家电',
      keywords: ['家电', '电器', '冰箱', '洗衣机', '洗碗机', '烘干机', '微波炉', '烤箱', '蒸箱', '净水器', '垃圾处理器', '家电尺寸', '嵌入家电', '家电预留'],
    },
    {
      agent: 'furniture_catalog',
      label: '🪑 家具',
      keywords: ['家具', '沙发', '餐桌', '床', '椅子', '茶几', '电视柜', '书桌', '衣柜', '鞋柜', '家具尺寸', '家具品牌', '家具风格', '家具列表'],
    },
    {
      agent: 'door_window_waterproof',
      label: '🚪 门窗防水',
      keywords: ['门窗', '窗户', '入户门', '室内门', '推拉门', '平开门', '封阳台', '断桥铝', '门窗尺寸', '防水', '防水涂料', '防水层', '闭水试验', '渗水'],
    },
    {
      agent: 'files',
      label: '📁 文件',
      keywords: ['文件', '上传', '下载', '附件', '合同', '照片', '证件', '文档管理', '文件管理', '图纸', '合同管理'],
    },
    {
      agent: 'products',
      label: '🏷️ 产品',
      keywords: ['产品', '商品', '材料价格', '产品目录', '产品上架', '产品管理', '产品列表', 'SKU', '产品信息', '规格参数'],
    },
    {
      agent: 'identity',
      label: '🆔 身份认证',
      keywords: ['实名', '认证', '身份', '身份证', '实名认证', '身份认证', '认证状态', '审核'],
    },
    {
      agent: 'voice',
      label: '🎙️ 语音',
      keywords: ['语音', '说话', '语音输入', '语音助手', '语音对话', '语音控制', '语音指令'],
    },
    {
      agent: 'notifications',
      label: '🔔 通知',
      keywords: ['通知', '消息', '推送', '提醒', '手机通知', '消息提醒', '通知设置'],
    },
    {
      agent: 'ifc_export',
      label: '🏗️ BIM导出',
      keywords: ['BIM', 'IFC', '导出BIM', 'BIM模型', 'IFC文件', '结构模型', '建筑模型', 'BIM导出', '模型导出'],
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
      master:                 { name: '总控',       emoji: '🏠', color: 'var(--agent-master)' },
      design:                 { name: '设计',       emoji: '📐', color: 'var(--agent-design)' },
      budget:                 { name: '预算',       emoji: '💰', color: 'var(--agent-budget)' },
      procurement:            { name: '采购',       emoji: '🛒', color: 'var(--agent-procurement)' },
      construction:           { name: '施工',       emoji: '🔨', color: 'var(--agent-construction)' },
      quality:                { name: '质检',       emoji: '✅', color: 'var(--agent-quality)' },
      settlement:             { name: '结算',       emoji: '🧾', color: 'var(--agent-settlement)' },
      support:                { name: '客服',       emoji: '🎧', color: 'var(--agent-support)' },
      admin:                  { name: '管理',       emoji: '⚙️', color: 'var(--accent)' },
      ar_measurement:         { name: 'AR测量',     emoji: '📏', color: 'var(--agent-design)' },
      floorplans:             { name: '户型',       emoji: '📋', color: 'var(--agent-design)' },
      structural:             { name: '土建结构',   emoji: '🏗️', color: 'var(--agent-construction)' },
      lighting:               { name: '灯光',       emoji: '💡', color: 'var(--agent-design)' },
      smart_home:             { name: '智能家居',   emoji: '🤖', color: 'var(--agent-construction)' },
      scene_automation:       { name: '场景',       emoji: '🔄', color: 'var(--agent-design)' },
      custom_furniture:       { name: '定制家具',   emoji: '🪚', color: 'var(--agent-design)' },
      tasks:                  { name: '任务',       emoji: '📝', color: 'var(--agent-construction)' },
      change_orders:          { name: '变更',       emoji: '📋', color: 'var(--agent-construction)' },
      crews:                  { name: '工程队',     emoji: '👷', color: 'var(--agent-construction)' },
      vr_panorama:            { name: 'VR全景',     emoji: '🥽', color: 'var(--agent-design)' },
      ai_render:              { name: 'AI渲染',     emoji: '🎨', color: 'var(--agent-design)' },
      sketch_to_3d:           { name: '草图转3D',   emoji: '✏️', color: 'var(--agent-design)' },
      soft_furnishing:        { name: '软装',       emoji: '🛋️', color: 'var(--agent-design)' },
      hard_decoration:        { name: '硬装',       emoji: '🧱', color: 'var(--agent-construction)' },
      takeoff:                { name: '工程量',     emoji: '📊', color: 'var(--agent-construction)' },
      points:                 { name: '积分',       emoji: '⭐', color: 'var(--agent-master)' },
      cad_import:             { name: 'CAD导入',    emoji: '📐', color: 'var(--agent-design)' },
      kitchen:                { name: '厨房',       emoji: '🍳', color: 'var(--agent-design)' },
      bathroom:               { name: '卫浴',       emoji: '🛁', color: 'var(--agent-design)' },
      mep:                    { name: '水电暖通',   emoji: '🔧', color: 'var(--agent-construction)' },
      appliance:              { name: '家电',       emoji: '📺', color: 'var(--agent-procurement)' },
      furniture_catalog:      { name: '家具',       emoji: '🪑', color: 'var(--agent-procurement)' },
      door_window_waterproof: { name: '门窗防水',   emoji: '🚪', color: 'var(--agent-construction)' },
      files:                  { name: '文件',       emoji: '📁', color: 'var(--agent-master)' },
      products:               { name: '产品',       emoji: '🏷️', color: 'var(--agent-procurement)' },
      identity:               { name: '身份认证',   emoji: '🆔', color: 'var(--agent-master)' },
      voice:                  { name: '语音',       emoji: '🎙️', color: 'var(--agent-master)' },
      notifications:          { name: '通知',       emoji: '🔔', color: 'var(--agent-master)' },
      ifc_export:             { name: 'BIM导出',    emoji: '🏗️', color: 'var(--agent-design)' },
    };
    return map[agentKey] || map.master;
  },
};

// 暴露到全局
window.AgentRouter = AgentRouter;
