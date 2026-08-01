// GOAI 赛道一 · Agent Infra — 初赛方案 PPT v2
// 家装全流程多 Agent 协同系统（AgentTeams 编排 × i-home.life 真实全流程 × MCP）
// 索克蓝主题 · 16:9 · 13 页
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
const W = 13.333;
const H = 7.5;
const MARGIN = 0.6;

function addFooter(slide, pageNo) {
  slide.addText("GOAI 赛道一 · Agent Infra ｜ 家装全流程多 Agent 协同系统", {
    x: MARGIN, y: H - 0.42, w: 8, h: 0.3, fontSize: 9, color: C.gray, fontFace: FONT, align: "left",
  });
  slide.addText(String(pageNo).padStart(2, "0"), {
    x: W - MARGIN - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 9, color: C.gray, fontFace: FONT, align: "right",
  });
}

function addHeader(slide, kicker, title) {
  slide.addShape(pptx.ShapeType.rect, { x: MARGIN, y: 0.5, w: 0.09, h: 0.55, fill: { color: C.primary } });
  slide.addText(kicker.toUpperCase(), {
    x: MARGIN + 0.22, y: 0.42, w: 9, h: 0.28, fontSize: 11, color: C.primary, fontFace: FONT, bold: true, charSpacing: 2,
  });
  slide.addText(title, {
    x: MARGIN + 0.22, y: 0.7, w: 11.5, h: 0.55, fontSize: 23, color: C.dark, fontFace: FONT, bold: true,
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

// ════════════════════════════════════════════════════════
// P1 封面
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  // 装饰圆（有意部分越界，避开文字区）
  s.addShape(pptx.ShapeType.ellipse, { x: 11.4, y: -3.0, w: 4.0, h: 4.0, fill: { color: "003166" }, line: { type: "none" } });
  s.addShape(pptx.ShapeType.ellipse, { x: -2.6, y: 6.1, w: 3.2, h: 3.2, fill: { color: "003166" }, line: { type: "none" } });
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.14, h: H, fill: { color: C.primary } });

  s.addText("GOAI 2026 · 赛道一 新智基座 | Agent Infra", {
    x: 0.9, y: 0.85, w: 9, h: 0.4, fontSize: 14, color: C.primary200, fontFace: FONT, bold: true, charSpacing: 3,
  });
  s.addText("家装全流程多 Agent 协同系统", {
    x: 0.9, y: 1.35, w: 11.5, h: 1.1, fontSize: 42, color: C.white, fontFace: FONT, bold: true,
  });
  s.addText("AgentTeams 编排 × i-home.life 真实全流程能力 × MCP 2026-07-28 规范", {
    x: 0.9, y: 2.55, w: 11, h: 0.45, fontSize: 16, color: "CCE4FF", fontFace: FONT,
  });
  s.addText("从 AR 量房、手绘草图、CAD 图纸、语音指令到方案设计、算量报价、采购施工、质检结算的端到端自动化", {
    x: 0.9, y: 3.0, w: 11.3, h: 0.45, fontSize: 12.5, color: "66ADFF", fontFace: FONT,
  });

  const layers = [
    { t: "23 个领域 Agent", d: "总控 / 设计 / 预算 / 采购 / 施工 / 质检 / 结算…", c: C.primary },
    { t: "60 个 API 模块", d: "AR·VR·CAD·BIM·语音·智能家居全链路", c: C.info },
    { t: "MCP 规范 8 项", d: "2026-07-28 全实现 · 工具连接层标准解耦", c: C.success },
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

  s.addText("队伍：索克家居 · i-home.life ｜ 基于 AgentTeams（agentscope-ai/AgentTeams v1.2.0）与 i-home.life v1.3.1", {
    x: 0.9, y: 6.3, w: 11, h: 0.35, fontSize: 12, color: "66ADFF", fontFace: FONT,
  });
  s.addText("2026 · 初赛 V2.0", { x: 0.9, y: 6.7, w: 4, h: 0.35, fontSize: 11, color: "66ADFF", fontFace: FONT });
}

// ════════════════════════════════════════════════════════
// P2 行业背景与机会
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Industry 2026", "行业背景：家装 AI 从\"像素生成\"到\"空间智能\"的范式转移");
  addFooter(s, 2);

  // 左：白皮书三能力
  s.addText("《2026 中国智能家装设计行业发展白皮书》· 空间智能三能力", {
    x: MARGIN, y: 1.55, w: 6.3, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true,
  });
  const caps = [
    { t: "空间感知", d: "看懂户型图，识别墙体/门窗/承重结构", c: C.primary },
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
  s.addText("市场：AI 室内设计 2025 年 32.8 亿美元 → 2033 年 150 亿美元（CAGR 20.9%）", {
    x: MARGIN, y: 5.35, w: 6.3, h: 0.35, fontSize: 10.5, color: C.primary600, fontFace: FONT, bold: true,
  });

  // 右：竞品对标
  s.addText("头部玩家对标（2026-07 建博会 / WAIC）", {
    x: 7.2, y: 1.55, w: 5.5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true,
  });
  const rivals = [
    { n: "金牌家居 · 飞流AI 3.1", d: "上传户型图 5 分钟输出全套交付物 + 承重墙识别", gap: "单点设计，非全流程多 Agent 协同" },
    { n: "三维家 · AI 工作台", d: "多专家智能体 + 图形软件连接器 + 异构应用 Hub", gap: "侧重设计↔生产，开放协议弱" },
    { n: "欧派 · AI 设计", d: "3 分钟全屋方案 + 5 秒渲染 + 设计到生产一键输出", gap: "定制家居闭环，非开放平台" },
  ];
  rivals.forEach((rv, i) => {
    const y = 2.0 + i * 1.05;
    addCard(s, 7.2, y, 5.5, 1.0, C.primary50);
    s.addText(rv.n, { x: 7.4, y: y + 0.1, w: 5.1, h: 0.32, fontSize: 12.5, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(rv.d, { x: 7.4, y: y + 0.44, w: 5.1, h: 0.3, fontSize: 10, color: C.gray, fontFace: FONT });
    s.addText("局限：" + rv.gap, { x: 7.4, y: y + 0.68, w: 5.1, h: 0.26, fontSize: 9, color: C.warning, fontFace: FONT });
  });

  // 底部定位
  addCard(s, MARGIN, 5.95, 12.1, 0.9, C.dark);
  s.addShape(pptx.ShapeType.rect, { x: MARGIN, y: 5.95, w: 0.1, h: 0.9, fill: { color: C.primary } });
  s.addText("索克差异化定位：不做\"效果图工具\"，而是家装全流程多 Agent 自主协同 + 标准 MCP 基础设施 —— 真实业务闭环（23 Agent / 60 API / 90 Service）+ 开放协议（MCP 2026-07-28 规范 8 项）+ 可编排协同层（AgentTeams）", {
    x: MARGIN + 0.3, y: 6.1, w: 11.5, h: 0.65, fontSize: 12, color: C.white, fontFace: FONT, valign: "mid",
  });
}

// ════════════════════════════════════════════════════════
// P3 索克家居能力全景（全流程闭环）
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Capability Map", "索克家居能力全景：真实全流程自动化闭环");
  addFooter(s, 3);

  const stages = [
    { t: "多模态输入", d: "AR 量房 / 手绘草图 / CAD / 拍照 / 语音 / 文本", c: C.primary },
    { t: "总控编排", d: "Orchestrator 37 意图 + AgentTeams Manager-Workers", c: C.dark },
    { t: "设计域", d: "方案 + 11 类分空间设计器 + 施工图 + BIM/IFC + 渲染 + VR", c: C.primary600 },
    { t: "预算算量", d: "正向算量 / 分项报价 / 智能家居方案与布线", c: C.info },
    { t: "采购", d: "物料比价 / 担保支付 / 物流 / 拍照上架", c: C.info },
    { t: "施工", d: "任务池 / 工程队匹配 / 三方 IM / 变更审批", c: C.success },
    { t: "质检结算", d: "验收报告 / 图纸比对 / 里程碑结算 / 支付", c: C.warning },
    { t: "智能运营", d: "能耗 / 健康 / 场景自动化 / 预测性维护", c: C.error },
  ];
  stages.forEach((st, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = MARGIN + col * 3.1;
    const y = 1.6 + row * 2.15;
    addCard(s, x, y, 2.9, 1.9, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y, w: 2.9, h: 0.09, fill: { color: st.c } });
    s.addText(String(i + 1).padStart(2, "0"), { x: x + 0.15, y: y + 0.18, w: 1, h: 0.4, fontSize: 18, color: st.c, fontFace: FONT, bold: true });
    s.addText(st.t, { x: x + 0.15, y: y + 0.62, w: 2.6, h: 0.35, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(st.d, { x: x + 0.15, y: y + 1.0, w: 2.62, h: 0.8, fontSize: 9.5, color: C.gray, fontFace: FONT });
    if (col < 3) {
      s.addText("→", { x: x + 2.94, y: y + 0.8, w: 0.16, h: 0.4, fontSize: 12, color: C.primary, fontFace: FONT, align: "center" });
    }
  });

  s.addText("* 诚实边界：质检缺陷识别（mock CV）、VR 渲染、AI 渲染 L1/L2 为标注降级；其余环节均为真实计算/生成逻辑（60 API 模块 / 50 ORM / 1491 测试全绿）", {
    x: MARGIN, y: 6.35, w: 12.1, h: 0.4, fontSize: 10.5, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P4 多模态采集：真实空间感知
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Spatial Perception", "多模态采集：对齐 2026 白皮书\"空间感知\"能力");
  addFooter(s, 4);

  const inputs = [
    { t: "AR 空间测量", d: "LiDAR / 视觉 SLAM / 摄影测量 / 手动四级降级，RMS 精度报告，墙面特征识别（承重/门窗/梁柱）", c: C.primary },
    { t: "手绘草图转 3D", d: "Sketch-to-3D：识别墙/门/窗/面积/房间数，生成 3D 布局", c: C.info },
    { t: "CAD 图纸导入", d: "DXF 解析（ezdxf：LINE/圆/弧/文字）+ DWG 转换，2D CAD 编辑器", c: C.success },
    { t: "拍照识别产品", d: "供应商拍照上架：多模态 AI 识别产品 + 确认创建", c: C.warning },
    { t: "语音全双工", d: "Qwen-Audio-3.0-Realtime：流式 ASR+TTS、工具调用、双工打断", c: C.error },
    { t: "户型 SSOT", d: "floorplan.data 单一数据源，支撑施工图/BIM/算量自动生成", c: C.dark },
  ];
  inputs.forEach((inp, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = MARGIN + col * 4.18;
    const y = 1.6 + row * 2.1;
    addCard(s, x, y, 3.9, 1.9, C.light);
    addAccentBar(s, x, y, 0.25, inp.c);
    s.addText(inp.t, { x: x + 0.2, y: y + 0.14, w: 3.5, h: 0.35, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(inp.d, { x: x + 0.2, y: y + 0.55, w: 3.55, h: 1.25, fontSize: 10, color: C.gray, fontFace: FONT });
  });

  s.addText("空间数据全链路：采集（多模态）→ 结构化（floorplan SSOT）→ 消费（设计/图纸/BIM/算量）→ 交付（施工/验收）", {
    x: MARGIN, y: 6.5, w: 12.1, h: 0.35, fontSize: 12, color: C.primary600, fontFace: FONT, bold: true, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P5 总控编排：Orchestrator × AgentTeams
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Orchestration", "总控编排：i-home.life 总控 × AgentTeams 协同的映射");
  addFooter(s, 5);

  // 左：i-home.life
  addCard(s, MARGIN, 1.6, 5.6, 2.6, C.primary50);
  s.addText("i-home.life 总控层（真实）", { x: MARGIN + 0.2, y: 1.72, w: 5.2, h: 0.35, fontSize: 14, color: C.primary600, fontFace: FONT, bold: true });
  const lh = [
    "OrchestratorAgent：37 类意图 LLM 分类 + 规则降级",
    "AgentRuntime/Harness：生命周期·追踪·降级策略",
    "语音并行编排：\"同时/另外/再帮我\"多任务调度",
    "SSE 流式：thinking_step 展示 Agent 决策过程",
  ];
  lh.forEach((t, i) => {
    s.addText("•  " + t, { x: MARGIN + 0.2, y: 2.12 + i * 0.42, w: 5.2, h: 0.36, fontSize: 10.5, color: C.ink, fontFace: FONT });
  });

  // 右：AgentTeams
  addCard(s, 7.13, 1.6, 5.6, 2.6, C.light);
  s.addText("AgentTeams 协同层（开源编排）", { x: 7.33, y: 1.72, w: 5.2, h: 0.35, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const rh = [
    "Manager-Workers：任务拆解 → 路由 → 并行执行",
    "Matrix 透明房间：人可随时介入/纠正/回放",
    "MinIO 共享文件：中间产物交换，防 Token 爆炸",
    "Worker 经 ihome-mcp Skill 调 i-home.life MCP",
  ];
  rh.forEach((t, i) => {
    s.addText("•  " + t, { x: 7.33, y: 2.12 + i * 0.42, w: 5.2, h: 0.36, fontSize: 10.5, color: C.ink, fontFace: FONT });
  });

  // 中：映射四要素
  s.addText("赛题要求映射到框架能力", { x: MARGIN, y: 4.45, w: 6, h: 0.35, fontSize: 13, color: C.dark, fontFace: FONT, bold: true });
  const maps = [
    { t: "角色编排", d: "23 Agent ↔ 8 Worker/Leader 映射表" },
    { t: "任务拆解", d: "37 意图分类 + Manager 子任务路由" },
    { t: "上下文传递", d: "Matrix 房间 + MinIO + 会话持久化" },
    { t: "协同执行/状态", d: "Harness Trace + 房间进度汇报" },
  ];
  maps.forEach((m, i) => {
    const x = MARGIN + i * 3.1;
    addCard(s, x, 4.85, 2.9, 1.45, C.light);
    addAccentBar(s, x, 4.85, 0.25, C.primary);
    s.addText(m.t, { x: x + 0.15, y: 4.98, w: 2.6, h: 0.32, fontSize: 12, color: C.dark, fontFace: FONT, bold: true });
    s.addText(m.d, { x: x + 0.15, y: 5.33, w: 2.62, h: 0.85, fontSize: 9.5, color: C.gray, fontFace: FONT });
  });

  // 底部示例
  addCard(s, MARGIN, 6.45, 12.1, 0.55, C.dark);
  s.addText("任务示例：\"请为 120 平三居制定完整装修方案\" → Manager 拆解 → 设计/预算/采购/施工/质检 Worker 经 MCP 并行取数 → 汇总全案", {
    x: MARGIN + 0.25, y: 6.53, w: 11.6, h: 0.4, fontSize: 11.5, color: C.white, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P6 设计域：从方案到交付物
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Design Domain", "设计域：从空间理解到交付物一键生成");
  addFooter(s, 6);

  // 左：方案能力
  addCard(s, MARGIN, 1.6, 5.4, 4.9, C.light);
  s.addText("方案生成与迭代", { x: MARGIN + 0.2, y: 1.72, w: 5.0, h: 0.35, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const design = [
    ["DesignerAgent", "3 套平面布局 + 动线分析（空间推理）"],
    ["讨论式方案", "2-3 套方案 + 语音增量修订（\"方案 B 加中岛\"）"],
    ["分空间设计器 ×11", "厨房/卫浴/硬装/软装/灯光/家具/家电/门窗/定制/土建/机电"],
    ["施工图自动生成", "模型即图纸：平/立/剖面 SVG 自动重生成"],
    ["BIM / IFC 导出", "IFC4 真实坐标 + Pset 属性（GB 50500/50854）"],
    ["AI 渲染 L0-L3", "ControlNet → mock → 占位 → 503 诚实降级"],
    ["VR 全景漫游", "全景图 + 热点 + 场景组合"],
  ];
  design.forEach((dd, i) => {
    s.addText(dd[0], { x: MARGIN + 0.2, y: 2.12 + i * 0.6, w: 2.0, h: 0.3, fontSize: 10, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(dd[1], { x: MARGIN + 2.2, y: 2.12 + i * 0.6, w: 3.0, h: 0.55, fontSize: 9, color: C.gray, fontFace: FONT });
  });

  // 右：交付物流
  s.addText("一次任务 · 全套交付物", { x: 6.4, y: 1.6, w: 6, h: 0.35, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const deliverables = [
    { t: "方案布局图", d: "平面 + 动线 + 3D 户型", c: C.primary },
    { t: "施工图纸", d: "平/立/剖面 SVG（模型即图纸）", c: C.primary600 },
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

  s.addText("对标：飞流AI 上传户型图 5 分钟出全套交付物 —— 索克以开放 MCP 协议 + 多 Agent 编排实现同等闭环，且能力可组合、可迁移", {
    x: MARGIN, y: 6.6, w: 12.1, h: 0.35, fontSize: 11, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P7 Skill 工程化
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Skill Engineering", "Skill 工程化：ihome-mcp 能力抽象层");
  addFooter(s, 7);

  s.addText("ihome-mcp（核心 Skill，5+ Worker 复用）", {
    x: MARGIN, y: 1.6, w: 6, h: 0.4, fontSize: 16, color: C.dark, fontFace: FONT, bold: true,
  });
  const sk = [
    { k: "类型", v: "自定义 Skill — 外部系统集成能力封装" },
    { k: "输入", v: "list / call <tool> <JSON 参数>" },
    { k: "输出", v: "MCP JSON-RPC 响应（含 source 来源标注）" },
    { k: "调用条件", v: "Worker 需项目设计/预算/物料/施工/质检数据时" },
    { k: "依赖", v: "i-home.life MCP Server（2026-07-28 规范）+ PASETO" },
    { k: "失败处理", v: "登录/调用失败返回 error JSON，如实说明不编造" },
    { k: "安全边界", v: "凭据 .env 600 权限；只读为主；红线拒绝" },
    { k: "复用价值", v: "5+ Worker 复用；可沉淀为分发 Skill 包" },
  ];
  sk.forEach((row, i) => {
    const y = 2.1 + i * 0.56;
    addCard(s, MARGIN, y, 6.0, 0.46, C.light);
    s.addText(row.k, { x: MARGIN + 0.15, y: y + 0.06, w: 1.4, h: 0.34, fontSize: 11.5, color: C.primary, fontFace: FONT, bold: true });
    s.addText(row.v, { x: MARGIN + 1.6, y: y + 0.06, w: 4.3, h: 0.34, fontSize: 10.5, color: C.ink, fontFace: FONT });
  });

  s.addText("MCP 工具能力矩阵（10 个）", {
    x: 7.0, y: 1.6, w: 5.7, h: 0.4, fontSize: 16, color: C.dark, fontFace: FONT, bold: true,
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
  ];
  const toolChip = { design: { bg: C.primary50, fg: C.primary600 }, budget: { bg: "D9E9FF", fg: C.primary600 }, procurement: { bg: C.info50, fg: C.info }, construction: { bg: C.success50, fg: C.success }, qa: { bg: C.warning50, fg: C.warning }, orchestration: { bg: "F0F0F2", fg: C.dark } };
  tools.forEach((t, i) => {
    const y = 2.1 + i * 0.42;
    s.addText(t[0], { x: 7.0, y, w: 2.9, h: 0.34, fontSize: 10, color: C.ink, fontFace: "Consolas", bold: true });
    s.addText(t[1], { x: 9.95, y, w: 1.6, h: 0.34, fontSize: 10, color: C.gray, fontFace: FONT });
    s.addShape(pptx.ShapeType.roundRect, {
      x: 11.6, y: y + 0.02, w: 1.35, h: 0.3, fill: { color: toolChip[t[2]].bg }, rectRadius: 0.15,
    });
    s.addText(t[2], { x: 11.6, y: y + 0.05, w: 1.35, h: 0.26, fontSize: 8.5, color: toolChip[t[2]].fg, fontFace: FONT, bold: true, align: "center" });
  });
}

// ════════════════════════════════════════════════════════
// P8 MCP 2026-07-28 规范 8 项
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "MCP Integration", "MCP 工具连接层：2026-07-28 规范 8 项全实现");
  addFooter(s, 8);

  const specs = [
    { t: "stateless", d: "无会话握手，请求自描述可横向扩展" },
    { t: "server/discover", d: "能力发现 RPC，统一接入入口" },
    { t: "header-routing", d: "Mcp-Method / Mcp-Name 头路由" },
    { t: "cacheable", d: "tools/list ETag/304 缓存语义" },
    { t: "MRTR", d: "多轮往返协作，采样/追问回传" },
    { t: "RFC 9207 + CIMD", d: "授权硬化，替代 DCR 注册" },
    { t: "Tasks", d: "tasks/* 扩展，任务生命周期" },
    { t: "Server Card", d: ".well-known/mcp 标准化发现" },
  ];
  specs.forEach((sp, i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    const x = MARGIN + col * 3.1;
    const y = 1.65 + row * 1.85;
    addCard(s, x, y, 2.9, 1.6, C.primary50);
    s.addText(sp.t, { x: x + 0.18, y: y + 0.14, w: 2.55, h: 0.4, fontSize: 13.5, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(sp.d, { x: x + 0.18, y: y + 0.58, w: 2.58, h: 0.9, fontSize: 10, color: C.gray, fontFace: FONT });
  });

  s.addText("Worker 调用链路：ihome-mcp Skill → POST /api/mcp（JSON-RPC 2.0 + Bearer PASETO）→ tools/call → 真实业务数据（source 透明标注）", {
    x: MARGIN, y: 6.4, w: 12.1, h: 0.5, fontSize: 12.5, color: C.dark, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P9 可观测与评估
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Observability & Eval", "可观测三支柱 + 领域评估体系");
  addFooter(s, 9);

  const pillars = [
    { t: "Trace 链路", d: "OTel 追踪 + AgentHarness 执行轨迹（状态/Token/工具调用链/降级信息）", c: C.primary },
    { t: "Log 日志", d: "structlog 结构化 JSON，PII 脱敏 + trace_id 关联", c: C.info },
    { t: "Metrics 指标", d: "Prometheus：请求/LLM 调用/DB 查询/缓存命中率", c: C.success },
  ];
  pillars.forEach((p, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 1.65, 3.9, 1.9, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.65, w: 3.9, h: 0.09, fill: { color: p.c } });
    s.addText(p.t, { x: x + 0.2, y: 1.85, w: 3.5, h: 0.4, fontSize: 14.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(p.d, { x: x + 0.2, y: 2.3, w: 3.55, h: 1.1, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  s.addText("IHomeEval 领域评估（10 维度）", {
    x: MARGIN, y: 3.85, w: 6, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true,
  });
  const dims = [
    ["报价准确性", "设计安全", "材料禁忌", "越权防护", "流式延迟"],
    ["降级率", "工具调用准确率", "思维链泄漏率", "HC 合规率", "反面论证质量"],
  ];
  dims.forEach((row, r) => {
    row.forEach((dm, i) => {
      const x = MARGIN + i * 2.46;
      const y = 4.35 + r * 0.6;
      addCard(s, x, y, 2.3, 0.46, C.success50);
      s.addText(dm, { x, y: y + 0.06, w: 2.3, h: 0.34, fontSize: 10.5, color: C.success, fontFace: FONT, bold: true, align: "center" });
    });
  });

  s.addText("诚实降级原则：数据来源 db / estimated_fallback / sample_fallback 透明标注，禁止伪装真实能力（历史教训：修复 6 处硬编码假数据）", {
    x: MARGIN, y: 5.85, w: 12.1, h: 0.6, fontSize: 11.5, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P10 安全与审计
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Security & Audit", "安全边界：可运行、可验证、可审计");
  addFooter(s, 10);

  const secs = [
    { t: "PASETO v4.local 鉴权", d: "非 JWT；密钥 ≥32 字节硬校验；Worker 仅持消费令牌，真实凭证由 Higress 网关托管", c: C.primary },
    { t: "HMAC 审计防篡改", d: "audit_log 写入自动签名（SHA256 + 密钥版本化），批量完整性校验，PII 脱敏", c: C.info },
    { t: "缓存用户隔离", d: "私有数据 cache key 强制含 user_id，未传直接 raise（cache_user_isolation_strict）", c: C.success },
    { t: "审批与回滚", d: "变更单状态机审批；高风险动作人工确认；DB 备份回滚 + feature-flag 回退", c: C.warning },
    { t: "HC 硬约束", d: "承重墙 / 报价含税 / 环保等级 / 工期缓冲 / 水电 / 逃生通道 / 燃气安全", c: C.error },
    { t: "RBAC 权限", d: "角色-权限表 + 项目归属校验（IDOR 防护），跨项目访问 403", c: C.dark },
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
// P11 运行验证与 Demo
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Running Demo", "运行验证：线上部署已实测打通");
  addFooter(s, 11);

  addCard(s, MARGIN, 1.6, 5.9, 2.35, C.dark);
  s.addText("部署环境（已在线）", { x: MARGIN + 0.25, y: 1.78, w: 5.4, h: 0.4, fontSize: 14.5, color: C.white, fontFace: FONT, bold: true });
  const deploys = [
    "AgentTeams v1.2.0（controller / manager / dashboard / Element Web）",
    "i-home.life v1.3.1（FastAPI · 118.31.223.213:8081）",
    "家装团队 ihome-team：1 Leader + 5 Worker 全部 Running",
    "演示数据：120 平三居 · 预算 ¥157,250 · 4 施工任务",
  ];
  deploys.forEach((dd, i) => {
    s.addText("•  " + dd, { x: MARGIN + 0.25, y: 2.25 + i * 0.42, w: 5.5, h: 0.36, fontSize: 10.5, color: "CCE4FF", fontFace: FONT });
  });

  addCard(s, 6.8, 1.6, 5.9, 2.35, C.primary50);
  s.addText("实测调用链路（已验证）", { x: 7.05, y: 1.78, w: 5.4, h: 0.4, fontSize: 14.5, color: C.primary600, fontFace: FONT, bold: true });
  const flow = [
    "ihome-budget → get_budget → 三档预算 + source 标注 ✅",
    "ihome-construction → get_construction_progress → 8 阶段进度 ✅",
    "ihome-procurement → search_materials → 物料列表 ✅",
    "tools/list → 10 个家装工具可发现 ✅",
  ];
  flow.forEach((ff, i) => {
    s.addText("•  " + ff, { x: 7.05, y: 2.25 + i * 0.42, w: 5.5, h: 0.36, fontSize: 10.5, color: C.ink, fontFace: FONT });
  });

  s.addText("Demo 演示流程：业主在 Element Web 下达任务 → Manager 拆解 → 5 Worker 并行经 MCP 取数 → 汇总装修全案", {
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
// P12 开放/开源计划
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Open Source", "开放/开源计划：可复用、可验证、可迁移");
  addFooter(s, 12);

  const items = [
    { t: "AgentTeams Worker 模板", d: "SOUL.md + Agent Identity 清单，任何垂直行业可复制建团", c: C.primary },
    { t: "ihome-mcp Skill", d: "标准化工具调用封装（登录/调用/失败处理），可分发复用", c: C.info },
    { t: "MCP 适配层", d: "2026-07-28 规范实现，可作为 MCP Server 接入参考实现", c: C.success },
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
  s.addText("仓库：github.com/SUOKE2024/i-home.life（已公开）", {
    x: MARGIN + 0.25, y: 5.75, w: 11.6, h: 0.35, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true,
  });
  s.addText("协议 Apache-2.0（与 AgentTeams 兼容）｜ 披露：LLM 商业 API（deepseek/qwen/glm/doubao）· 第三方依赖 · 数据授权边界 ｜ 已有项目基础：i-home.life（23 Agent / 60 API / 90 Service）", {
    x: MARGIN + 0.25, y: 6.15, w: 11.6, h: 0.55, fontSize: 10.5, color: C.gray, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P13 落地计划与风险
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Roadmap & Risks", "落地计划与风险应对");
  addFooter(s, 13);

  const phases = [
    { v: "V1 初赛", t: "方案 + 链路验证", d: "AgentTeams 部署、Worker 建团、MCP 调用链路、能力全景梳理 ✅ 已完成", c: C.success },
    { v: "V1.5 复赛", t: "完整闭环 Demo", d: "Element Web 全流程演示、评估数据集、Trace 看板、真实项目数据", c: C.primary },
    { v: "V2 决赛", t: "真实项目试点", d: "接入真实家装项目、LLM-as-Judge 评测、开源工程化、行业复制", c: C.warning },
  ];
  phases.forEach((ph, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 1.65, 3.9, 3.3, C.light);
    s.addShape(pptx.ShapeType.roundRect, { x, y: 1.65, w: 3.9, h: 0.62, fill: { color: ph.c }, rectRadius: 0 });
    s.addText(ph.v, { x, y: 1.75, w: 3.9, h: 0.4, fontSize: 16, color: C.white, fontFace: FONT, bold: true, align: "center" });
    s.addText(ph.t, { x: x + 0.2, y: 2.5, w: 3.5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
    s.addText(ph.d, { x: x + 0.2, y: 2.95, w: 3.55, h: 1.8, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  s.addText("风险与应对", { x: MARGIN, y: 5.25, w: 6, h: 0.4, fontSize: 14.5, color: C.dark, fontFace: FONT, bold: true });
  const risks = [
    "部分能力为诚实标注的 mock（质检缺陷 CV/VR 渲染/AI 渲染 L1/L2）→ 如实披露，作为工程边界而非隐藏",
    "AgentTeams 版本演进（v1.2.0 刚发布）→ 抽象 MCP 契约层，编排层可替换",
    "LLM 成本与不可用 → 多供应商 fallback 链（deepseek→qwen→glm→doubao）",
  ];
  risks.forEach((rk, i) => {
    addCard(s, MARGIN, 5.7 + i * 0.46, 12.1, 0.38, C.warning50);
    s.addText("•  " + rk, { x: MARGIN + 0.2, y: 5.74 + i * 0.46, w: 11.7, h: 0.3, fontSize: 10, color: C.ink, fontFace: FONT });
  });
}

// ── 校验：重叠与越界 ──
pptx.writeFile({ fileName: "GOAI初赛-家装全流程多Agent协同系统.pptx" }).then(() => {
  console.log("✅ PPT 已生成");
  for (let i = 0; i < pptx.slides.length; i++) {
    const slide = pptx.slides[i];
    helpers.warnIfSlideHasOverlaps(slide, pptx);
    helpers.warnIfSlideElementsOutOfBounds(slide, pptx);
  }
});
