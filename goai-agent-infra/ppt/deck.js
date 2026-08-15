// GOAI 赛道一 · Agent Infra — 初赛方案 PPT v3
// 家装全流程多 Agent 协同系统(AgentTeams 编排 × i-home.life 真实全链路 × MCP/A2A 双协议)
// 基于真实能力全景 + 2026 技术对齐 · 索克蓝主题 · 16:9 · 15 页
"use strict";

const PptxGenJS = require("pptxgenjs");
const helpers = require("./index.js");

const pptx = new PptxGenJS();
pptx.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });
pptx.layout = "WIDE";

const C = {
  dark: "001833", primary: "007aff", primary600: "0062cc", primary200: "99c9ff", primary50: "e8f2ff",
  ink: "1d1d1f", gray: "6e6e73", light: "f5f5f7", white: "FFFFFF",
  success: "28a745", success50: "e8f8ee", warning: "ff9500", warning50: "fff8e8",
  error: "ff3b30", error50: "fce8e8", info: "5ac8fa", info50: "e8f5fc",
};
const FONT = "Microsoft YaHei";
const MONO = "Consolas";
const W = 13.333;
const H = 7.5;
const MARGIN = 0.6;

function addFooter(slide, pageNo) {
  slide.addText("GOAI 赛道一 · Agent Infra ｜ 家装全流程多 Agent 协同系统 ｜ i-home.life", {
    x: MARGIN, y: H - 0.42, w: 9, h: 0.3, fontSize: 9, color: C.gray, fontFace: FONT, align: "left",
  });
  slide.addText(String(pageNo).padStart(2, "0"), {
    x: W - MARGIN - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 9, color: C.gray, fontFace: FONT, align: "right",
  });
}

function addHeader(slide, kicker, title) {
  slide.addShape(pptx.ShapeType.rect, { x: MARGIN, y: 0.5, w: 0.09, h: 0.55, fill: { color: C.primary } });
  slide.addText(kicker.toUpperCase(), {
    x: MARGIN + 0.22, y: 0.42, w: 10, h: 0.28, fontSize: 11, color: C.primary, fontFace: FONT, bold: true, charSpacing: 2,
  });
  slide.addText(title, {
    x: MARGIN + 0.22, y: 0.7, w: 12, h: 0.55, fontSize: 23, color: C.dark, fontFace: FONT, bold: true,
  });
  slide.addShape(pptx.ShapeType.line, { x: MARGIN, y: 1.35, w: W - 2 * MARGIN, h: 0, line: { color: "E0E0E6", width: 1 } });
}

function addCard(slide, x, y, w, h, fill) {
  return slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, fill: { color: fill || C.light }, line: { color: "E8E8ED", width: 0.75 }, rectRadius: 0.06,
  });
}

function addAccentBar(slide, x, y, w, color) {
  slide.addShape(pptx.ShapeType.rect, { x, y, w, h: 0.045, fill: { color: color || C.primary } });
}

function bullet(slide, textLines, x, y, w, h, fontSize, color) {
  const opts = {
    x, y, w, h, fontSize, color: color || C.ink, fontFace: FONT, valign: "top",
    breakLine: false,
  };
  return slide.addText(textLines, opts);
}

// ════════════════════════════════════════════════════════
// P1 封面
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  // 装饰圆(有意部分越界,避开文字区)
  s.addShape(pptx.ShapeType.ellipse, { x: 11.4, y: -3.0, w: 4.0, h: 4.0, fill: { color: "003166" }, line: { type: "none" } });
  s.addShape(pptx.ShapeType.ellipse, { x: -2.6, y: 6.1, w: 3.2, h: 3.2, fill: { color: "003166" }, line: { type: "none" } });
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.14, h: H, fill: { color: C.primary } });

  s.addText("GOAI 2026 · 赛道一 新智基座 | Agent Infra", {
    x: 0.9, y: 0.85, w: 9, h: 0.4, fontSize: 14, color: C.primary200, fontFace: FONT, bold: true, charSpacing: 3,
  });
  s.addText("家装全流程多 Agent 协同系统", {
    x: 0.9, y: 1.35, w: 11.5, h: 1.1, fontSize: 42, color: C.white, fontFace: FONT, bold: true,
  });
  s.addText("AgentTeams 编排 × i-home.life 真实全链路能力 × MCP 2026-07-28 规范 + A2A v1.0", {
    x: 0.9, y: 2.55, w: 11.5, h: 0.45, fontSize: 16, color: "CCE4FF", fontFace: FONT,
  });
  s.addText("从 AR 量房、手绘草图、CAD 图纸、语音指令到方案设计、算量报价、采购施工、质检结算的端到端自动化", {
    x: 0.9, y: 3.0, w: 11.5, h: 0.45, fontSize: 12.5, color: "66ADFF", fontFace: FONT,
  });

  const layers = [
    { t: "76 个 API 路由模块", d: "139 ORM · 109 Service", c: C.primary },
    { t: "25 个 Agent 模块", d: "总控/设计/预算/采购/施工/质检/结算…", c: C.info },
    { t: "MCP 8 项 + A2A v1.0", d: "2026 双协议 · 11 个真实工具", c: C.success },
  ];
  layers.forEach((L, i) => {
    const x = 0.9 + i * 3.9;
    s.addShape(pptx.ShapeType.roundRect, {
      x, y: 4.0, w: 3.55, h: 1.35, fill: { color: "003166" }, line: { color: C.primary600, width: 1 }, rectRadius: 0.08,
    });
    s.addShape(pptx.ShapeType.rect, { x, y: 4.0, w: 0.07, h: 1.35, fill: { color: L.c } });
    s.addText(L.t, { x: x + 0.25, y: 4.17, w: 3.1, h: 0.4, fontSize: 15, color: C.white, fontFace: FONT, bold: true });
    s.addText(L.d, { x: x + 0.25, y: 4.6, w: 3.15, h: 0.6, fontSize: 10.5, color: "99C9FF", fontFace: FONT });
  });

  s.addText("队伍:索克家居 · i-home.life ｜ AgentTeams(开源 Hiclaw)× i-home.life v1.14.0(生产运行)", {
    x: 0.9, y: 6.3, w: 11.5, h: 0.35, fontSize: 12, color: "66ADFF", fontFace: FONT,
  });
  s.addText("2026 · 初赛 V4.2(基于真实能力全景 v1.14.0 + 2026 最新技术对齐 + 空间数字底座 Robot-Ready Home)", { x: 0.9, y: 6.7, w: 9, h: 0.35, fontSize: 11, color: "66ADFF", fontFace: FONT });
}

