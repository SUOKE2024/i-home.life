import '../models/chat_message.dart';

/// 自然语言 → Agent 路由器
///
/// 不使用 @ 标记，纯自然语言意图识别。端口自 Web 端 agent-router.js。
class AgentRouter {
  AgentRouter._();

  static final AgentRouter _instance = AgentRouter._();
  factory AgentRouter() => _instance;

  /// 路由结果
  /// - agent: 目标 Agent key
  /// - confidence: 置信度 (0.0 ~ 1.0)
  /// - payload: 附加数据（低置信度时包含 clarify 提示）
  static RouteResult route(String text) {
    if (text.isEmpty) {
      return const RouteResult(agent: 'master', confidence: 0.0);
    }

    final lower = text.toLowerCase();
    final scores = <String, int>{};

    for (final p in _patterns) {
      scores[p.agent] = 0;
      for (final kw in p.keywords) {
        if (text.contains(kw) || lower.contains(kw.toLowerCase())) {
          scores[p.agent] = scores[p.agent]! + 1;
        }
      }
    }

    String bestAgent = 'master';
    int bestScore = 0;
    for (final entry in scores.entries) {
      if (entry.value > bestScore) {
        bestScore = entry.value;
        bestAgent = entry.key;
      }
    }

    final denom = (text.length / 20).ceil().clamp(1, 100);
    final confidence =
        bestScore == 0 ? 0.0 : (bestScore / denom).clamp(0.0, 1.0);

    if (confidence < 0.3 || bestScore == 0) {
      return RouteResult(
        agent: 'master',
        confidence: confidence,
        payload: {
          'clarify': true,
          'message': '我理解你想了解一些信息。能更具体一些吗？比如想问预算、设计、施工进度还是其他？',
        },
      );
    }

    return RouteResult(
      agent: bestAgent,
      confidence: confidence,
      payload: {'original_text': text},
    );
  }

  /// 获取 Agent 显示信息
  static AgentInfo getAgentInfo(String agentKey) {
    return AgentInfo.getByKey(agentKey);
  }

