// TERA-Award 2026 智慧家庭专题赛 — 参赛方案 PPT
// 主题：智联万家 · 零碳未来 ｜ 主攻「家庭生活 AI 及智能体」+ 副「家庭安全与用能」
// 基于 i-home.life 真实能力全景（v1.16.x）· 索克蓝主题 · 16:9 · 14 页
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

function addFooter(slide, pageNo, left) {
  slide.addText(left || "TERA-Award 2026 智慧家庭专题赛 ｜ i-home.life ｜ 家庭生活 AI 及智能体", {
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
    x: MARGIN + 0.22, y: 0.7, w: 12, h: 0.55, fontSize: 22, color: C.dark, fontFace: FONT, bold: true,
  });
  slide.addShape(pptx.ShapeType.line, { x: MARGIN, y: 1.35, w: W - 2 * MARGIN, h: 0, line: { color: "E0E0E6", width: 1 } });
}

function addCard(slide, x, y, w, h, fill, line) {
  return slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, fill: { color: fill || C.light }, line: { color: line || "E8E8ED", width: 0.75 }, rectRadius: 0.06,
  });
}

function addBullet(slide, items, x, y, w, h, fontSize, color) {
  const runs = items.map((it) => ({ text: it, options: { bullet: { code: "2022" }, breakLine: true } }));
  slide.addText(runs, { x, y, w, h, fontSize, color: color || C.ink, fontFace: FONT, valign: "top", paraSpaceAfter: 6 });
}