// ════════════════════════════════════════════════════════
// P2 行业背景:空间智能范式转移 + 市场 + 2026 协议标准化
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Industry 2026", "行业背景:家装 AI 从\"像素生成\"到\"空间智能\"的范式转移");
  addFooter(s, 2);

  // 左:白皮书三能力
  s.addText("《2026 中国智能家装设计行业发展白皮书》· 空间智能三能力", {
    x: MARGIN, y: 1.55, w: 6.3, h: 0.4, fontSize: 13, color: C.dark, fontFace: FONT, bold: true,
  });
  const caps = [
    { t: "空间感知", d: "看懂户型图,识别墙体/门窗/承重结构", c: C.primary },
    { t: "空间推理", d: "判断动线是否合理、空间是否被浪费", c: C.info },
    { t: "空间交互", d: "把设计方案转化为可执行的施工指令", c: C.success },
  ];
  caps.forEach((cp, i) => {
    const y = 2.0 + i * 1.05;
    addCard(s, MARGIN, y, 6.3, 0.9, C.light);
    s.addShape(pptx.ShapeType.ellipse, { x: MARGIN + 0.15, y: y + 0.25, w: 0.4, h: 0.4, fill: { color: cp.c } });
    s.addText(String(i + 1), { x: MARGIN + 0.15, y: y + 0.27, w: 0.4, h: 0.36, fontSize: 13, color: C.white, fontFace: FONT, bold: true, align: "center" });
    s.addText(cp.t, { x: MARGIN + 0.7, y: y + 0.12, w: 5.4, h: 0.35, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
    s.addText(cp.d, { x: MARGIN + 0.7, y: y + 0.5, w: 5.4, h: 0.32, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });
  s.addText("市场:AI 室内设计 2025 年 32.8 亿美元 → 2033 年 150 亿美元(CAGR 20.9%);2028 中国空间设计软件 68 亿元", {
    x: MARGIN, y: 5.3, w: 6.3, h: 0.6, fontSize: 10.5, color: C.primary600, fontFace: FONT, bold: true,
  });

  // 右:2026 Agent 基础设施标准化
  s.addText("2026 Agent 基础设施标准化(本方案全部对齐)", {
    x: 7.2, y: 1.55, w: 5.5, h: 0.4, fontSize: 13, color: C.dark, fontFace: FONT, bold: true,
  });
  const trends = [
    { t: "MCP", d: "AAIF 托管 · 10k+ Server · 月 9700 万 SDK 下载", s: "✅ 规范 8 项全实现" },
    { t: "A2A v1.0", d: "2026-03 发布 · 150+ 组织 · 22k+ stars", s: "✅ A2A v1.0 在线" },
    { t: "MCP+A2A 融合草案", d: "2026-06-25 AAIF:分层架构非合并", s: "✅ 双协议同平台" },
    { t: "AG-UI", d: "2026-03 三方对齐 · Agent 动作前端透明", s: "✅ 对齐 AG-UI 卡片流" },
  ];
  trends.forEach((tr, i) => {
    const y = 2.0 + i * 1.0;
    addCard(s, 7.2, y, 5.5, 0.9, C.primary50);
    s.addText(tr.t, { x: 7.4, y: y + 0.06, w: 3.0, h: 0.3, fontSize: 12.5, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(tr.d, { x: 7.4, y: y + 0.4, w: 3.0, h: 0.4, fontSize: 9.5, color: C.gray, fontFace: FONT });
    s.addText(tr.s, { x: 10.6, y: y + 0.1, w: 2.0, h: 0.7, fontSize: 9.5, color: C.success, fontFace: FONT, bold: true, align: "right", valign: "mid" });
  });

  // 底部定位
  addCard(s, MARGIN, 6.05, 12.1, 0.9, C.dark);
  s.addShape(pptx.ShapeType.rect, { x: MARGIN, y: 6.05, w: 0.1, h: 0.9, fill: { color: C.primary } });
  s.addText("索克差异化定位:不做\"效果图工具\",而是家装全流程多 Agent 自主协同 + 标准 MCP/A2A 基础设施 —— 真实业务闭环(76 路由模块/139 模型/25 Agent/109 Service)+ 开放协议 + 可编排协同层(AgentTeams)", {
    x: MARGIN + 0.3, y: 6.18, w: 11.5, h: 0.65, fontSize: 11.5, color: C.white, fontFace: FONT, valign: "mid",
  });
}

// ════════════════════════════════════════════════════════
// P3 竞品能力覆盖矩阵
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Competitive Matrix", "竞品能力覆盖矩阵:全链路一体化是核心差异");
  addFooter(s, 3);

  const dims = [
    ["能力维度", "酷家乐", "住小帮", "Shapr3D", "Procore", "Planner5D", "MagicPlan", "索克家居"],
    ["AR/LiDAR 空间测量", "✕", "✕", "✕", "✕", "✕", "△", "✓"],
    ["3D 设计建模", "✓", "✕", "✓", "✕", "✓", "△", "✓"],
    ["照片级效果图渲染", "✓", "✕", "△", "✕", "✓", "✕", "✓"],
    ["CAD 精确绘图(平立剖)", "△", "✕", "✓", "✕", "△", "△", "✓"],
    ["AI 设计生成与建议", "△", "✕", "✕", "✕", "△", "✕", "✓"],
    ["智能预算与 BOM", "✕", "✕", "✕", "△", "✕", "✕", "✓"],
    ["供应链/采购管理", "✕", "△", "✕", "△", "✕", "✕", "✓"],
    ["施工过程管理", "✕", "✕", "✕", "✓", "✕", "✕", "✓"],
    ["结算/验收闭环", "✕", "✕", "✕", "△", "✕", "✕", "✓"],
    ["AI Agent 自治运营", "✕", "✕", "✕", "✕", "✕", "✕", "✓"],
    ["多端协同(平板+手机)", "△", "△", "✕", "△", "✓", "△", "✓"],
  ];
  const rows = dims.map((row, ri) =>
    row.map((cell, ci) => {
      const isSoke = ci === 7;
      const isDim = ci === 0;
      const isHeader = ri === 0;
      const textColor = isHeader ? C.white : isDim ? C.dark : isSoke ? C.primary600 : C.gray;
      const fillColor = isHeader ? C.dark : isSoke ? C.primary50 : ri % 2 === 0 ? C.light : C.white;
      const fontSize = isHeader ? 10 : isDim ? 8.5 : 9;
      return {
        text: cell,
        options: {
          color: textColor,
          bold: isDim || isSoke || isHeader,
          fontSize,
          fontFace: FONT,
          align: "center",
          valign: "mid",
          fill: { color: fillColor },
        },
      };
    })
  );
  s.addTable(rows, {
    x: MARGIN, y: 1.55, w: 12.1,
    colW: [2.9, 1.17, 1.17, 1.17, 1.17, 1.25, 1.35, 1.92],
    rowH: [0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36, 0.36],
    border: { type: "solid", color: "E0E0E6", pt: 0.5 },
  });

  s.addText("竞品多为单点能力(设计 or 管理 or 测量),索克家居实现测量→设计→预算→采购→施工→结算全链路一体化 + AI Agent 自治运营(✓=完全具备 △=部分 ✕=缺失)", {
    x: MARGIN, y: 6.45, w: 12.1, h: 0.4, fontSize: 10.5, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P4 索克家居能力全景(真实全流程闭环,实测数字)
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Capability Map", "索克家居能力全景:真实全流程自动化闭环(76 路由模块实测)");
  addFooter(s, 4);

  const stages = [
    { t: "多模态输入", d: "AR 量房 / 草图转 3D / CAD / 拍照 / 语音双工 / 传感器", c: C.primary },
    { t: "总控编排", d: "Orchestrator 40 意图 + AgentTeams Manager-Workers", c: C.dark },
    { t: "设计域", d: "方案 + 11 类分空间设计器 + 施工图 + BIM/IFC + 渲染 L0-L3 + VR", c: C.primary600 },
    { t: "预算算量", d: "正向算量 / 分项报价 / 定额库(9 类×4 档)", c: C.info },
    { t: "采购·供应链", d: "供应商入驻审核 / 比价 / 担保支付 / 物流 / 拍照上架", c: C.info },
    { t: "施工·服务商", d: "工程队/技术人员入驻 / 任务池 / 三方 IM / 变更审批", c: C.success },
    { t: "质检结算", d: "验收报告 / 图纸比对 / 里程碑结算 / 支付 / 积分", c: C.warning },
    { t: "智能运营", d: "能耗 / 健康 OS / 场景自动化 / 预测性维护", c: C.error },
  ];
  stages.forEach((st, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = MARGIN + col * 3.1;
    const y = 1.6 + row * 2.1;
    addCard(s, x, y, 2.9, 1.85, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y, w: 2.9, h: 0.09, fill: { color: st.c } });
    s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.15, y: y + 0.18, w: 1, h: 0.4, fontSize: 18, color: st.c, fontFace: FONT, bold: true });
    s.addText(st.t, { x: x + 0.15, y: y + 0.6, w: 2.6, h: 0.35, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(st.d, { x: x + 0.15, y: y + 0.98, w: 2.62, h: 0.8, fontSize: 9.5, color: C.gray, fontFace: FONT });
    if (col < 3) {
      s.addText("→", { x: x + 2.94, y: y + 0.75, w: 0.16, h: 0.4, fontSize: 12, color: C.primary, fontFace: FONT, align: "center" });
    }
  });

  s.addText("* 诚实边界:质检真实 CV 已启用(`real_cv_quality_enabled=True`),不可用时诚实降级到规则 mock 并标注 `cv_mode=\"mock\"`;VR 渲染、AI 渲染 L1/L2 为标注降级;前沿功能(材料溯源 HENF / AI 工地监理 / 局改快装 / 米家生态+L1-L5 / 方案 LLM 深化 / BOM 版本+几何算量)均已实装(实测 76 路由模块/139 模型/2392 测试基线全绿)", {
    x: MARGIN, y: 6.35, w: 12.1, h: 0.4, fontSize: 10.5, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P5 2026 前沿功能实装(方案 V4.1 新增,诚实降级)
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Frontier Features", "2026 前沿功能实装:六项增量全部落地(带诚实降级)");
  addFooter(s, 5);

  const frontier = [
    { t: "F50 材料溯源(HENF)", d: "一板一码:产地/批次/物流全链路可查 + HENF 环保等级(GB18580-2025)", g: "无认证数据 → unverified 诚实标注,不伪装等级", c: C.primary },
    { t: "F48 AI 施工监理", d: "闭水试验监测 / 违规抓拍,多模态视觉大模型(DeepSeek→GLM→Qwen)", g: "视觉 key 不可用 → 规则 mock + `cv_mode=\"mock\"` 标注", c: C.info },
    { t: "F49 局改快装产品化", d: "48h 厨卫换新 / 7 天墙面焕新标准化套餐 + 干法施工 + 0 搬家", g: "无套餐模板 → 明确占位,不臆造", c: C.success },
    { t: "F46 米家生态桥接 + L1-L5", d: "真实小米云登录 + 设备清单;L1-L5 智能等级量化(对齐国标,L3 起真智能)", g: "云登录失败/未实现控制 → 诚实报错 + 待实现标注", c: C.warning },
    { t: "F45 方案前置 LLM 深化", d: "6 大装修风格目录 + 多轮反馈深化方案(LLM 优先,方案 B 加中岛)", g: "LLM 不可用 → 规则兜底 + `source=rule_based` 标注", c: C.error },
    { t: "F7 BOM 版本 + 几何算量", d: "BOM 版本快照/差异对比 + 从 floorplan 几何派生工程量", g: "无几何数据 → 经验法 + `quantity_source=empirical` 标注", c: C.dark },
  ];
  frontier.forEach((f, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = MARGIN + col * 4.18;
    const y = 1.6 + row * 2.0;
    addCard(s, x, y, 3.9, 1.8, C.light);
    addAccentBar(s, x, y, 0.25, f.c);
    s.addText(f.t, { x: x + 0.2, y: y + 0.14, w: 3.5, h: 0.35, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(f.d, { x: x + 0.2, y: y + 0.55, w: 3.55, h: 0.7, fontSize: 9.5, color: C.gray, fontFace: FONT });
    s.addText("诚实降级:" + f.g, { x: x + 0.2, y: y + 1.28, w: 3.55, h: 0.42, fontSize: 8.5, color: C.primary600, fontFace: FONT, bold: true });
  });

  addCard(s, MARGIN, 5.75, 12.1, 1.0, C.success50);
  s.addText("诚实降级原则:所有前沿功能带 feature flag + 来源标注(db / rule_based / empirical / mock),禁用硬编码假数据 —— 呼应赛题\"不伪装能力\"与白皮书空间智能(实测 76 路由模块/139 模型/25 Agent/109 Service)", {
    x: MARGIN + 0.25, y: 5.9, w: 11.6, h: 0.7, fontSize: 11, color: C.success, fontFace: FONT, valign: "mid",
  });
}

// ════════════════════════════════════════════════════════
// P6 多模态采集:真实空间感知 + 残健融合
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Spatial Perception", "多模态采集:对齐 2026 白皮书\"空间感知\"能力");
  addFooter(s, 6);

  const inputs = [
    { t: "AR 空间测量", d: "LiDAR / 视觉 SLAM / 摄影测量 / 手动四级降级,RMS 精度报告;iOS ARKit+RoomPlan,鸿蒙原生工程", c: C.primary },
    { t: "手绘草图转 3D", d: "识别墙/门/窗/面积/房间数,生成 3D 布局", c: C.info },
    { t: "CAD 图纸导入", d: "DXF 解析(ezdxf)+ DWG 转换 + 2D CAD 编辑器", c: C.success },
    { t: "语音全双工", d: "Qwen-Audio-3.0-Realtime:流式 ASR+TTS+工具调用,全局悬浮语音,4 场景画像(含 elderly)", c: C.warning },
    { t: "拍照识别 + 传感器", d: "拍照识别产品上架;加速度/陀螺/磁力 60Hz + GPS 融合快照", c: C.error },
    { t: "户型 SSOT", d: "floorplan.data 单一数据源,支撑施工图/BIM/算量自动生成", c: C.dark },
  ];
  inputs.forEach((inp, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = MARGIN + col * 4.18;
    const y = 1.6 + row * 2.05;
    addCard(s, x, y, 3.9, 1.85, C.light);
    addAccentBar(s, x, y, 0.25, inp.c);
    s.addText(inp.t, { x: x + 0.2, y: y + 0.14, w: 3.5, h: 0.35, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(inp.d, { x: x + 0.2, y: y + 0.55, w: 3.55, h: 1.2, fontSize: 10, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 6.05, 12.1, 0.85, C.success50);
  s.addText("残健融合:全局语音悬浮窗(任意页面唤起+后台并行 Agent)+ 主动语音播报 + Semantics 语义标注 + AR 扫描引导(弱视/行动不便者量房替代)—— 诚实边界:无障碍以\"语音+播报+AR 引导\"为形态,非专用导盲/手语模块", {
    x: MARGIN + 0.25, y: 6.15, w: 11.6, h: 0.65, fontSize: 10.5, color: C.success, fontFace: FONT, valign: "mid",
  });
}

// ════════════════════════════════════════════════════════
// P7 总控编排:Orchestrator × AgentTeams(五项映射 + 审批 + 自主权)
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Orchestration", "总控编排:i-home.life 总控 × AgentTeams 协同的映射");
  addFooter(s, 7);

  // 左:i-home.life
  addCard(s, MARGIN, 1.55, 5.6, 1.85, C.primary50);
  s.addText("i-home.life 总控层(真实)", { x: MARGIN + 0.2, y: 1.63, w: 5.2, h: 0.3, fontSize: 13.5, color: C.primary600, fontFace: FONT, bold: true });
  const lh = [
    "OrchestratorAgent:39 类意图 LLM 分类 + 关键词规则兜底",
    "AgentRuntime/Harness:生命周期·追踪·降级·离线 Eval",
    "语音并行编排:\"同时/另外/再帮我\"多任务调度",
    "SSE 流式:thinking_step 展示 Agent 决策过程",
  ];
  lh.forEach((t, i) => {
    s.addText("•  " + t, { x: MARGIN + 0.2, y: 1.97 + i * 0.34, w: 5.2, h: 0.3, fontSize: 10, color: C.ink, fontFace: FONT });
  });

  // 右:AgentTeams
  addCard(s, 7.13, 1.55, 5.6, 1.85, C.light);
  s.addText("AgentTeams 协同层(阿里云产品/开源 Hiclaw)", { x: 7.33, y: 1.63, w: 5.2, h: 0.3, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
  const rh = [
    "Manager-Workers:任务拆解 → 路由 → 并行执行",
    "Matrix 透明房间:人可随时介入/纠正/回放",
    "MinIO 共享文件:中间产物交换,防 Token 爆炸",
    "Worker 经 ihome-mcp Skill 调 i-home.life MCP",
  ];
  rh.forEach((t, i) => {
    s.addText("•  " + t, { x: 7.33, y: 1.97 + i * 0.34, w: 5.2, h: 0.3, fontSize: 10, color: C.ink, fontFace: FONT });
  });

  // 赛题映射五要素
  s.addText("赛题五项能力映射到框架能力(8.1 核心核验点)", { x: MARGIN, y: 3.52, w: 8, h: 0.3, fontSize: 12.5, color: C.dark, fontFace: FONT, bold: true });
  const maps = [
    { t: "角色编排", d: "25 Agent ↔ 9 角色(1 Leader + 8 Worker)" },
    { t: "任务拆解", d: "40 意图 + Manager 路由 + 多意图并行" },
    { t: "上下文传递", d: "Matrix + MinIO + 加密会话 + SSOT" },
    { t: "协同执行", d: "并行 + 失败隔离 + 凭证收敛" },
    { t: "状态追踪", d: "Harness Trace + OTel + 审计" },
  ];
  maps.forEach((m, i) => {
    const x = MARGIN + i * 2.46;
    addCard(s, x, 3.85, 2.3, 0.9, C.light);
    addAccentBar(s, x, 3.85, 0.25, C.primary);
    s.addText(m.t, { x: x + 0.12, y: 3.93, w: 2.1, h: 0.28, fontSize: 11, color: C.dark, fontFace: FONT, bold: true });
    s.addText(m.d, { x: x + 0.12, y: 4.22, w: 2.1, h: 0.46, fontSize: 8.5, color: C.gray, fontFace: FONT });
  });

  // 人类审批节点 H1-H5
  s.addText("人类审批节点(高风险动作人工确认 · 赛题\"审批/审计\"硬要求)", { x: MARGIN, y: 4.9, w: 9, h: 0.3, fontSize: 12.5, color: C.dark, fontFace: FONT, bold: true });
  const approvals = ["H1 方案确认", "H2 预算批准", "H3 下单确认", "H4 验收确认", "H5 结算确认"];
  approvals.forEach((ap, i) => {
    const x = MARGIN + i * 2.5;
    addCard(s, x, 5.22, 2.3, 0.5, C.warning50);
    s.addText(ap, { x, y: 5.29, w: 2.3, h: 0.36, fontSize: 11.5, color: C.warning, fontFace: FONT, bold: true, align: "center" });
  });

  // Agent 自主权分级 L1-L4
  s.addText("Agent 自主权分级(工程成熟度)", { x: MARGIN, y: 5.85, w: 6, h: 0.3, fontSize: 12.5, color: C.dark, fontFace: FONT, bold: true });
  const levels = [
    { t: "L1 建议", d: "Agent 建议,人类决策" },
    { t: "L2 执行+确认", d: "自动执行,人工审批" },
    { t: "L3 自主执行", d: "完全自主,仅通知结果" },
    { t: "L4 自适应", d: "历史项目持续优化" },
  ];
  levels.forEach((lv, i) => {
    const x = MARGIN + i * 3.1;
    addCard(s, x, 6.17, 2.9, 0.55, C.info50);
    s.addText(lv.t + "  " + lv.d, { x: x + 0.12, y: 6.24, w: 2.7, h: 0.4, fontSize: 9.5, color: C.info, fontFace: FONT, bold: true });
  });
}

// ════════════════════════════════════════════════════════
// P8 设计域:从方案到交付物
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Design Domain", "设计域:从空间理解到交付物一键生成");
  addFooter(s, 8);

  // 左:方案能力
  addCard(s, MARGIN, 1.6, 5.4, 4.9, C.light);
  s.addText("方案生成与迭代", { x: MARGIN + 0.2, y: 1.72, w: 5.0, h: 0.35, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const design = [
    ["DesignerAgent", "3 套平面布局 + 动线分析(空间推理)"],
    ["讨论式方案", "2-3 套方案 + 语音增量修订(\"方案 B 加中岛\")"],
    ["分空间设计器 ×11", "厨房/卫浴/硬装/软装/灯光/家具/家电/门窗/定制/土建/机电"],
    ["施工图自动生成", "模型即图纸:平/立/剖面 SVG 自动重生成"],
    ["BIM / IFC 导出", "IFC4 真实坐标 + Pset 属性(LOD200/300/350)"],
    ["AI 渲染 L0-L3", "ControlNet → mock → 占位 → 503 诚实降级"],
    ["VR 全景漫游", "全景图 + 热点 + 场景组合"],
  ];
  design.forEach((dd, i) => {
    s.addText(dd[0], { x: MARGIN + 0.2, y: 2.12 + i * 0.6, w: 2.0, h: 0.3, fontSize: 10, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(dd[1], { x: MARGIN + 2.2, y: 2.12 + i * 0.6, w: 3.0, h: 0.55, fontSize: 9, color: C.gray, fontFace: FONT });
  });

  // 右:交付物流
  s.addText("一次任务 · 全套交付物", { x: 6.4, y: 1.6, w: 6, h: 0.35, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const deliverables = [
    { t: "方案布局图", d: "平面 + 动线 + 3D 户型", c: C.primary },
    { t: "施工图纸", d: "平/立/剖面 SVG(模型即图纸)", c: C.primary600 },
    { t: "BIM/IFC4 文件", d: "真实坐标 + Pset 属性", c: C.info },
    { t: "AI 渲染效果图", d: "2D/3D/照片重布置", c: C.success },
    { t: "VR 全景漫游", d: "720° 场景 + 热点跳转", c: C.warning },
    { t: "算量报价清单", d: "正向算量 → 分项报价", c: C.error },
  ];
  deliverables.forEach((dl, i) => {
    const x = 6.4 + (i % 2) * 3.2;
    const y = 2.05 + Math.floor(i / 2) * 1.05;
    addCard(s, x, y, 3.1, 0.9, C.white);
    s.addShape(pptx.ShapeType.rect, { x, y, w: 0.07, h: 0.9, fill: { color: dl.c } });
    s.addText(dl.t, { x: x + 0.2, y: y + 0.1, w: 2.8, h: 0.32, fontSize: 11.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(dl.d, { x: x + 0.2, y: y + 0.45, w: 2.8, h: 0.38, fontSize: 9, color: C.gray, fontFace: FONT });
  });

  s.addText("对标:飞流AI 上传户型图 5 分钟出全套交付物 —— 索克以开放 MCP 协议 + 多 Agent 编排实现同等闭环,且能力可组合、可迁移、可审计", {
    x: MARGIN, y: 6.6, w: 12.1, h: 0.35, fontSize: 11, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P9 Skill 工程化:ihome-mcp + 10 工具矩阵
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Skill Engineering", "Skill 工程化:ihome-mcp 能力抽象层(11 工具实测)");
  addFooter(s, 9);

  s.addText("ihome-mcp(核心 Skill,8 Worker 复用)", {
    x: MARGIN, y: 1.6, w: 6, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true,
  });
  const sk = [
    { k: "类型", v: "自定义 Skill — 外部系统集成能力封装" },
    { k: "输入", v: "list / call <tool> <JSON 参数>" },
    { k: "输出", v: "MCP JSON-RPC 响应(含 source 来源标注)" },
    { k: "调用条件", v: "Worker 需项目设计/预算/物料/施工/质检数据时" },
    { k: "依赖", v: "i-home.life MCP Server(2026-07-28 规范)+ PASETO" },
    { k: "失败处理", v: "登录/调用失败返回 error JSON,如实说明不编造" },
    { k: "安全边界", v: "凭据 .env 600 权限;只读为主;红线拒绝" },
    { k: "复用价值", v: "8 Worker 复用;可沉淀为分发 Skill 包" },
  ];
  sk.forEach((row, i) => {
    const y = 2.1 + i * 0.56;
    addCard(s, MARGIN, y, 6.0, 0.46, C.light);
    s.addText(row.k, { x: MARGIN + 0.15, y: y + 0.06, w: 1.4, h: 0.34, fontSize: 11.5, color: C.primary, fontFace: FONT, bold: true });
    s.addText(row.v, { x: MARGIN + 1.6, y: y + 0.06, w: 4.3, h: 0.34, fontSize: 10.5, color: C.ink, fontFace: FONT });
  });

  s.addText("MCP 工具能力矩阵(11 个,实测)", {
    x: 7.0, y: 1.6, w: 5.7, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true,
  });
  const tools = [
    ["get_design_layout", "设计方案布局", "design"],
    ["generate_design_proposals", "生成设计方案", "design"],
    ["update_design_proposal", "更新设计提案", "design"],
    ["get_budget", "项目预算查询", "budget"],
    ["search_materials", "装修物料搜索", "procurement"],
    ["get_construction_progress", "施工进度查询", "construction"],
    ["run_qa_inspection", "质量检测执行", "qa"],
    ["launch_agent_task", "启动平台 Agent 任务", "orchestration"],
    ["get_voice_tasks", "语音任务查询", "voice"],
    ["cancel_agent_task", "取消后台任务", "orchestration"],
  ];
  const toolChip = { design: { bg: C.primary50, fg: C.primary600 }, budget: { bg: "D9E9FF", fg: C.primary600 }, procurement: { bg: C.info50, fg: C.info }, construction: { bg: C.success50, fg: C.success }, qa: { bg: C.warning50, fg: C.warning }, orchestration: { bg: "F0F0F2", fg: C.dark }, voice: { bg: C.error50, fg: C.error } };
  tools.forEach((t, i) => {
    const y = 2.1 + i * 0.43;
    s.addText(t[0], { x: 7.0, y, w: 2.9, h: 0.35, fontSize: 10, color: C.ink, fontFace: MONO, bold: true });
    s.addText(t[1], { x: 9.95, y, w: 1.6, h: 0.35, fontSize: 9.5, color: C.gray, fontFace: FONT });
    s.addShape(pptx.ShapeType.roundRect, {
      x: 11.6, y: y + 0.03, w: 1.35, h: 0.3, fill: { color: toolChip[t[2]].bg }, rectRadius: 0.15,
    });
    s.addText(t[2], { x: 11.6, y: y + 0.06, w: 1.35, h: 0.26, fontSize: 8.5, color: toolChip[t[2]].fg, fontFace: FONT, bold: true, align: "center" });
  });
}

// ════════════════════════════════════════════════════════
// P10 MCP 2026-07-28 规范 8 项 + A2A v1.0 双协议
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "MCP + A2A", "双协议在线:MCP 2026-07-28 规范 8 项 + A2A v1.0");
  addFooter(s, 10);

  s.addText("MCP(自研,纯 Python,零第三方 SDK)", {
    x: MARGIN, y: 1.5, w: 6.5, h: 0.32, fontSize: 13, color: C.dark, fontFace: FONT, bold: true,
  });
  const specs = [
    { t: "stateless", d: "无会话握手,请求自描述可横向扩展" },
    { t: "server/discover", d: "能力发现 RPC,统一接入入口" },
    { t: "header-routing", d: "Mcp-Method / Mcp-Name 头路由" },
    { t: "cacheable", d: "tools/list ETag/304 缓存语义" },
    { t: "MRTR", d: "多轮往返协作,采样/追问回传" },
    { t: "RFC 9207 + CIMD", d: "授权硬化,替代 DCR 注册" },
    { t: "Tasks", d: "tasks/* 扩展,任务生命周期" },
    { t: "Server Card", d: ".well-known/mcp 标准化发现" },
  ];
  specs.forEach((sp, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = MARGIN + col * 3.1;
    const y = 1.9 + row * 1.55;
    addCard(s, x, y, 2.9, 1.3, C.primary50);
    s.addText(sp.t, { x: x + 0.18, y: y + 0.12, w: 2.55, h: 0.38, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(sp.d, { x: x + 0.18, y: y + 0.52, w: 2.58, h: 0.7, fontSize: 9.5, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 5.15, 5.9, 1.35, C.success50);
  s.addText("A2A v1.0(2026-03,Google 协议,跨 Agent 委托)", { x: MARGIN + 0.2, y: 5.28, w: 5.5, h: 0.32, fontSize: 13, color: C.success, fontFace: FONT, bold: true });
  const a2a = [
    "GET /.well-known/agent-card:公开 22 个 Agent 技能",
    "tasks/send + tasks/{id} 状态查询:经 Harness 执行并持久化(24h TTL)",
  ];
  a2a.forEach((t, i) => {
    s.addText("•  " + t, { x: MARGIN + 0.2, y: 5.66 + i * 0.38, w: 5.5, h: 0.34, fontSize: 10, color: C.ink, fontFace: FONT });
  });

  addCard(s, 6.8, 5.15, 5.9, 1.35, C.info50);
  s.addText("与 MCP Tasks 互补(2026 融合架构)", { x: 7.0, y: 5.28, w: 5.5, h: 0.32, fontSize: 13, color: C.info, fontFace: FONT, bold: true });
  const comp = [
    "MCP 管工具(纵向连接)· A2A 管 Agent(横向协调)",
    "Worker 调用链路:ihome-mcp Skill → /api/mcp → tools/call → 真实业务",
  ];
  comp.forEach((t, i) => {
    s.addText("•  " + t, { x: 7.0, y: 5.66 + i * 0.38, w: 5.5, h: 0.34, fontSize: 10, color: C.ink, fontFace: FONT });
  });

  s.addText("前沿增量:W3C Trace(SEP-414,响应 `_meta` 注入 traceparent/tracestate/baggage)+ MCP Enterprise(审计/SSO/gateway 扩展,`mcp_enterprise_extension_enabled=True`)均已实装", {
    x: MARGIN, y: 6.6, w: 12.1, h: 0.35, fontSize: 10.5, color: C.primary600, fontFace: FONT, bold: true, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P11 2026 技术对齐(新增)
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "2026 Alignment", "2026 技术对齐:协议标准化 × 空间智能 × 评估飞轮");
  addFooter(s, 11);

  const items = [
    { t: "MCP 2026-07-28 正式版", d: "AAIF 托管 · 8 大 Platinum · SDK 月下载近 1 亿(9700 万)", s: "自研 MCP 规范 8 项(纯 Python 零 SDK)", c: C.primary },
    { t: "A2A v1.0(2026-03)", d: "150+ 组织 · 22k+ stars · 5 SDK · AP2 支付", s: "A2A v1.0 在线 + AP2 结算复用", c: C.info },
    { t: "MCP+A2A 融合草案", d: "2026-06-25 AAIF:分层架构非合并", s: "双协议同平台落地", c: C.success },
    { t: "AG-UI(三方对齐)", d: "2026-03 Oracle+CopilotKit+Google 对齐", s: "对齐 AG-UI 卡片流(区隔 Google A2UI)", c: C.warning },
    { t: "AgentLoop 数据飞轮", d: "赛题两大基础设施之一 · 持续进化维度", s: "自建 AgentTrace+IHomeEval 飞轮对标", c: C.error },
    { t: "空间智能 Agent", d: "SpaceMind(2026-06)/飞流AI 3.1(2026-07)/大晓 Kairos-HomeWorld(2026-07)产业化", s: "三能力齐备 + Robot-Ready Home 空间数字底座", c: C.dark },
  ];
  items.forEach((it, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = MARGIN + col * 4.18;
    const y = 1.6 + row * 2.2;
    addCard(s, x, y, 3.9, 2.0, C.light);
    addAccentBar(s, x, y, 0.25, it.c);
    s.addText(it.t, { x: x + 0.2, y: y + 0.14, w: 3.5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
    s.addText(it.d, { x: x + 0.2, y: y + 0.58, w: 3.55, h: 0.65, fontSize: 10, color: C.gray, fontFace: FONT });
    addCard(s, x + 0.2, y + 1.35, 3.5, 0.5, C.white);
    s.addText("✅ " + it.s, { x: x + 0.32, y: y + 1.42, w: 3.3, h: 0.36, fontSize: 9.5, color: C.success, fontFace: FONT, bold: true });
  });

  s.addText("对齐原则:AgentTeams(协同基座)+ AgentLoop(数据飞轮)双基础设施对标赛题 —— MCP/A2A 标准协议解耦,业务零重写,编排层可替换 ｜ 新增:MCP Enterprise(W3C Trace + 审计/SSO/gateway)+ GB/Z 185-2026 互联互通国标 + WAICO 创始文件", {
    x: MARGIN, y: 6.55, w: 12.1, h: 0.4, fontSize: 11.5, color: C.primary600, fontFace: FONT, bold: true, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P12 可观测与评估
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Observability & Eval", "可观测三支柱 + 评估飞轮(对标赛题 AgentLoop)");
  addFooter(s, 12);

  const pillars = [
    { t: "Trace 链路", d: "OTel 追踪 + AgentHarness 执行轨迹(状态/Token/工具调用链/降级信息)", c: C.primary },
    { t: "Log 日志", d: "structlog 结构化 JSON,PII 脱敏 + trace_id 关联", c: C.info },
    { t: "Metrics 指标", d: "Prometheus:请求/LLM 调用/DB 查询/缓存命中率", c: C.success },
  ];
  pillars.forEach((p, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 1.6, 3.9, 1.85, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.6, w: 3.9, h: 0.09, fill: { color: p.c } });
    s.addText(p.t, { x: x + 0.2, y: 1.8, w: 3.5, h: 0.4, fontSize: 14.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(p.d, { x: x + 0.2, y: 2.25, w: 3.55, h: 1.05, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  s.addText("IHomeEval 领域评估(10 维度)+ Agent-as-a-Judge 飞轮", {
    x: MARGIN, y: 3.75, w: 10, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true,
  });
  const dims = [
    ["报价准确性", "设计安全", "材料禁忌", "越权防护", "流式延迟"],
    ["降级率", "工具调用准确率", "思维链泄漏率", "HC 合规率", "反面论证质量"],
  ];
  dims.forEach((row, r) => {
    row.forEach((dm, i) => {
      const x = MARGIN + i * 2.46;
      const y = 4.25 + r * 0.6;
      addCard(s, x, y, 2.3, 0.46, C.success50);
      s.addText(dm, { x, y: y + 0.06, w: 2.3, h: 0.34, fontSize: 10.5, color: C.success, fontFace: FONT, bold: true, align: "center" });
    });
  });

  addCard(s, MARGIN, 5.75, 12.1, 1.1, C.primary50);
  s.addText("评估飞轮(对标 AgentLoop):Trace → Trajectory → 评估(IHomeEval 10 维 + DSPy)→ Experience 经验自进化 → Skill/Prompt 调优(赛题持续进化维度)", {
    x: MARGIN + 0.25, y: 5.9, w: 11.6, h: 0.4, fontSize: 11.5, color: C.primary600, fontFace: FONT, bold: true,
  });
  s.addText("诚实降级原则:数据来源 db / estimated_fallback / sample_fallback 透明标注,禁止伪装真实能力(历史教训:修复 6 处硬编码假数据)", {
    x: MARGIN + 0.25, y: 6.32, w: 11.6, h: 0.4, fontSize: 10.5, color: C.gray, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P13 安全与审计
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Security & Audit", "安全边界:可运行、可验证、可审计");
  addFooter(s, 13);

  const secs = [
    { t: "PASETO v4.local 鉴权", d: "非 JWT;密钥 ≥32 字节硬校验;WebAuthn/FIDO2/Passkey 无密码登录", c: C.primary },
    { t: "HMAC 审计防篡改", d: "audit_log 写入自动签名(SHA256 + 密钥版本化),PII 8 类脱敏", c: C.info },
    { t: "缓存用户隔离", d: "私有数据 cache key 强制含 user_id,未传直接 raise", c: C.success },
    { t: "审批与回滚", d: "H1-H5 审批节点 + 变更单状态机 + DB 备份回滚 + feature-flag 回退", c: C.warning },
    { t: "HC 硬约束", d: "承重墙 / 报价含税 / 环保等级 / 工期缓冲 / 水电 / 逃生通道 / 燃气(9 HC+3 SC)", c: C.error },
    { t: "RBAC 权限", d: "角色-权限表 + 项目归属校验(IDOR 防护),跨项目访问 403", c: C.dark },
  ];
  secs.forEach((sc, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = MARGIN + col * 6.15;
    const y = 1.6 + row * 1.7;
    addCard(s, x, y, 5.9, 1.5, C.light);
    s.addShape(pptx.ShapeType.ellipse, { x: x + 0.2, y: y + 0.18, w: 0.42, h: 0.42, fill: { color: sc.c } });
    s.addText("✓", { x: x + 0.2, y: y + 0.2, w: 0.42, h: 0.38, fontSize: 15, color: C.white, fontFace: FONT, bold: true, align: "center" });
    s.addText(sc.t, { x: x + 0.8, y: y + 0.16, w: 5.0, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
    s.addText(sc.d, { x: x + 0.8, y: y + 0.6, w: 4.95, h: 0.8, fontSize: 10, color: C.gray, fontFace: FONT });
  });
}

// ════════════════════════════════════════════════════════
// P14 运行验证与 Demo
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Running Demo", "运行验证:线上部署已实测打通");
  addFooter(s, 14);

  addCard(s, MARGIN, 1.6, 5.9, 2.35, C.dark);
  s.addText("部署环境(已在线)", { x: MARGIN + 0.25, y: 1.78, w: 5.4, h: 0.4, fontSize: 14.5, color: C.white, fontFace: FONT, bold: true });
  const deploys = [
    "开源 Hiclaw(controller / manager / dashboard / Element Web)",
    "i-home.life v1.14.0(FastAPI · 阿里云 FC 3.0,架构红线:禁 K8s)",
    "家装团队 ihome-team:1 Leader + 5 Worker 全部 Running",
    "演示数据:3 模拟项目(云栖雅苑 126㎡ 施工中 / 滇池湖畔 / 翠湖名邸),预算 ¥106,214 可逐项核对",
  ];
  deploys.forEach((dd, i) => {
    s.addText("•  " + dd, { x: MARGIN + 0.25, y: 2.25 + i * 0.42, w: 5.5, h: 0.36, fontSize: 10.5, color: "CCE4FF", fontFace: FONT });
  });

  addCard(s, 6.8, 1.6, 5.9, 2.35, C.primary50);
  s.addText("实测调用链路(已验证)", { x: 7.05, y: 1.78, w: 5.4, h: 0.4, fontSize: 14.5, color: C.primary600, fontFace: FONT, bold: true });
  const flow = [
    "ihome-budget → get_budget → 三档预算 + source 标注 ✅",
    "ihome-construction → get_construction_progress → 8 阶段进度 ✅",
    "ihome-procurement → search_materials → 物料列表 ✅",
    "tools/list → 11 个家装工具可发现 ✅",
  ];
  flow.forEach((ff, i) => {
    s.addText("•  " + ff, { x: 7.05, y: 2.25 + i * 0.42, w: 5.5, h: 0.36, fontSize: 10.5, color: C.ink, fontFace: FONT });
  });

  s.addText("Demo 演示流程:业主在 Element Web 下达任务 → Manager 拆解 → 5 Worker 并行经 MCP 取数 → 汇总装修全案", {
    x: MARGIN, y: 4.15, w: 12.1, h: 0.5, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true, align: "center",
  });
  const demo = ["① 输入任务", "② Manager 拆解", "③ Worker 执行", "④ MCP 取数", "⑤ 汇总验证"];
  demo.forEach((dd, i) => {
    const x = MARGIN + i * 2.5;
    addCard(s, x, 4.8, 2.3, 1.5, C.light);
    addAccentBar(s, x, 4.8, 2.3, C.primary);
    s.addText(dd, { x, y: 5.25, w: 2.3, h: 0.6, fontSize: 12.5, color: C.dark, fontFace: FONT, bold: true, align: "center" });
  });
}

// ════════════════════════════════════════════════════════
// P15 开放/开源计划
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Open Source", "开放/开源计划:可复用、可验证、可迁移");
  addFooter(s, 15);

  const items = [
    { t: "AgentTeams Worker 模板", d: "SOUL.md + Agent Identity 清单,任何垂直行业可复制建团", c: C.primary },
    { t: "ihome-mcp Skill", d: "标准化工具调用封装(登录/调用/失败处理),可分发复用", c: C.info },
    { t: "MCP 适配层", d: "2026-07-28 规范 8 项实现,可作为 MCP Server 参考实现", c: C.success },
    { t: "分空间设计器契约 + 数据集", d: "11 类设计器接口契约 + 家装样例输入输出 + 评测基线", c: C.warning },
  ];
  items.forEach((it, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = MARGIN + col * 6.15;
    const y = 1.65 + row * 1.85;
    addCard(s, x, y, 5.9, 1.6, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y, w: 0.1, h: 1.6, fill: { color: it.c } });
    s.addText(it.t, { x: x + 0.3, y: y + 0.18, w: 5.4, h: 0.4, fontSize: 14.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(it.d, { x: x + 0.3, y: y + 0.65, w: 5.4, h: 0.8, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 5.6, 12.1, 1.2, C.primary50);
  s.addText("仓库:github.com/SUOKE2024/i-home.life(已公开)", {
    x: MARGIN + 0.25, y: 5.75, w: 11.6, h: 0.35, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true,
  });
  s.addText("协议 Apache-2.0(与 AgentTeams 兼容)｜ 披露:LLM 商业 API(deepseek/qwen/glm/doubao)· 第三方依赖 · 数据授权边界 ｜ 已有项目基础:i-home.life(76 路由模块 / 139 模型 / 25 Agent / 109 Service)", {
    x: MARGIN + 0.25, y: 6.15, w: 11.6, h: 0.55, fontSize: 10.5, color: C.gray, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P16 落地计划与风险(含复赛 Demo 验收目标)
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Roadmap & Risks", "落地计划与风险应对");
  addFooter(s, 16);

  const phases = [
    { v: "V1 初赛", t: "方案 + 链路验证", d: "AgentTeams 部署、Worker 建团、MCP 调用链路 ✅ 已完成(V4.2)", c: C.success },
    { v: "V1.5 复赛", t: "完整闭环 Demo", d: "三场景可演示 + 评测集 + Trace 看板 + A2A 委托证据", c: C.primary },
    { v: "V2 决赛", t: "真实项目试点", d: "真实项目接入、Agent-as-a-Judge 评测、开源工程化", c: C.warning },
  ];
  phases.forEach((ph, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 1.6, 3.9, 1.75, C.light);
    s.addShape(pptx.ShapeType.roundRect, { x, y: 1.6, w: 3.9, h: 0.55, fill: { color: ph.c }, rectRadius: 0 });
    s.addText(ph.v, { x, y: 1.68, w: 3.9, h: 0.36, fontSize: 15, color: C.white, fontFace: FONT, bold: true, align: "center" });
    s.addText(ph.t, { x: x + 0.2, y: 2.25, w: 3.5, h: 0.35, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(ph.d, { x: x + 0.2, y: 2.62, w: 3.55, h: 0.7, fontSize: 10, color: C.gray, fontFace: FONT });
  });

  // 复赛 Demo 验收目标
  s.addText("复赛 Demo 验收目标(借鉴 PRD Demo 规格)", { x: MARGIN, y: 3.5, w: 8, h: 0.3, fontSize: 13, color: C.dark, fontFace: FONT, bold: true });
  const demos = [
    { t: "AI 语音改设计", d: "\"拆墙做开放式加中岛\" → 3D 更新 + 面积/预算联动(≤5s)", c: C.primary },
    { t: "采购 AI 比价", d: "BOM → 多供应商比价报告 → 一键下单", c: C.info },
    { t: "施工日报质检", d: "现场照片上传 → AI 比对图纸 → 偏差标注整改", c: C.success },
  ];
  demos.forEach((dm, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 3.85, 3.9, 1.5, C.light);
    addAccentBar(s, x, 3.85, 0.25, dm.c);
    s.addText(dm.t, { x: x + 0.2, y: 3.98, w: 3.5, h: 0.32, fontSize: 12.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(dm.d, { x: x + 0.2, y: 4.33, w: 3.55, h: 0.9, fontSize: 9.5, color: C.gray, fontFace: FONT });
  });

  s.addText("风险与应对", { x: MARGIN, y: 5.55, w: 6, h: 0.3, fontSize: 13, color: C.dark, fontFace: FONT, bold: true });
  const risks = [
    "部分能力为诚实标注的 mock(质检缺陷 CV/VR 渲染/AI 渲染 L1/L2)→ 如实披露,契约固化(RENDER_CONTRACT)后续可一键接入真实后端",
    "AgentTeams 版本演进(v1.2.0 刚发布)→ 抽象 MCP 契约层,编排层可替换",
    "LLM 成本与不可用 → 4 供应商 fallback 链(deepseek→qwen→glm→doubao)+ TTS 3 级链",
  ];
  risks.forEach((rk, i) => {
    addCard(s, MARGIN, 5.88 + i * 0.38, 12.1, 0.32, C.warning50);
    s.addText("•  " + rk, { x: MARGIN + 0.2, y: 5.91 + i * 0.38, w: 11.7, h: 0.28, fontSize: 9.5, color: C.ink, fontFace: FONT });
  });
}

// ── 校验:重叠与越界 ──
pptx.writeFile({ fileName: "GOAI初赛-家装全流程多Agent协同系统.pptx" }).then(() => {
  console.log("✅ PPT 已生成");
  for (let i = 0; i < pptx.slides.length; i++) {
    const slide = pptx.slides[i];
    helpers.warnIfSlideHasOverlaps(slide, pptx);
    helpers.warnIfSlideElementsOutOfBounds(slide, pptx);
  }
});