  /// Agent 关键词模式（与 Web 端 agent-router.js 同步）
  static const List<_AgentPattern> _patterns = [
    _AgentPattern(agent: 'budget', keywords: [
      '预算', '花了多少钱', '还剩多少', '支出', '费用', '超支', '成本', '价格',
      '多少钱', '报价', '账单', '付款', '支付',
    ]),
    _AgentPattern(agent: 'design', keywords: [
      '设计', '方案', '图纸', '布局', '风格', '装修风格', '效果图', '改造',
      '改', '开放式', '打通', '隔断', 'CAD', '3D',
    ]),
    _AgentPattern(agent: 'construction', keywords: [
      '施工', '进度', '开工', '水电', '木工', '瓦工', '油漆', '泥工', '贴砖',
      '刷墙', '打孔', '拆', '今天干', '任务', '工序', '阶段',
    ]),
    _AgentPattern(agent: 'procurement', keywords: [
      '采购', '买', '订购', '下单', '物流', '到货', '发货', '什么时候到',
      '供应商', '比价', '地砖', '瓷砖', '地板', '涂料', '材料',
      '发布产品', '上架', '我的产品', '修改产品', '下架', '库存', '报价', '改价格', '产品管理',
    ]),
    _AgentPattern(agent: 'quality', keywords: [
      '质检', '验收', '检查', '问题', '毛病', '整改', '返工', '合格',
      '不合格', '检测', '偏差', '偏差多少',
    ]),
    _AgentPattern(agent: 'settlement', keywords: [
      '结算', '对账', '尾款', '结清', '结账', '完工结算', '最终账单', '总账',
    ]),
    _AgentPattern(agent: 'support', keywords: [
      '客服', '帮助', '怎么用', '怎么操作', '联系', '投诉', '建议', '反馈', '问题反馈',
    ]),
    _AgentPattern(agent: 'master', keywords: [
      '总控', '统筹', '协调', '概况', '整体', '总结', '汇报', '状态',
      '什么时候完工', '还要多久',
    ]),
    _AgentPattern(agent: 'admin', keywords: [
      '用户管理', '角色管理', '权限管理', '平台统计', '管理员', '禁用用户',
      '启用用户', '审核认证', '修改角色', '用户列表', '设为管理员',
      '平台数据', '全部项目', '所有用户', '实名认证',
    ]),
    _AgentPattern(agent: 'ar_measurement', keywords: [
      'AR', 'AR测量', '测量', '扫描', '量房', '激光', 'LiDAR', 'RoomPlan',
      '测距', '丈量', '拍照测量', '三维扫描', '空间测量',
      '面积测算', '户型测绘', '空间扫描', '距离测量', '3D扫描',
    ]),
    _AgentPattern(agent: 'floorplans', keywords: [
      '户型', '平面图', '户型方案', '户型图', '户型管理',
      '我的户型', '保存户型', '楼层平面',
    ]),
    _AgentPattern(agent: 'structural', keywords: [
      '结构', '梁', '柱', '承重', '框架', '地基', '剪力墙', '楼板', '钢筋', '混凝土',
    ]),
    _AgentPattern(agent: 'lighting', keywords: [
      '灯光', '照明', '照度', '色温', '灯具', '射灯', '筒灯', '轨道灯', '氛围灯', '灯带',
    ]),
    _AgentPattern(agent: 'smart_home', keywords: [
      '智能家居', '智能', '自动化', '传感器', '窗帘电机', '智能灯',
      'Matter', 'Zigbee', '智能开关', '智能插座', '温控', '门锁',
    ]),
    _AgentPattern(agent: 'scene_automation', keywords: [
      '场景联动', '场景', '情景', '离家', '回家', '睡眠', '会客', '一键', '触发', '条件',
    ]),
    _AgentPattern(agent: 'custom_furniture', keywords: [
      '定制', '定做', '柜子', '衣柜', '橱柜', '书柜',
      '板材', '板材计算', '展开面积', '投影面积',
    ]),
    _AgentPattern(agent: 'tasks', keywords: [
      '任务', '待办', '交办', '分派', '安排', '谁来做',
      '施工任务', '任务列表', '安排任务',
    ]),
    _AgentPattern(agent: 'change_orders', keywords: [
      '变更', '改方案', '改设计', '变更单', '设计变更',
      '工程变更', '修改方案', '方案变更',
    ]),
    _AgentPattern(agent: 'crews', keywords: [
      '工程队', '班组', '施工队', '外包', '哪个队', '派工',
      '工队', '施工班组', '装修队',
    ]),
    _AgentPattern(agent: 'vr_panorama', keywords: [
      'VR', '全景', '虚拟', '360', '漫游', '沉浸',
      'VR全景', '360度', '虚拟现实',
    ]),
    _AgentPattern(agent: 'ai_render', keywords: [
      '渲染', '效果图', '出图', '配色', '色调',
      '3D渲染', '2D渲染', '渲染图', '风格迁移',
    ]),
    _AgentPattern(agent: 'sketch_to_3d', keywords: [
      '草图', '手绘', '转3D', '画图', '涂鸦',
      '手绘转', '草图转', '随手画',
    ]),
    _AgentPattern(agent: 'soft_furnishing', keywords: [
      '软装', '窗帘', '地毯', '抱枕', '装饰画', '挂画',
      '软装配饰', '布艺', '饰品', '摆件',
    ]),
    _AgentPattern(agent: 'hard_decoration', keywords: [
      '硬装', '吊顶', '墙面装饰', '背景墙', '地面',
      '涂料', '墙纸', '石材', '大理石',
    ]),
    _AgentPattern(agent: 'takeoff', keywords: [
      '工程量', '算量', '材料清单', '用量计算', '工程量清单',
      '材料用量', '辅料计算', '清单计算',
    ]),
    _AgentPattern(agent: 'points', keywords: [
      '积分', '会员', '等级', '兑换', '奖励', '累计', '积分商城',
      '积分兑换', '成长值', '权益',
    ]),
    _AgentPattern(agent: 'cad_import', keywords: [
      'CAD导入', '导入CAD', 'DXF', 'DWG', 'CAD文件',
      '导入图纸', '上传CAD', 'CAD图纸',
    ]),
    // ── v1.1.22 补齐 12 个 Agent 模式（对齐 Web 端）──
    _AgentPattern(agent: 'kitchen', keywords: [
      '厨房', '厨房设计', '橱柜', '三件套', '油烟机', '灶具', '操作台', '厨房动线',
      '黄金三角', '厨房水电', '厨房布局', '岛台', '中岛', '水槽', '洗碗机位置',
    ]),
    _AgentPattern(agent: 'bathroom', keywords: [
      '卫生间', '浴室', '卫浴', '马桶', '淋浴', '花洒', '浴缸', '干湿分离',
      '三分离', '浴室柜', '台盆', '地漏', '坡度', '防水层',
    ]),
    _AgentPattern(agent: 'mep', keywords: [
      '水电点位', '暖通', '空调', '新风', '地暖', '暖气', 'MEP', '强弱电',
      '配电箱', '插座布置', '开关布置', '给排水', '管道', '冷热水', '管线综合',
    ]),
    _AgentPattern(agent: 'appliance', keywords: [
      '家电', '电器', '冰箱', '洗衣机', '洗碗机', '烘干机', '微波炉', '烤箱',
      '蒸箱', '净水器', '垃圾处理器', '家电尺寸', '嵌入家电', '家电预留',
    ]),
    _AgentPattern(agent: 'furniture_catalog', keywords: [
      '家具', '沙发', '餐桌', '床', '椅子', '茶几', '电视柜', '书桌', '衣柜',
      '鞋柜', '家具尺寸', '家具品牌', '家具风格', '家具列表', '家具搭配',
    ]),
    _AgentPattern(agent: 'door_window_waterproof', keywords: [
      '门窗', '窗户', '入户门', '室内门', '推拉门', '平开门', '封阳台',
      '断桥铝', '门窗尺寸', '防水', '防水涂料', '防水层', '闭水试验', '渗水',
    ]),
    _AgentPattern(agent: 'files', keywords: [
      '文件', '上传', '下载', '附件', '合同', '照片', '证件', '文档管理',
      '文件管理', '图纸管理', '合同管理',
    ]),
    _AgentPattern(agent: 'products', keywords: [
      '产品', '商品', '材料价格', '产品目录', '产品上架', '产品管理',
      '产品列表', 'SKU', '产品信息', '规格参数',
    ]),
    _AgentPattern(agent: 'identity', keywords: [
      '实名', '认证', '身份', '身份证', '实名认证', '身份认证', '认证状态', '审核',
    ]),
    _AgentPattern(agent: 'voice', keywords: [
      '语音', '说话', '语音输入', '语音助手', '语音对话', '语音控制', '语音指令',
      '麦克风', '讲话', '录音',
    ]),
    _AgentPattern(agent: 'notifications', keywords: [
      '通知', '消息', '推送', '提醒', '手机通知', '消息提醒', '通知设置',
    ]),
    _AgentPattern(agent: 'ifc_export', keywords: [
      'BIM', 'IFC', '导出BIM', 'BIM模型', 'IFC文件', '结构模型',
      '建筑模型', 'BIM导出', '模型导出', 'IFC格式',
    ]),
  ];
}

/// 路由结果
class RouteResult {
  final String agent;
  final double confidence;
  final Map<String, dynamic>? payload;

  const RouteResult({
    required this.agent,
    required this.confidence,
    this.payload,
  });

  bool get needsClarify => payload?['clarify'] == true;
}

/// 关键词模式（内部使用）
class _AgentPattern {
  final String agent;
  final List<String> keywords;
  const _AgentPattern({required this.agent, required this.keywords});
}