// ════════════════════════════════════════════════════════════════
// P1 封面
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  // 装饰圆已移除（避免越界警告），保留深色背景 + 左侧品牌竖条
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.14, h: H, fill: { color: C.primary } });

  s.addText("TERA-AWARD 2026 · 智慧家庭专题赛 · 智联万家 零碳未来", {
    x: 0.9, y: 0.85, w: 10, h: 0.4, fontSize: 14, color: C.primary200, fontFace: FONT, bold: true, charSpacing: 3,
  });
  s.addText("AI 智能装修管家", {
    x: 0.9, y: 1.4, w: 11.5, h: 1.1, fontSize: 44, color: C.white, fontFace: FONT, bold: true,
  });
  s.addText("从设计到康养疗愈的居家智能体", {
    x: 0.9, y: 2.55, w: 11.5, h: 0.5, fontSize: 20, color: "CCE4FF", fontFace: FONT,
  });
  s.addText("20+ 执行型智能体 × MCP/A2A/ATH 可信互联 × 康养·旅居·疗愈场景联动", {
    x: 0.9, y: 3.15, w: 11.5, h: 0.4, fontSize: 13, color: "66ADFF", fontFace: FONT,
  });

  const layers = [
    { t: "20+ 执行型智能体", d: "设计/预算/采购/施工/验收/结算/康养管家", c: C.primary },
    { t: "可信握手 ATH", d: "九步握手 ④⑤⑦ · 证据链可回放", c: C.info },
    { t: "四大场景", d: "康养 · 旅居 · 疗愈(中医/西医)", c: C.success },
  ];
  layers.forEach((L, i) => {
    const x = 0.9 + i * 3.9;
    s.addShape(pptx.ShapeType.roundRect, { x, y: 4.0, w: 3.55, h: 1.35, fill: { color: "003166" }, line: { color: C.primary600, width: 1 }, rectRadius: 0.08 });
    s.addShape(pptx.ShapeType.rect, { x, y: 4.0, w: 0.07, h: 1.35, fill: { color: L.c } });
    s.addText(L.t, { x: x + 0.25, y: 4.17, w: 3.1, h: 0.4, fontSize: 15, color: C.white, fontFace: FONT, bold: true });
    s.addText(L.d, { x: x + 0.25, y: 4.6, w: 3.15, h: 0.6, fontSize: 10.5, color: "99C9FF", fontFace: FONT });
  });

  s.addText("队伍: 索克家居 · i-home.life ｜ 生产运行 v1.16.x ｜ 主攻「家庭生活 AI 及智能体」", {
    x: 0.9, y: 6.3, w: 11.5, h: 0.35, fontSize: 12, color: "66ADFF", fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════════════
// P2 痛点
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Problem", "三大痛点：家装链路割裂 + 康养缺智能闭环 + 智能体缺信任底座");
  addFooter(s, 2);

  const pains = [
    { t: "链路割裂", d: "设计 / 预算 / 采购 / 施工 / 验收各自为政，信息孤岛，返工率高", c: C.error },
    { t: "康养缺闭环", d: "老龄化加速，康养/疗愈/旅居场景缺「监测→联动→照护」智能闭环", c: C.warning },
    { t: "信任缺失", d: "智能体自主决策缺身份核验 / 授权管控 / 行为审计，难以规模化落地", c: C.primary },
  ];
  pains.forEach((p, i) => {
    const y = 1.6 + i * 1.5;
    addCard(s, MARGIN, y, 12.13, 1.25, C.light);
    s.addShape(pptx.ShapeType.rect, { x: MARGIN, y, w: 0.08, h: 1.25, fill: { color: p.c } });
    s.addText(p.t, { x: MARGIN + 0.3, y: y + 0.14, w: 3, h: 0.4, fontSize: 17, color: C.dark, fontFace: FONT, bold: true });
    s.addText(p.d, { x: MARGIN + 0.3, y: y + 0.58, w: 11.4, h: 0.55, fontSize: 12.5, color: C.gray, fontFace: FONT });
  });
  s.addText("数据锚点：家装平均决策周期长、返工率高；老年空巢 / 康养需求持续攀升（引用行业公开数据）", {
    x: MARGIN, y: 6.15, w: 12, h: 0.4, fontSize: 11, color: C.primary600, fontFace: FONT, bold: true,
  });
}

// ════════════════════════════════════════════════════════════════
// P3 方案总览
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Solution", "方案总览：一个模块化单体，覆盖家装全链路 + 康养延伸");
  addFooter(s, 3);

  const chain = ["设计", "预算", "采购", "施工", "验收", "结算", "管家"];
  chain.forEach((t, i) => {
    const x = MARGIN + i * 1.78;
    s.addShape(pptx.ShapeType.roundRect, { x, y: 1.7, w: 1.55, h: 0.85, fill: { color: i === 6 ? C.primary : C.primary50 }, line: { color: C.primary, width: 1 }, rectRadius: 0.08 });
    s.addText(t, { x, y: 1.95, w: 1.55, h: 0.4, fontSize: 16, color: i === 6 ? C.white : C.primary600, fontFace: FONT, bold: true, align: "center" });
  });

  s.addText("架构分层", { x: MARGIN, y: 3.0, w: 5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const arch = [
    { t: "运行时", d: "Agent Harness · 轨迹落库 · 可观测", c: C.primary },
    { t: "编排层", d: "Orchestrator · 拓扑执行 · 结构化聚合", c: C.info },
    { t: "协议层", d: "MCP(工具) + A2A(智能体间) + ATH(可信握手)", c: C.success },
    { t: "数据层", d: "140 ORM · 项目/健康/设备/证据链", c: C.warning },
  ];
  arch.forEach((a, i) => {
    const y = 3.45 + i * 0.72;
    addCard(s, MARGIN, y, 6.4, 0.6, C.light);
    s.addShape(pptx.ShapeType.rect, { x: MARGIN, y, w: 0.07, h: 0.6, fill: { color: a.c } });
    s.addText(a.t, { x: MARGIN + 0.25, y: y + 0.08, w: 1.3, h: 0.4, fontSize: 13, color: C.dark, fontFace: FONT, bold: true });
    s.addText(a.d, { x: MARGIN + 1.6, y: y + 0.08, w: 4.6, h: 0.4, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  s.addText("四大场景延伸", { x: 7.4, y: 3.0, w: 5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const scenes = [
    { t: "康养", d: "健康监测 → 场景联动", c: C.success },
    { t: "旅居", d: "远程设计 + 远程监测", c: C.info },
    { t: "疗愈·中医", d: "药膳厨房/药浴/艾灸通风", c: C.warning },
    { t: "疗愈·西医", d: "康复空间/护理联动", c: C.error },
  ];
  scenes.forEach((sc, i) => {
    const y = 3.45 + i * 0.72;
    addCard(s, 7.4, y, 5.33, 0.6, C.primary50);
    s.addText(sc.t, { x: 7.55, y: y + 0.08, w: 1.7, h: 0.4, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true });
    s.addText(sc.d, { x: 9.3, y: y + 0.08, w: 3.3, h: 0.4, fontSize: 10, color: C.gray, fontFace: FONT });
  });
}

// ════════════════════════════════════════════════════════════════
// P4 技术底座：可信互联（ATH）
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Trust Foundation", "技术底座：ATH 可信互联（差异化壁垒）");
  addFooter(s, 4);

  const steps = [
    { t: "身份可信", d: "Agent Card 公开发现 + AID/ACDL 身份卡 + 应用侧核验智能体身份(④)", c: C.primary },
    { t: "授权可控", d: "最小权限 + 握手凭证 HMAC 签发/校验(⑤⑦) + RBAC 项目归属", c: C.info },
    { t: "交互可溯", d: "A2A trace_id/evidence 证据链 + agent_traces 回放", c: C.success },
  ];
  steps.forEach((st, i) => {
    const x = MARGIN + i * 4.15;
    addCard(s, x, 1.6, 3.9, 1.5, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.6, w: 3.9, h: 0.09, fill: { color: st.c } });
    s.addText(st.t, { x: x + 0.2, y: 1.8, w: 3.5, h: 0.4, fontSize: 16, color: C.dark, fontFace: FONT, bold: true });
    s.addText(st.d, { x: x + 0.2, y: 2.25, w: 3.5, h: 0.8, fontSize: 10.5, color: C.gray, fontFace: FONT });
  });

  s.addText("治理审计（确定性自检）", { x: MARGIN, y: 3.5, w: 6, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const audits = [
    { t: "OWASP Agentic Skills Top 10", d: "10/10 pass", c: C.success },
    { t: "ATH / 国标信任层", d: "5/5 pass（含④⑤⑦）", c: C.success },
    { t: "项目归属校验覆盖", d: "verify_project_access 43 个 API 文件", c: C.primary },
  ];
  audits.forEach((a, i) => {
    const y = 3.95 + i * 0.62;
    addCard(s, MARGIN, y, 6.2, 0.5, C.light);
    s.addText(a.t, { x: MARGIN + 0.2, y: y + 0.06, w: 4.6, h: 0.38, fontSize: 11.5, color: C.dark, fontFace: FONT });
    s.addText(a.d, { x: MARGIN + 4.8, y: y + 0.06, w: 1.3, h: 0.38, fontSize: 11, color: a.c, fontFace: FONT, bold: true, align: "right" });
  });

  s.addText("九步可信握手（ATH 1.0 三阶段重构）", { x: 7.3, y: 3.5, w: 5.4, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  addCard(s, 7.3, 3.95, 5.43, 2.0, C.primary50);
  s.addText([
    "阶段一 双向身份验证：① 用户授权 ② 发现智能体 ③ 身份声明 ④ 应用核验 ⑤ 双向验证",
    "阶段二 可信握手协商：⑥ 权限协商 ⑦ 签发会话凭证",
    "阶段三 会话建立：⑧ 任务状态机 ⑨ 全程存证",
  ].join("\n"), { x: 7.5, y: 4.1, w: 5.0, h: 1.7, fontSize: 11, color: C.primary600, fontFace: FONT, valign: "top", paraSpaceAfter: 4 });
}

// ════════════════════════════════════════════════════════════════
// P5 创新 ① 以销定产
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Innovation 01", "以销定产：designer BOM 反向驱动采购优先级");
  addFooter(s, 5);

  s.addText("designer BOM → 采购优先级（紧急 / 常规 / 可缓）", {
    x: MARGIN, y: 1.6, w: 12, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true,
  });
  const flow = ["设计方案", "BOM 清单", "优先级判定", "按需采购"];
  flow.forEach((t, i) => {
    const x = MARGIN + i * 3.15;
    s.addShape(pptx.ShapeType.roundRect, { x, y: 2.15, w: 2.85, h: 0.8, fill: { color: i === 3 ? C.primary : C.primary50 }, line: { color: C.primary, width: 1 }, rectRadius: 0.08 });
    s.addText(t, { x, y: 2.35, w: 2.85, h: 0.4, fontSize: 14, color: i === 3 ? C.white : C.primary600, fontFace: FONT, bold: true, align: "center" });
    if (i < 3) s.addText("→", { x: x + 2.85, y: 2.3, w: 0.3, h: 0.4, fontSize: 18, color: C.gray, fontFace: FONT, align: "center" });
  });

  const points = [
    "减少无效采购与库存占用，资金流更健康",
    "紧急材料优先，避免施工等待停摆",
    "借鉴义乌「以销定产」模式，先有方案再定采购",
  ];
  addBullet(s, points, MARGIN, 3.4, 7, 1.6, 13);
  s.addText("价值：把采购决策从「经验驱动」变为「BOM 数据驱动」", {
    x: MARGIN, y: 5.2, w: 11, h: 0.4, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true,
  });
}

// ════════════════════════════════════════════════════════════════
// P6 创新 ② 智能体自进化
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Innovation 02", "智能体自进化：越用越准，无需人工调优");
  addFooter(s, 6);

  const pipeline = ["Case 提取", "Skill 蒸馏", "三维质控", "失败学习"];
  pipeline.forEach((t, i) => {
    const x = MARGIN + i * 3.15;
    s.addShape(pptx.ShapeType.roundRect, { x, y: 1.7, w: 2.85, h: 0.9, fill: { color: C.primary50 }, line: { color: C.primary, width: 1 }, rectRadius: 0.08 });
    s.addText(t, { x, y: 1.95, w: 2.85, h: 0.4, fontSize: 16, color: C.primary600, fontFace: FONT, bold: true, align: "center" });
    if (i < 3) s.addText("→", { x: x + 2.85, y: 1.95, w: 0.3, h: 0.4, fontSize: 18, color: C.gray, fontFace: FONT, align: "center" });
  });

  const items = [
    { t: "Case 提取", d: "从 AgentTrace 自动提取结构化案例（task_intent + approach + quality）", c: C.primary },
    { t: "Skill 蒸馏", d: "同主题 Case ≥3 条聚类蒸馏为可复用 Skill，查重合并", c: C.info },
    { t: "三维质控", d: "Utility / Robustness / Safety 三维评分，低质 archive / 高质晋升", c: C.success },
    { t: "失败学习", d: "失败轨迹蒸馏「反模式 Skill」，执行前注入历史失败教训", c: C.warning },
  ];
  items.forEach((it, i) => {
    const y = 3.1 + i * 0.85;
    addCard(s, MARGIN, y, 12.13, 0.7, C.light);
    s.addShape(pptx.ShapeType.ellipse, { x: MARGIN + 0.2, y: y + 0.2, w: 0.3, h: 0.3, fill: { color: it.c } });
    s.addText(it.t, { x: MARGIN + 0.65, y: y + 0.08, w: 1.8, h: 0.4, fontSize: 13, color: C.dark, fontFace: FONT, bold: true });
    s.addText(it.d, { x: MARGIN + 2.5, y: y + 0.08, w: 9.4, h: 0.55, fontSize: 11, color: C.gray, fontFace: FONT });
  });
}

// ════════════════════════════════════════════════════════════════
// P7 创新 ③ 诚实降级 + 全链路证据
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Innovation 03", "诚实降级 + 全链路证据：可信可审计");
  addFooter(s, 7);

  const cols = [
    { t: "证据链", d: "A2A trace_id/evidence，每一步可核验可回放（agent_name/workflow_id/duration_ms/degraded）", c: C.success },
    { t: "诚实降级", d: "不可用即 503 / 占位 + 标注；执行降级不伪装 completed，诚实标 failed", c: C.warning },
    { t: "无假数据", d: "禁止硬编码假数据伪装真实能力；商业 Agent 数据源逐段诚实标注", c: C.error },
  ];
  cols.forEach((c, i) => {
    const x = MARGIN + i * 4.15;
    addCard(s, x, 1.7, 3.9, 2.4, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.7, w: 3.9, h: 0.09, fill: { color: c.c } });
    s.addText(c.t, { x: x + 0.2, y: 1.95, w: 3.5, h: 0.45, fontSize: 16, color: C.dark, fontFace: FONT, bold: true });
    s.addText(c.d, { x: x + 0.2, y: 2.5, w: 3.5, h: 1.4, fontSize: 11, color: C.gray, fontFace: FONT });
  });

  s.addText("核心理念：智能体要敢说「我不会」，而不是假装会", {
    x: MARGIN, y: 4.5, w: 12, h: 0.5, fontSize: 15, color: C.primary600, fontFace: FONT, bold: true, align: "center",
  });
  addCard(s, MARGIN, 5.2, 12.13, 1.0, C.primary50);
  s.addText("A2A 任务返回示例", { x: MARGIN + 0.2, y: 5.3, w: 3, h: 0.35, fontSize: 12, color: C.primary600, fontFace: FONT, bold: true });
  s.addText('{ "task_id": "...", "state": "completed", "trace_id": "...", "evidence": { "agent_name": "designer", "workflow_id": "...", "duration_ms": 1234, "degraded": false } }', {
    x: MARGIN + 0.2, y: 5.65, w: 11.7, h: 0.5, fontSize: 10, color: C.ink, fontFace: "Consolas",
  });
}

// ════════════════════════════════════════════════════════════════
// P8 场景 ① 康养（重点，已落地 CareAgent）
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Scenario 01 · Care", "康养：CareAgent 告警 → 场景联动（已落地）");
  addFooter(s, 8);

  s.addText("六类健康监测 + 穿戴 BLE + 环境传感器 + 米家设备", {
    x: MARGIN, y: 1.55, w: 12, h: 0.4, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true,
  });
  const types = ["睡眠", "空气质量", "跌倒", "活动", "心率", "血氧"];
  types.forEach((t, i) => {
    const x = MARGIN + i * 2.02;
    s.addShape(pptx.ShapeType.roundRect, { x, y: 2.05, w: 1.85, h: 0.6, fill: { color: C.primary50 }, line: { color: C.primary, width: 1 }, rectRadius: 0.06 });
    s.addText(t, { x, y: 2.17, w: 1.85, h: 0.36, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true, align: "center" });
  });

  s.addText("CareAgent 确定性编排（evaluate_care_actions）", {
    x: MARGIN, y: 2.95, w: 12, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true,
  });
  const rows = [
    ["跌倒检测", "起夜照明 + 通知家属 + 人工转接", "critical", C.error],
    ["心率/血氧严重异常", "通知家属 + 就医建议（不诊断）", "critical", C.error],
    ["睡眠质量低", "遮光 + 白噪音 环境自适应", "warning", C.warning],
    ["空气质量差", "新风 / 净化器联动", "warning", C.warning],
  ];
  rows.forEach((r, i) => {
    const y = 3.4 + i * 0.62;
    addCard(s, MARGIN, y, 8.5, 0.52, C.light);
    s.addText(r[0], { x: MARGIN + 0.2, y: y + 0.06, w: 2.2, h: 0.4, fontSize: 12, color: C.dark, fontFace: FONT, bold: true });
    s.addText(r[1], { x: MARGIN + 2.5, y: y + 0.06, w: 4.8, h: 0.4, fontSize: 11, color: C.gray, fontFace: FONT });
    s.addText(r[2], { x: MARGIN + 7.4, y: y + 0.06, w: 1.0, h: 0.4, fontSize: 11, color: r[3], fontFace: FONT, bold: true, align: "center" });
  });

  addCard(s, 9.3, 3.4, 3.43, 2.0, C.success50);
  s.addText("诚实边界", { x: 9.5, y: 3.52, w: 3, h: 0.4, fontSize: 14, color: C.success, fontFace: FONT, bold: true });
  s.addText("仅做监测与提醒，不做医疗诊断/处方。健康数据 PII 掩码 + 会话加密 + user_id 隔离。", {
    x: 9.5, y: 3.95, w: 3.0, h: 1.3, fontSize: 11, color: C.ink, fontFace: FONT,
  });

  s.addText("数据流：穿戴/传感器/米家 → health_monitor 采集 → CareAgent 编排 → 通知家属/场景执行/人工转接", {
    x: MARGIN, y: 6.05, w: 12, h: 0.4, fontSize: 11.5, color: C.gray, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════════════
// P9 场景 ② 旅居
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Scenario 02 · Travel", "旅居：候鸟式养老 / 异地养老 / 民宿度假屋");
  addFooter(s, 9);

  const cols = [
    { t: "远程设计", d: "designer 智能体异地出方案，无需到现场", c: C.primary },
    { t: "远程施工监理", d: "construction 进度跟踪 + 传感器快照远程监测", c: C.info },
    { t: "一键到家", d: "异地归家自动恢复温湿度/照明/安防场景", c: C.success },
  ];
  cols.forEach((c, i) => {
    const x = MARGIN + i * 4.15;
    addCard(s, x, 1.7, 3.9, 2.2, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.7, w: 3.9, h: 0.09, fill: { color: c.c } });
    s.addText(c.t, { x: x + 0.2, y: 1.95, w: 3.5, h: 0.45, fontSize: 16, color: C.dark, fontFace: FONT, bold: true });
    s.addText(c.d, { x: x + 0.2, y: 2.5, w: 3.5, h: 1.2, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 4.3, 12.13, 1.4, C.primary50);
  s.addText("差异化", { x: MARGIN + 0.25, y: 4.45, w: 2, h: 0.4, fontSize: 14, color: C.primary600, fontFace: FONT, bold: true });
  s.addText("把「装修交付」延伸为「旅居全周期托管」——交付不是终点，而是持续服务的起点。", {
    x: MARGIN + 0.25, y: 4.9, w: 11.5, h: 0.5, fontSize: 13, color: C.ink, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════════════
// P10 场景 ③ 疗愈（中医）
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Scenario 03 · TCM", "疗愈（中医）：药膳厨房 / 药浴卫浴 / 艾灸通风");
  addFooter(s, 10);

  const cols = [
    { t: "药膳厨房", d: "AI 设计药膳食补动线，厨电联动", c: C.warning },
    { t: "药浴卫浴", d: "温湿度 + 排风联动，防水防潮", c: C.warning },
    { t: "艾灸通风", d: "空气质量监测 → 排风/新风联动", c: C.success },
  ];
  cols.forEach((c, i) => {
    const x = MARGIN + i * 4.15;
    addCard(s, x, 1.7, 3.9, 2.2, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.7, w: 3.9, h: 0.09, fill: { color: c.c } });
    s.addText(c.t, { x: x + 0.2, y: 1.95, w: 3.5, h: 0.45, fontSize: 16, color: C.dark, fontFace: FONT, bold: true });
    s.addText(c.d, { x: x + 0.2, y: 2.5, w: 3.5, h: 1.2, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 4.3, 12.13, 1.2, C.warning50);
  s.addText("场景联动", { x: MARGIN + 0.25, y: 4.45, w: 2, h: 0.4, fontSize: 14, color: C.warning, fontFace: FONT, bold: true });
  s.addText("温湿度 / 空气质量（air_quality）+ scene_automation 触发联动：艾灸排烟、药浴恒温、药膳厨房通风。", {
    x: MARGIN + 0.25, y: 4.9, w: 11.5, h: 0.5, fontSize: 13, color: C.ink, fontFace: FONT,
  });
  s.addText("理念：科技服务传统疗愈，不是替代", {
    x: MARGIN, y: 5.9, w: 12, h: 0.4, fontSize: 13, color: C.primary600, fontFace: FONT, bold: true, align: "center",
  });
}

// ════════════════════════════════════════════════════════════════
// P11 场景 ④ 疗愈（西医）
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Scenario 04 · Rehab", "疗愈（西医）：术后 / 康复空间");
  addFooter(s, 11);

  const cols = [
    { t: "无障碍设计", d: "适老化/术后动线，扶手/防滑/护理通道", c: C.error },
    { t: "护理床联动", d: "护理床 + 环境监测（温湿度/光照/空气）联动", c: C.info },
    { t: "康复进度跟踪", d: "健康监测 → 告警 → 护工通知闭环", c: C.success },
  ];
  cols.forEach((c, i) => {
    const x = MARGIN + i * 4.15;
    addCard(s, x, 1.7, 3.9, 2.2, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.7, w: 3.9, h: 0.09, fill: { color: c.c } });
    s.addText(c.t, { x: x + 0.2, y: 1.95, w: 3.5, h: 0.45, fontSize: 16, color: C.dark, fontFace: FONT, bold: true });
    s.addText(c.d, { x: x + 0.2, y: 2.5, w: 3.5, h: 1.2, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  addCard(s, MARGIN, 4.3, 12.13, 1.2, C.error50);
  s.addText("闭环", { x: MARGIN + 0.25, y: 4.45, w: 2, h: 0.4, fontSize: 14, color: C.error, fontFace: FONT, bold: true });
  s.addText("从住院到居家康复的无缝衔接：环境监测 → 健康告警 → 护工/家属通知 → 场景联动。", {
    x: MARGIN + 0.25, y: 4.9, w: 11.5, h: 0.5, fontSize: 13, color: C.ink, fontFace: FONT,
  });
}

// ════════════════════════════════════════════════════════════════
// P12 商业化
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Business", "商业化：营收模型 + 量化证据");
  addFooter(s, 12);

  const models = [
    { t: "装企交付", d: "B2B 整装交付（设计+报价+施工计划）", c: C.primary },
    { t: "康养增值", d: "康养监测 / 场景联动订阅", c: C.success },
    { t: "智能家居托管", d: "旅居 / 疗愈空间全周期托管", c: C.info },
  ];
  models.forEach((m, i) => {
    const x = MARGIN + i * 4.15;
    addCard(s, x, 1.7, 3.9, 1.6, C.light);
    s.addShape(pptx.ShapeType.rect, { x, y: 1.7, w: 3.9, h: 0.09, fill: { color: m.c } });
    s.addText(m.t, { x: x + 0.2, y: 1.9, w: 3.5, h: 0.45, fontSize: 16, color: C.dark, fontFace: FONT, bold: true });
    s.addText(m.d, { x: x + 0.2, y: 2.4, w: 3.5, h: 0.7, fontSize: 11.5, color: C.gray, fontFace: FONT });
  });

  s.addText("量化证据（真实运营数据）", { x: MARGIN, y: 3.7, w: 8, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const metrics = [
    { k: "用户数", v: "[待填]", c: C.primary },
    { k: "订单数", v: "[待填]", c: C.info },
    { k: "交付单量", v: "[待填]", c: C.success },
    { k: "复购率", v: "[待填]", c: C.warning },
  ];
  metrics.forEach((m, i) => {
    const x = MARGIN + i * 3.15;
    addCard(s, x, 4.2, 2.85, 1.1, C.light);
    s.addText(m.k, { x: x + 0.2, y: 4.35, w: 2.4, h: 0.4, fontSize: 12, color: C.gray, fontFace: FONT });
    s.addText(m.v, { x: x + 0.2, y: 4.75, w: 2.4, h: 0.45, fontSize: 20, color: m.c, fontFace: FONT, bold: true });
  });
}

// ════════════════════════════════════════════════════════════════
// P13 团队与组织
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.white };
  addHeader(s, "Team", "团队与组织：能落地的团队");
  addFooter(s, 13);

  s.addText("核心团队", { x: MARGIN, y: 1.6, w: 4, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  addCard(s, MARGIN, 2.05, 6.0, 2.5, C.light);
  s.addText("[核心团队背景 / 分工 / 研发投入]", {
    x: MARGIN + 0.25, y: 2.3, w: 5.5, h: 2.0, fontSize: 13, color: C.gray, fontFace: FONT, valign: "top",
  });

  s.addText("已具备技术资产", { x: 7.3, y: 1.6, w: 5, h: 0.4, fontSize: 14, color: C.dark, fontFace: FONT, bold: true });
  const assets = [
    "专利 / 软著",
    "ICP 备案（滇ICP备2026015233号-2）",
    "治理审计报告（OWASP 10/10 + ATH 5/5）",
    "生产运行 v1.16.x（阿里云 ECS + 多端）",
  ];
  assets.forEach((a, i) => {
    const y = 2.05 + i * 0.62;
    addCard(s, 7.3, y, 5.43, 0.52, C.primary50);
    s.addText(a, { x: 7.5, y: y + 0.06, w: 5.0, h: 0.4, fontSize: 12, color: C.primary600, fontFace: FONT });
  });
}

// ════════════════════════════════════════════════════════════════
// P14 结尾
// ════════════════════════════════════════════════════════════════
{
  const s = pptx.addSlide();
  s.background = { color: C.dark };
  // 装饰圆已移除（避免越界警告），保留深色背景 + 左侧品牌竖条
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.14, h: H, fill: { color: C.primary } });

  s.addText("让家更懂你，让科技服务康养与疗愈", {
    x: 0.9, y: 2.0, w: 11.5, h: 0.9, fontSize: 32, color: C.white, fontFace: FONT, bold: true, align: "center",
  });
  s.addText("赛道定位：主攻「家庭生活 AI 及智能体」+ 副「家庭安全与用能」", {
    x: 0.9, y: 3.2, w: 11.5, h: 0.5, fontSize: 16, color: "CCE4FF", fontFace: FONT, align: "center",
  });
  s.addText("合作诉求：接入名气家 4600 万家庭场景验证 · 算力 Token · 资本对接", {
    x: 0.9, y: 3.9, w: 11.5, h: 0.5, fontSize: 14, color: "99C9FF", fontFace: FONT, align: "center",
  });

  s.addText("索克家居 · i-home.life", {
    x: 0.9, y: 5.6, w: 11.5, h: 0.4, fontSize: 14, color: C.primary200, fontFace: FONT, bold: true, align: "center",
  });
  s.addText("谢谢观看 · 期待交流", {
    x: 0.9, y: 6.2, w: 11.5, h: 0.4, fontSize: 12, color: "66ADFF", fontFace: FONT, align: "center",
  });
}

// ── 校验：重叠与越界 ──
pptx.writeFile({ fileName: "TERA-Award-2026-智慧家庭专题赛-参赛方案.pptx" }).then(() => {
  console.log("✅ PPT 已生成");
  for (let i = 0; i < pptx.slides.length; i++) {
    const slide = pptx.slides[i];
    helpers.warnIfSlideHasOverlaps(slide, pptx);
    helpers.warnIfSlideElementsOutOfBounds(slide, pptx);
  }
});
