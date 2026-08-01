// GOAI 赛道一 · Agent Infra — 初赛方案 PPT
// 家装全流程多 Agent 协同系统（基于 AgentTeams + i-home.life MCP）
// 全新设计：索克蓝主题 · 16:9 · 12 页
"use strict";

const PptxGenJS = require("pptxgenjs");
const helpers = require("./index.js");

const pptx = new PptxGenJS();
pptx.defineLayout({ name: "WIDE", width: 13.333, height: 7.5 });
pptx.layout = "WIDE";

// ── 品牌色板（索克家居 design tokens）──
const C = {
  dark: "001833", // soke-primary-900 深蓝
  primary: "007aff", // 索克蓝 accent
  primary600: "0062cc",
  primary200: "99c9ff",
  primary50: "e8f2ff",
  ink: "1d1d1f", // 中性 900
  gray: "6e6e73", // 中性 600
  light: "f5f5f7", // 中性 100
  white: "FFFFFF",
  success: "28a745",
  success50: "e8f8ee",
  warning: "ff9500",
  warning50: "fff8e8",
  error: "ff3b30",
  error50: "fce8e8",
  info: "5ac8fa",
  info50: "e8f5fc",
};

const FONT = "Microsoft YaHei";
const W = 13.333;
const H = 7.5;
const MARGIN = 0.6;

// ── 通用 helpers ──
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
    x: MARGIN + 0.22, y: 0.42, w: 8, h: 0.28, fontSize: 11, color: C.primary, fontFace: FONT, bold: true, charSpacing: 2,
  });
  slide.addText(title, {
    x: MARGIN + 0.22, y: 0.7, w: 11, h: 0.55, fontSize: 24, color: C.dark, fontFace: FONT, bold: true,
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
  // 装饰：右上大圆 + 左下小圆（氛围元素；有意部分越界，避开文字区）
  s.addShape(pptx.ShapeType.ellipse, { x: 11.4, y: -3.0, w: 4.0, h: 4.0, fill: { color: "003166" }, line: { type: "none" } });
  s.addShape(pptx.ShapeType.ellipse, { x: -2.6, y: 6.1, w: 3.2, h: 3.2, fill: { color: "003166" }, line: { type: "none" } });
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.14, h: H, fill: { color: C.primary } });

  s.addText("GOAI 2026 · 赛道一 新智基座 | Agent Infra", {
    x: 0.9, y: 1.0, w: 9, h: 0.4, fontSize: 14, color: C.primary200, fontFace: FONT, bold: true, charSpacing: 3,
  });
  s.addText("家装全流程多 Agent 协同系统", {
    x: 0.9, y: 1.55, w: 11.5, h: 1.2, fontSize: 44, color: C.white, fontFace: FONT, bold: true,
  });
  s.addText("让 AgentTeams 编排与 MCP 工具链驱动家装项目从设计到结算的端到端自动化", {
    x: 0.9, y: 2.85, w: 10.5, h: 0.5, fontSize: 17, color: "CCE4FF", fontFace: FONT,
  });

  // 三层架构标签（封面亮点）
  const layers = [
    { t: "AgentTeams 编排层", d: "Manager-Workers · Matrix 透明协作", c: C.primary },
    { t: "Skill 能力层", d: "ihome-mcp · 登录鉴权 · 失败处理 · 复用", c: C.info },
    { t: "MCP 工具连接层", d: "2026-07-28 规范 8 项 · 10 个工具", c: C.success },
  ];
  layers.forEach((L, i) => {
    const x = 0.9 + i * 3.9;
    s.addShape(pptx.ShapeType.roundRect, {
      x, y: 4.15, w: 3.55, h: 1.35, fill: { color: "003166" }, line: { color: C.primary600, width: 1 }, rectRadius: 0.08,
    });
    s.addShape(pptx.ShapeType.rect, { x, y: 4.15, w: 0.07, h: 1.35, fill: { color: L.c } });
    s.addText(L.t, { x: x + 0.25, y: 4.32, w: 3.1, h: 0.4, fontSize: 15, color: C.white, fontFace: FONT, bold: true });
    s.addText(L.d, { x: x + 0.25, y: 4.75, w: 3.15, h: 0.6, fontSize: 11, color: "99C9FF", fontFace: FONT });
  });

  s.addText("队伍：索克家居 · i-home.life ｜ 基于 AgentTeams（agentscope-ai/AgentTeams）与 i-home.life v1.3.1", {
    x: 0.9, y: 6.35, w: 11, h: 0.4, fontSize: 12, color: "66ADFF", fontFace: FONT,
  });
  s.addText("2026 · 初赛 V1.0", {
    x: 0.9, y: 6.75, w: 4, h: 0.35, fontSize: 11, color: "66ADFF", fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P2 场景与价值
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Scene & Value", "场景与价值：家装复杂任务需要 Agent 团队");
  addFooter(s, 2);

  // 痛点卡（左）
  const pains = [
    { t: "链条长 · 专业割裂", d: "设计/预算/采购/施工/质检五大环节分属不同专业，跨部门信息靠人传话" },
    { t: "决策黑盒 · 结果难溯", d: "报价构成、方案依据、质量结论缺乏结构化证据，纠纷难举证" },
    { t: "经验难规模化", d: "资深项目经理的诊断与排期经验沉淀在个人脑中，无法复制" },
  ];
  pains.forEach((p, i) => {
    const y = 1.65 + i * 1.42;
    addCard(s, MARGIN, y, 5.5, 1.22, C.light);
    addAccentBar(s, MARGIN, y, 0.28, C.error);
    s.addText(p.t, { x: MARGIN + 0.25, y: y + 0.12, w: 5.0, h: 0.38, fontSize: 15, color: C.ink, fontFace: FONT, bold: true });
    s.addText(p.d, { x: MARGIN + 0.25, y: y + 0.52, w: 5.05, h: 0.6, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  // 方案价值（右）
  const vals = [
    { k: "5 个职能 Agent", d: "设计师 / 预算师 / 采购员 / 施工经理 / 质检员 端到端协同" },
    { k: "MCP 规范 8 项", d: "2026-07-28 规范全实现，工具接入标准化、可迁移" },
    { k: "全程可审计", d: "Matrix 房间 + HMAC 审计签名 + 诚实数据来源标注" },
  ];
  vals.forEach((v, i) => {
    const y = 1.65 + i * 1.42;
    addCard(s, 6.5, y, 6.2, 1.22, C.primary50);
    addAccentBar(s, 6.5, y, 0.28, C.primary);
    s.addText(v.k, { x: 6.75, y: y + 0.12, w: 5.8, h: 0.38, fontSize: 15, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(v.d, { x: 6.75, y: y + 0.52, w: 5.85, h: 0.6, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  // 底部可复制性
  addCard(s, MARGIN, 6.05, 12.1, 0.85, C.dark);
  s.addText("行业可复制性：设计→预算→采购→施工→质检是工程、公装、地产、物业共通的流程范式，Agent 团队可平移到任一垂直行业", {
    x: MARGIN + 0.25, y: 6.2, w: 11.6, h: 0.55, fontSize: 13, color: C.white, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P3 系统总体架构
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Architecture", "系统架构：AgentTeams 编排 × Skill 能力 × MCP 工具三层解耦");
  addFooter(s, 3);

  const layers = [
    { name: "用户入口", sub: "Element Web（Matrix 客户端）/ Web 控制台 / 语音", color: C.gray, h: 0.5 },
    { name: "AgentTeams 编排层", sub: "Manager-Workers · 任务拆解 · 状态流转 · 路由与升级 · Matrix 透明房间", color: C.primary, h: 0.72 },
    { name: "多 Agent 协同层", sub: "ihome-manager ｜ designer · budget · procurement · construction · qa", color: C.primary600, h: 0.72 },
    { name: "Skill 能力层", sub: "ihome-mcp：PASETO 登录 → tools/list → tools/call · Schema · 失败处理", color: C.info, h: 0.72 },
    { name: "MCP 工具连接层", sub: "i-home.life MCP Server · 2026-07-28 规范 8 项 · 10 个家装工具", color: C.success, h: 0.72 },
    { name: "业务数据层", sub: "项目 / 预算 / 物料 / 施工 / 质检 · 50 ORM 模型 · 74+ API 路由", color: C.gray, h: 0.72 },
  ];

  let y = 1.6;
  layers.forEach((L, i) => {
    // 左侧色块层
    s.addShape(pptx.ShapeType.roundRect, {
      x: MARGIN, y, w: 12.1, h: L.h, fill: { color: i % 2 === 0 ? C.white : C.light },
      line: { color: "E0E0E6", width: 1 }, rectRadius: 0.05,
    });
    s.addShape(pptx.ShapeType.rect, { x: MARGIN, y, w: 0.1, h: L.h, fill: { color: L.color } });
    s.addText(L.name, { x: MARGIN + 0.3, y: y + 0.08, w: 3.35, h: 0.38, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
    s.addText(L.sub, { x: 4.35, y: y + (L.h - 0.34) / 2, w: 7.85, h: 0.34, fontSize: 10.5, color: C.gray, fontFace: FONT, valign: "mid" });
    y += L.h + 0.08;
  });
}

// ════════════════════════════════════════════════════════
// P4 多 Agent 角色编排
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Agent Identity", "多 Agent 设计：1 个 Leader + 5 个职能 Worker");
  addFooter(s, 4);

  const agents = [
    { n: "ihome-manager", r: "Team Leader 编排者", d: "任务拆解 · 路由分派 · 进度监控 · 异常升级", c: C.dark },
    { n: "ihome-designer", r: "方案设计专家", d: "布局规划 · 设计提案生成/更新", c: C.primary },
    { n: "ihome-budget", r: "预算成本专家", d: "预算编制 · 成本分析 · 超支预警", c: C.primary600 },
    { n: "ihome-procurement", r: "物料采购专家", d: "物料搜索 · 比价分析 · 采购计划", c: C.info },
    { n: "ihome-construction", r: "施工进度专家", d: "进度跟踪 · 工期管理 · 工序协调", c: C.success },
    { n: "ihome-qa", r: "质量检测专家", d: "阶段质检 · 标准核验 · 缺陷识别", c: C.warning },
  ];

  agents.forEach((a, i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    const x = MARGIN + col * 4.18;
    const y = 1.6 + row * 2.6;
    addCard(s, x, y, 3.9, 2.35, C.light);
    s.addShape(pptx.ShapeType.roundRect, { x, y, w: 3.9, h: 0.55, fill: { color: a.c }, rectRadius: 0 });
    s.addText(a.n, { x, y: y + 0.07, w: 3.9, h: 0.4, fontSize: 14, color: C.white, fontFace: FONT, bold: true, align: "center" });
    s.addText(a.r, { x: x + 0.2, y: y + 0.72, w: 3.5, h: 0.38, fontSize: 13, color: C.dark, fontFace: FONT, bold: true });
    s.addText(a.d, { x: x + 0.2, y: y + 1.15, w: 3.5, h: 1.05, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  s.addText("任务示例：\"120 平三居室装修\" → Manager 拆解 → 设计提案 / 预算编制 / 物料清单 / 施工计划 / 质检计划", {
    x: MARGIN, y: 6.55, w: 12.1, h: 0.5, fontSize: 12.5, color: C.primary600, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P5 上下文传递与协同执行
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Collaboration", "上下文传递与协同执行：映射 AgentTeams 原生能力");
  addFooter(s, 5);

  const steps = [
    { n: "01", t: "任务输入", d: "业主/公司以自然语言下达复杂任务", c: C.primary },
    { n: "02", t: "任务拆解", d: "Manager 拆解为可执行子任务并按能力路由", c: C.primary600 },
    { n: "03", t: "协同执行", d: "Worker 在 Matrix 房间并行执行、汇报进度", c: C.info },
    { n: "04", t: "工具调用", d: "Worker 经 ihome-mcp Skill 调 MCP 取真实数据", c: C.success },
    { n: "05", t: "结果验证", d: "Manager 汇总、校验，输出证据链", c: C.warning },
    { n: "06", t: "证据沉淀", d: "全程留痕：房间消息 + 审计日志 + 数据来源", c: C.error },
  ];
  steps.forEach((st, i) => {
    const x = MARGIN + i * 1.97;
    addCard(s, x, 1.7, 1.75, 3.3, C.light);
    s.addText(st.n, { x: x + 0.12, y: 1.85, w: 1.5, h: 0.5, fontSize: 24, color: st.c, fontFace: FONT, bold: true });
    s.addText(st.t, { x: x + 0.12, y: 2.55, w: 1.5, h: 0.4, fontSize: 13.5, color: C.dark, fontFace: FONT, bold: true });
    s.addText(st.d, { x: x + 0.12, y: 3.0, w: 1.52, h: 1.85, fontSize: 10, color: C.gray, fontFace: FONT });
    if (i < 5) {
      s.addText("→", { x: x + 1.80, y: 2.9, w: 0.16, h: 0.5, fontSize: 13, color: C.primary, fontFace: FONT, align: "center" });
    }
  });

  // 底部三大机制
  const mech = [
    { t: "Matrix 透明房间", d: "人与 Agent 同房间，随时介入/纠正，全程可回放" },
    { t: "MinIO 共享文件", d: "中间产物走共享文件系统，避免 Token 爆炸" },
    { t: "Human-in-the-Loop", d: "高风险动作人工确认，安全边界内置" },
  ];
  mech.forEach((m, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 5.35, 3.9, 1.15, C.primary50);
    s.addText(m.t, { x: x + 0.2, y: 5.48, w: 3.5, h: 0.35, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(m.d, { x: x + 0.2, y: 5.85, w: 3.55, h: 0.55, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });
}

// ════════════════════════════════════════════════════════
// P6 Skill 工程化
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Skill Engineering", "Skill 工程化：ihome-mcp 能力抽象层");
  addFooter(s, 6);

  // 左侧：Skill 结构
  s.addText("ihome-mcp（核心 Skill，5 Worker 复用）", {
    x: MARGIN, y: 1.6, w: 6, h: 0.4, fontSize: 16, color: C.dark, fontFace: FONT, bold: true,
  });
  const sk = [
    { k: "类型", v: "自定义 Skill — 外部系统集成能力封装" },
    { k: "输入", v: "list / call <tool> <JSON 参数>" },
    { k: "输出", v: "MCP JSON-RPC 响应（含 source 数据来源标注）" },
    { k: "调用条件", v: "Worker 需项目设计/预算/物料/施工/质检数据时" },
    { k: "依赖", v: "i-home.life MCP Server（2026-07-28 规范）+ PASETO" },
    { k: "失败处理", v: "登录/调用失败返回 error JSON，如实说明不编造" },
    { k: "安全边界", v: "凭据 .env 600 权限；只读为主；红线拒绝" },
    { k: "复用价值", v: "5 Worker 复用；可沉淀为分发 Skill 包" },
  ];
  sk.forEach((row, i) => {
    const y = 2.1 + i * 0.56;
    addCard(s, MARGIN, y, 6.0, 0.46, C.light);
    s.addText(row.k, { x: MARGIN + 0.15, y: y + 0.06, w: 1.4, h: 0.34, fontSize: 11.5, color: C.primary, fontFace: FONT, bold: true });
    s.addText(row.v, { x: MARGIN + 1.6, y: y + 0.06, w: 4.3, h: 0.34, fontSize: 11, color: C.ink, fontFace: FONT });
  });

  // 右侧：工具能力矩阵
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
    s.addText(t[0], { x: 7.0, y, w: 2.9, h: 0.34, fontSize: 10.5, color: C.ink, fontFace: "Consolas", bold: true });
    s.addText(t[1], { x: 9.95, y, w: 1.6, h: 0.34, fontSize: 10.5, color: C.gray, fontFace: FONT });
    s.addShape(pptx.ShapeType.roundRect, {
      x: 11.6, y: y + 0.02, w: 1.35, h: 0.3, fill: { color: toolChip[t[2]].bg }, rectRadius: 0.15,
    });
    s.addText(t[2], { x: 11.6, y: y + 0.05, w: 1.35, h: 0.26, fontSize: 9, color: toolChip[t[2]].fg, fontFace: FONT, bold: true, align: "center" });
  });
}

// ════════════════════════════════════════════════════════
// P7 MCP 与工具集成
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "MCP Integration", "MCP 工具连接层：2026-07-28 规范 8 项全实现");
  addFooter(s, 7);

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
    s.addText(sp.t, { x: x + 0.18, y: y + 0.14, w: 2.55, h: 0.4, fontSize: 14, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(sp.d, { x: x + 0.18, y: y + 0.58, w: 2.58, h: 0.9, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  s.addText("Worker 调用链路：ihome-mcp Skill → POST /api/mcp（JSON-RPC 2.0 + Bearer PASETO）→ tools/call → 真实业务数据（source 透明标注）", {
    x: MARGIN, y: 6.4, w: 12.1, h: 0.5, fontSize: 12.5, color: C.dark, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P8 可观测与评估
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Observability & Eval", "可观测三支柱 + 领域评估体系");
  addFooter(s, 8);

  const pillars = [
    { t: "Trace 链路", d: "OTel 追踪 + AgentHarness 执行轨迹（状态/Token/工具调用链/降级信息）", c: C.primary },
    { t: "Log 日志", d: "structlog 结构化 JSON，PII 脱敏 + trace_id 关联", c: C.info },
    { t: "Metrics 指标", d: "Prometheus：请求/LLM 调用/DB 查询/缓存命中率", c: C.success },
  ];
  pillars.forEach((p, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 1.65, 3.9, 1.9, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.65, w: 3.9, h: 0.09, fill: { color: p.c } });
    s.addText(p.t, { x: x + 0.2, y: 1.85, w: 3.5, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true });
    s.addText(p.d, { x: x + 0.2, y: 2.3, w: 3.55, h: 1.1, fontSize: 11, color: C.gray, fontFace: FONT });
  });

  s.addText("IHomeEval 领域评估（10 维度）", {
    x: MARGIN, y: 3.85, w: 6, h: 0.4, fontSize: 16, color: C.dark, fontFace: FONT, bold: true,
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
      s.addText(dm, { x, y: y + 0.06, w: 2.3, h: 0.34, fontSize: 11, color: C.success, fontFace: FONT, bold: true, align: "center" });
    });
  });

  s.addText("诚实降级原则：数据来源 db / estimated_fallback / sample_fallback 透明标注，禁止伪装真实能力（历史教训：修复 6 处硬编码假数据）", {
    x: MARGIN, y: 5.85, w: 12.1, h: 0.6, fontSize: 12, color: C.gray, fontFace: FONT, align: "center",
  });
}

// ════════════════════════════════════════════════════════
// P9 安全与审计
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Security & Audit", "安全边界：可运行、可验证、可审计");
  addFooter(s, 9);

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
    s.addText(sc.d, { x: x + 0.8, y: y + 0.6, w: 4.95, h: 0.8, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });
}

// ════════════════════════════════════════════════════════
// P10 运行验证与 Demo
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Running Demo", "运行验证：线上部署已实测打通");
  addFooter(s, 10);

  // 部署信息
  addCard(s, MARGIN, 1.6, 5.9, 2.35, C.dark);
  s.addText("部署环境（已在线）", { x: MARGIN + 0.25, y: 1.78, w: 5.4, h: 0.4, fontSize: 15, color: C.white, fontFace: FONT, bold: true });
  const deploys = [
    "AgentTeams v1.2.0（controller / manager / dashboard / Element Web）",
    "i-home.life v1.3.1（FastAPI · 118.31.223.213:8081）",
    "家装团队 ihome-team：1 Leader + 5 Worker 全部 Running",
    "演示数据：120 平三居 · 预算 ¥157,250 · 4 施工任务",
  ];
  deploys.forEach((dd, i) => {
    s.addText("•  " + dd, { x: MARGIN + 0.25, y: 2.25 + i * 0.42, w: 5.5, h: 0.36, fontSize: 11, color: "CCE4FF", fontFace: FONT });
  });

  // 实测链路
  addCard(s, 6.8, 1.6, 5.9, 2.35, C.primary50);
  s.addText("实测调用链路（已验证）", { x: 7.05, y: 1.78, w: 5.4, h: 0.4, fontSize: 15, color: C.primary600, fontFace: FONT, bold: true });
  const flow = [
    "ihome-budget → get_budget → 三档预算 + source 标注 ✅",
    "ihome-construction → get_construction_progress → 8 阶段进度 ✅",
    "ihome-procurement → search_materials → 物料列表 ✅",
    "tools/list → 10 个家装工具可发现 ✅",
  ];
  flow.forEach((ff, i) => {
    s.addText("•  " + ff, { x: 7.05, y: 2.25 + i * 0.42, w: 5.5, h: 0.36, fontSize: 11, color: C.ink, fontFace: FONT });
  });

  // 演示流程
  s.addText("Demo 演示流程：业主在 Element Web 下达任务 → Manager 拆解 → 5 Worker 并行经 MCP 取数 → 汇总装修全案", {
    x: MARGIN, y: 4.15, w: 12.1, h: 0.5, fontSize: 14, color: C.dark, fontFace: FONT, bold: true, align: "center",
  });
  const demo = ["① 输入任务", "② Manager 拆解", "③ Worker 执行", "④ MCP 取数", "⑤ 汇总验证"];
  demo.forEach((dd, i) => {
    const x = MARGIN + i * 2.5;
    addCard(s, x, 4.8, 2.3, 1.5, C.light);
    addAccentBar(s, x, 4.8, 2.3, C.primary);
    s.addText(dd, { x, y: 5.25, w: 2.3, h: 0.6, fontSize: 13, color: C.dark, fontFace: FONT, bold: true, align: "center" });
  });
}

// ════════════════════════════════════════════════════════
// P11 开放/开源计划
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Open Source", "开放/开源计划：可复用、可验证、可迁移");
  addFooter(s, 11);

  const items = [
    { t: "Worker 模板", d: "SOUL.md + Agent Identity 清单，任何垂直行业可复制建团", c: C.primary },
    { t: "ihome-mcp Skill", d: "标准化工具调用封装（登录/调用/失败处理），可分发复用", c: C.info },
    { t: "MCP 适配层", d: "2026-07-28 规范实现，可作为 MCP Server 接入参考实现", c: C.success },
    { t: "演示数据集", d: "家装场景样例输入输出 + 评测基线", c: C.warning },
  ];
  items.forEach((it, i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = MARGIN + col * 6.15;
    const y = 1.65 + row * 1.85;
    addCard(s, x, y, 5.9, 1.6, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y, w: 0.1, h: 1.6, fill: { color: it.c } });
    s.addText(it.t, { x: x + 0.3, y: y + 0.18, w: 5.4, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true });
    s.addText(it.d, { x: x + 0.3, y: y + 0.65, w: 5.4, h: 0.8, fontSize: 11, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 5.6, 12.1, 1.2, C.primary50);
  s.addText("仓库：github.com/SUOKE2024/i-home.life（已公开）", {
    x: MARGIN + 0.25, y: 5.75, w: 11.6, h: 0.35, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true,
  });
  s.addText("协议 Apache-2.0（与 AgentTeams 兼容）｜ 披露：LLM 商业 API（deepseek/qwen/glm/doubao）· 第三方依赖 · 数据授权边界 ｜ 已有项目基础：i-home.life（24 Agent / 80+ Service）", {
    x: MARGIN + 0.25, y: 6.15, w: 11.6, h: 0.55, fontSize: 11, color: C.gray, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════
// P12 落地计划与风险
// ════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Roadmap & Risks", "落地计划与风险应对");
  addFooter(s, 12);

  const phases = [
    { v: "V1 初赛", t: "方案 + 链路验证", d: "AgentTeams 部署、5 Worker 建团、MCP 调用链路、演示数据 ✅ 已完成", c: C.success },
    { v: "V1.5 复赛", t: "完整闭环 Demo", d: "Element Web 全流程演示、评估数据集、Trace 看板、安全执行白名单", c: C.primary },
    { v: "V2 决赛", t: "真实项目试点", d: "接入真实家装项目、LLM-as-Judge 评测、开源工程化、行业复制", c: C.warning },
  ];
  phases.forEach((ph, i) => {
    const x = MARGIN + i * 4.18;
    addCard(s, x, 1.65, 3.9, 3.3, C.light);
    s.addShape(pptx.ShapeType.roundRect, { x, y: 1.65, w: 3.9, h: 0.62, fill: { color: ph.c }, rectRadius: 0 });
    s.addText(ph.v, { x, y: 1.75, w: 3.9, h: 0.4, fontSize: 16, color: C.white, fontFace: FONT, bold: true, align: "center" });
    s.addText(ph.t, { x: x + 0.2, y: 2.5, w: 3.5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
    s.addText(ph.d, { x: x + 0.2, y: 2.95, w: 3.55, h: 1.8, fontSize: 11, color: C.gray, fontFace: FONT });
  });

  s.addText("风险与应对", { x: MARGIN, y: 5.25, w: 6, h: 0.4, fontSize: 15, color: C.dark, fontFace: FONT, bold: true });
  const risks = [
    "AgentTeams 版本演进（v1.2.0 刚发布）→ 抽象 MCP 契约层，编排层可替换",
    "LLM 成本与不可用 → 多供应商 fallback 链（deepseek→qwen→glm→doubao）",
    "数据授权边界 → 演示数据自建，业务数据脱敏 + 授权披露",
  ];
  risks.forEach((rk, i) => {
    addCard(s, MARGIN, 5.7 + i * 0.46, 12.1, 0.38, C.warning50);
    s.addText("•  " + rk, { x: MARGIN + 0.2, y: 5.74 + i * 0.46, w: 11.7, h: 0.3, fontSize: 10.5, color: C.ink, fontFace: FONT });
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
