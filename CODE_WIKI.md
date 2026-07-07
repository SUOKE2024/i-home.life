<img src="assets/images/icons/desktop/suoke-logo-128.png" alt="索克家居" width="48" height="48" align="left" style="border-radius:10px;margin-right:12px;">

# i-home.life（索克家居）Code Wiki

> **版本**：v4.0
> **最后更新**：2026-07-08
> **项目状态**：Phase 1-4 后端全链路完成（163 测试通过，8 AI Agent，21 路由 154 端点，54 张数据表）
> **作者**：索克生活 (suoke.life) · song.xu@icloud.com
> **代码仓库**：github.com/SUOKE2024/i-home.life

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 项目架构](#2-项目架构)
- [3. 目录结构](#3-目录结构)
- [4. 核心模块说明](#4-核心模块说明)
- [5. 关键文件详解](#5-关键文件详解)
- [6. 技术栈与依赖](#6-技术栈与依赖)
- [7. 数据模型](#7-数据模型)
- [8. AI Agent 体系](#8-ai-agent-体系)
- [9. 运行方式](#9-运行方式)
- [10. 开发路线图](#10-开发路线图)
- [11. 约定与规范](#11-约定与规范)

---

## 1. 项目概述

### 1.1 一句话定位

索克家居（i-home.life）是一个 **AI 驱动的全链路智能家居建造平台**，通过多端 App 矩阵和 AI Agent 集群，覆盖「设计 → 预算 → 选材 → 采购 → 施工 → 结算 → 验收」全流程。

### 1.2 核心差异化

| 维度 | 传统模式 | 索克家居 |
|------|---------|---------|
| 运营主体 | 人类设计师/预算员/监理 | AI Agent 7×24 自主运营 |
| 数据流转 | 多工具碎片化导入导出 | 统一数据底座实时同步 |
| 交互方式 | 鼠标键盘操作 | 语音/拍照/AR 多模态 |
| 覆盖范围 | 单一环节 | 测量→设计→采购→施工→结算全链路 |

### 1.3 目标用户

| 角色 | 端 | 设备 | 核心诉求 |
|------|-----|------|---------|
| 业主 | 业主端 | 手机 | 透明比价、实时进度、预算控制 |
| 设计师 | 设计台 | 平板 | 高效出图、自动 BOM、方案同步 |
| 施工队/工长 | 施工端 | 手机 | 清晰图纸、进度上报、验收闭环 |
| 供应商 | 供应链端 | 手机 | 精准采购需求、在线报价接单 |
| 自由设计师/监理 | 服务端 | 手机+平板 | 接单投标、在线签约、交付验收 |

---

## 2. 项目架构

### 2.1 系统分层架构

```
┌──────────────────────────────────────────────────────┐
│                  AI Agent 自治层                        │
│  总控Agent │ 设计Agent │ 预算Agent │ 采购Agent          │
│  施工Agent │ 质检Agent │ 结算Agent │ 客服Agent          │
└──────────────────────────────────────────────────────┘
                           ↕
┌──────────────────────────────────────────────────────┐
│             客户端层 (Flutter 跨平台)                    │
│  iPadOS · Android平板 · HarmonyOS平板                   │
│  UI 层：工作台 / 商城 / 采购 / 施工 / 预算               │
│  图形引擎：2D Canvas + 3D Three.js/Filament              │
│  AR 层：RoomPlan / ARKit / ARCore / AR Engine           │
└──────────────────────────────────────────────────────┘
                           ↕
┌──────────────────────────────────────────────────────┐
│                   网关层                                │
│  RESTful + WebSocket (PASETO 认证)                     │
│  消息队列 (Agent 间通信)                                │
└──────────────────────────────────────────────────────┘
                           ↕
┌──────────────────────────────────────────────────────┐
│                   微服务层                              │
│  用户服务 · 项目服务 · 设计服务 + 几何引擎                │
│  渲染服务 (GPU 集群) · 物料服务 BOM                      │
│  采购服务 · 施工服务 · 预算与结算服务                      │
│  AI 推理服务 (LLM + CV + Agent 框架)                    │
└──────────────────────────────────────────────────────┘
                           ↕
┌──────────────────────────────────────────────────────┐
│                   数据层                                │
│  PostgreSQL · 对象存储(图纸/照片/3D)                     │
│  Redis(缓存/队列) · ES(搜索/日志)                        │
│  向量数据库(RAG 知识库)                                  │
└──────────────────────────────────────────────────────┘
```

### 2.2 四端分离架构

| 端（App） | 核心用户 | 主力设备 | 功能特征 |
|-----------|---------|---------|---------|
| 设计台 Designer Suite | 室内设计师 / 建筑师 | iPad Pro · Galaxy Tab · MatePad Pro | 2D CAD 精确绘图、3D 建模、平立剖生成、效果图渲染 |
| 业主端 Homeowner | 业主（发包方） | iPhone · Android · 鸿蒙手机 | 方案浏览、AR 预览、预算监控、采购审批、进度查看 |
| 供应链端 Supply Chain | 建材供应商 / 家具品牌商 / 电器经销商 | 手机 | 询价推送、在线报价、订单管理、物流追踪 |
| 施工端 Construction | 工长 / 施工队 / 监理 | 手机 | 任务接收、拍照上报、AI 质检、离线模式 |

### 2.3 跨端数据流

```
设计台(平板) ──方案变更──→ 统一数据底座 ←──拍照/进度── 施工端(手机)
                  ↕            ↕
业主端(手机) ──审批/下单──→  WebSocket   ←──报价/发货── 供应链端(手机)
                      实时推送 < 3s
```

---

## 3. 目录结构

```
/Users/netsong/Developer/i-home.life/
│
├── app/                              # 后端应用 (FastAPI)
│   ├── api/                          # 21 个路由模块 (154 端点)
│   │   ├── auth.py                   # 认证 (register/login/me)
│   │   ├── projects.py               # 项目管理
│   │   ├── materials.py              # 物料 + BOM + Excel导出
│   │   ├── budgets.py                # 预算管理
│   │   ├── procurement.py            # 采购 + 供应商
│   │   ├── construction.py           # 施工 + 日志 + 质检
│   │   ├── settlements.py            # 结算管理
│   │   ├── floorplans.py             # 户型方案存储
│   │   ├── voice.py                  # 语音处理
│   │   ├── files.py                  # 文件上传/下载
│   │   ├── agents.py                 # AI Agent 路由 (mock + LLM 双模式, 8 Agent)
│   │   ├── payments.py               # 支付管理
│   │   ├── chat.py                   # 三方协作 IM
│   │   ├── crews.py                  # 工程队匹配
│   │   ├── surveys.py                # AR 测量数据
│   │   ├── layouts.py                # 智能布局动线分析
│   │   └── ...                       # 其他路由模块
│   ├── agents/                       # 8 个 AI Agent
│   │   ├── orchestrator.py           # 总控 (意图路由 + fallback_classify)
│   │   ├── designer.py               # 设计 (9套布局 + 修改意图识别)
│   │   ├── budget.py                 # 预算分析
│   │   ├── procurement.py            # 采购建议
│   │   ├── construction.py           # 施工计划 (F37 进度管理 + F38 质量检测)
│   │   ├── settlement.py             # 财务结算
│   │   ├── qa_inspector.py           # 质检 (验收报告 + 缺陷识别 + 设计比对)
│   │   ├── concierge.py              # 客服 (FAQ 知识库 + 咨询分类 + 升级规则)
│   │   └── base.py                   # BaseAgent
│   ├── models/                       # 54 张数据表 (SQLAlchemy 2.0 async)
│   ├── schemas/                      # Pydantic 验证
│   ├── services/                     # 业务逻辑层
│   ├── auth/                         # PASETO Token 认证
│   ├── database.py                   # 异步引擎 + 会话工厂
│   └── main.py                       # FastAPI 入口
│
├── flutter_app/                      # 跨平台 App (iOS/iPadOS/Android/HarmonyOS)
│   ├── lib/
│   │   ├── pages/                    # cad_page / dashboard / projects / ai_chat / materials
│   │   └── services/api.dart         # HTTP 客户端
│   ├── ohos/                         # HarmonyOS 平台配置
│   │   ├── hvigor/hvigor-config.json5  # 指向 DevEco Studio 本地 hvigor
│   │   └── oh-package.json5          # (不含 @ohos/hvigor, DevEco 内置)
│   └── pubspec.yaml                  # 依赖: path_provider, file_picker, image_picker, provider, intl, uuid
│
├── web/                              # 前端页面
│   ├── index.html                    # 管理后台 SPA (10 Tab)
│   ├── studio.html                   # 统一设计台 (Canvas + Three.js + AI)
│   ├── 3d-viewer.html                # 3D 效果图查看器
│   └── designer.html                 # Canvas 户型编辑器
│
├── alembic/                          # 数据库迁移 (Alembic)
│   ├── env.py                        # 从 settings 注入 DATABASE_URL (SQLite/PostgreSQL 双库)
│   ├── alembic.ini                   # Alembic 配置
│   └── versions/                     # 迁移版本目录
│
├── scripts/                          # 运维脚本
│   ├── demo-start.sh                 # 一键启动演示环境
│   ├── e2e-full.sh                   # 全链路自动测试
│   ├── verify-ac.sh                  # AC 验收报告
│   ├── deploy.sh                     # 生产部署
│   ├── deploy-ohos.sh                # HarmonyOS HAP 构建部署 (DevEco Studio)
│   ├── matepad-test.sh               # MatePad 真机测试指引
│   ├── bench-matepad.sh              # MatePad 性能验收脚本
│   └── seed.py                       # 种子数据 (225 SKU)
│
├── tests/                            # 测试套件 (163 pass / 9 skipped)
│   ├── conftest.py                   # pytest fixtures (AsyncClient + ASGITransport)
│   ├── test_auth.py                  # 认证 (7)
│   ├── test_projects.py              # 项目 CRUD (4)
│   ├── test_materials.py             # 物料 + BOM (7)
│   ├── test_budgets_and_agents.py    # 预算 + Agent (7)
│   ├── test_procurement_construction.py  # 采购 + 施工 (6)
│   ├── test_settlements.py           # 结算 (8)
│   ├── test_floorplans.py            # 户型 CRUD (6)
│   ├── test_files_and_voice.py       # 文件上传 + 语音 (14)
│   ├── test_agents_llm.py            # Agent LLM 路径 + mock 模式 (23)
│   ├── test_websocket.py             # WebSocket (3 pass / 9 skipped)
│   ├── test_qa_inspector_concierge.py  # 质检 + 客服 Agent (31)
│   └── ...                           # 其他测试模块
│
├── _shared/                          # 共享静态资源
│   └── js/
│       ├── echarts.min.js            # ECharts 图表库
│       └── mermaid.min.js            # Mermaid 图表库
│
├── assets/                           # 静态资源（截图、图标）
│
├── docs/                             # 文档
│   └── PHASE2_ROADMAP.md             # Phase 2 路线图
│
├── .gitignore                        # Git 忽略规则
├── .python-version                   # Python 3.12.13
├── .env                              # 环境变量 (DATABASE_URL/PASETO_KEY/DEEPSEEK_API_KEY)
├── requirements.txt                  # Python 依赖
├── house-design-platform-prd.html    # 完整 PRD v3.0
└── interactive-demo.html             # 交互式 Demo（入口）
```

---

## 4. 核心模块说明

### 4.1 PRD 文档模块

**文件**：[house-design-platform-prd.html](file:///Users/netsong/Developer/i-home.life/house-design-platform-prd.html)

产品需求文档，包含 12 个主要章节：

| 章节 | 内容 | 关键产出 |
|------|------|---------|
| §1 需求背景 | 行业痛点分析 + 技术窗口分析 | 6 项痛点卡片 + 7 项技术突破表 |
| §2 市场与竞品分析 | 6 款竞品功能对比 | 23 维 × 7 产品热力图 |
| §3 产品定位 | 一句话定位 + 平台支持 + 目标用户 | 设备优先级矩阵 |
| §4 多平台多角色适配 | 四端分离架构 + 端-平台覆盖矩阵 | 5 端 × 6 平台覆盖表 |
| §5 AI 智能体架构 | 8 个 Agent 定义 + 协作机制 + 自主权分级 | Mermaid 流程图 |
| §6 用户画像与场景 | 用户旅程 + 3 个典型场景 | 端到端流程 Mermaid 图 |
| §7 功能需求 | 40 项功能需求详情 | F1—F40 功能矩阵表 |
| §8 系统架构 | 分层架构图 + 技术决策表 | 12 项技术决策 |
| §9 核心数据模型 | ER 图 + 关键实体字段 | Mermaid ER 图 |
| §10 依赖风险路线图 | 5 项关键依赖 + Gantt 图 | 5 阶段路线图 |
| §11 MVP 范围 | Phase 1 必须交付 + 不做清单 | 8 项 P0 功能 |
| §11A Demo 规格 | 3 个交互场景 + 技术指标 | 9 项性能指标 |
| §12 验收标准 | 9 项 AC 验收项 | 通过标准定义 |

### 4.2 交互式 Demo 模块

**文件**：[interactive-demo.html](file:///Users/netsong/Developer/i-home.life/interactive-demo.html)

一个纯前端单页面应用，模拟 AI 设计助手的工作流程：

```
┌─────────────┬───────────────────────┬──────────────┐
│   Sidebar   │      Canvas 区域      │  Chat 面板    │
│             │                       │              │
│  📐 设计方案 │   ┌───────────────┐  │ AI 对话历史   │
│  💰 预算管理 │   │  3D 平面预览   │  │              │
│  🛒 采购市场 │   │               │  │ 快捷操作:     │
│  🔨 施工管理 │   │  房间平面图    │  │ 🍳 开放式厨房 │
│             │   │               │  │ 👔 主卧衣帽间 │
│             │   │  126㎡         │  │ 🌿 打通阳台   │
│             │   └───────────────┘  │ 💰 查看预算   │
│             │   [AI 状态条]        │              │
│             │                       │ [输入框]      │
│             │   ┌─ 预算 Dashboard ─┐│              │
│             │   │ (滑出面板)       ││              │
│             │   └─────────────────┘│              │
└─────────────┴───────────────────────┴──────────────┘
```

**功能交互流程**：

```
用户输入/点击快捷操作
    │
    ▼
sendMsg() ──→ addMsg('user', text)    // 显示用户消息
    │              │
    ▼              ▼
processAI(text)    DOM 更新聊天面板
    │
    ├── 关键词匹配：
    │   ├── 厨房/开放/中岛 → action='kitchen'
    │   ├── 衣帽间/衣柜   → action='wardrobe'
    │   ├── 阳台/打通     → action='balcony'
    │   ├── 预算/费用     → toggleDashboard()
    │   └── 默认         → 引导提示
    │
    ▼
setTimeout 模拟 AI 延迟 (0.8–1.4s)
    │
    ├── addMsg('ai', reply)          // 显示 AI 回复
    ├── updateRoom(action)           // 更新 3D 平面预览
    ├── updateBudgetDisplay()        // 更新预算数字
    ├── advanceStep()                // 推进步骤指示器
    └── showToast()                  // 显示同步提示
```

**状态管理**（全局变量 `state`）：

```javascript
state = {
    modifications: [],    // 已执行的修改列表 ['kitchen', 'wardrobe']
    budget: 186500,       // 当前总预算（动态变化）
    area: 126,            // 当前面积（动态变化）
    steps: 1              // 当前步骤指示器位置
}
```

### 4.3 竞品分析模块

竞品能力覆盖矩阵已内联至 PRD HTML 表格（`<table class="matrix">`），数据维度：

| 竞品 | 覆盖能力数（23 维） | AI 能力 |
|------|-------------------|---------|
| 酷家乐 | 10 项部分 + 2 项完全 | 无 Agent |
| 住小帮 | 仅移动端原生 | 无 |
| Shapr3D | CAD+3D+移动端 | 无 |
| Planner 5D | 设计+软装+移动端 | AI 渲染生成 |
| MagicPlan | AR 测量+移动端 | 无 |
| Procore | 施工管理+工程队匹配 | 无 |
| **索克家居** | **23 项全覆盖** | **8 Agent** |

---

## 5. 关键文件详解

### 5.1 `house-design-platform-prd.html`

| 属性 | 值 |
|------|-----|
| 作用 | 完整产品需求文档 |
| 大小 | ~47KB |
| 技术 | HTML5 + CSS3 + Mermaid + ECharts |
| 包含图表 | 4 张 Mermaid 流程图 + 1 张 ECharts 热力图 + 1 张 Mermaid ER 图 + 1 张 Mermaid Gantt 图 |
| 样式策略 | CSS 变量主题系统、响应式布局、打印友好 |

**外部依赖**：
- `_shared/js/echarts.min.js`
- `_shared/js/mermaid.min.js`

### 5.2 `interactive-demo.html`

| 属性 | 值 |
|------|-----|
| 作用 | AI 设计助手交互 Demo |
| 大小 | ~21KB |
| 技术 | HTML5 + CSS3 + Vanilla JS |
| 交互模式 | 文本输入 + 快捷按钮 + 语音模拟 |

**核心函数**：

| 函数名 | 职责 |
|--------|------|
| `sendMsg()` | 获取输入框文本，调用 `addMsg` 和 `processAI` |
| `addMsg(type, text)` | 向聊天面板添加消息气泡（user/ai 样式） |
| `processAI(userText)` | 关键词匹配 AI 意图，生成回复文本 + 动作 |
| `updateRoom(action)` | 根据 action 类型在 Canvas 上渲染对应 UI 元素 |
| `updateBudgetDisplay()` | 动态更新预算仪表盘中的数字 |
| `advanceStep()` | 推进步骤指示器到下一步 |
| `toggleDashboard()` | 滑出/隐藏预算仪表盘面板 |
| `showToast(msg)` | 顶部 Toast 提示（2.5s 自动消失） |
| `resetDemo()` | 重置所有状态到初始值 |

### 5.3 配置文件

| 文件 | 内容 | 说明 |
|------|------|------|
| `.python-version` | `3.12.13` | Python 运行环境版本 |
| `.gitignore` | Python / Flutter / IDE / OS / Serverless 忽略规则 | 多技术栈覆盖 |

---

## 6. 技术栈与依赖

### 6.1 规划技术栈（后端）

| 层面 | 技术选型 | 理由 |
|------|---------|------|
| 语言 | Python 3.12+ | 项目根 `.python-version` 指定 |
| Web 框架 | FastAPI | `.venv` 中包含 fastapi / uvicorn |
| 数据库 | PostgreSQL (asyncpg) | `.venv` 中有 asyncpg 驱动 |
| 缓存/队列 | Redis | 架构设计中定义 |
| 搜索/日志 | Elasticsearch | 架构设计中定义 |
| 向量数据库 | 待定（RAG 知识库） | 装修规范/国标/产品目录 |
| 认证 | PASETO | 项目约定（非 JWT），`.venv` 中有 paseto 库 |
| 加密 | Cryptodome / cryptography | 已在 `.venv` 中 |
| 部署 | 直接二进制部署 | 不使用 Docker（项目约定） |

### 6.2 规划技术栈（前端）

| 层面 | 技术选型 | 理由 |
|------|---------|------|
| 跨平台框架 | Flutter (Impeller) + 鸿蒙适配层 | 单代码库覆盖 iOS + Android + HarmonyOS |
| 2D 绘图 | Flutter CustomPainter (Skia) | 自研对象捕捉、视图变换交互层 |
| 3D 渲染 | Three.js (WebView) → Filament | Three.js 快速迭代，长线迁移 Filament |
| 几何内核 | OpenCascade.js (WASM) + 自研简化求解器 | 复杂布尔运算走 OCC，简单操作走自研 |
| AR | RoomPlan / ARKit / ARCore / AR Engine | 各平台原生 AR 能力 |

### 6.3 实际技术栈（AI）

| 层面 | 技术选型 |
|------|---------|
| Agent 框架 | 自研混合路由（关键词匹配 + LLM fallback）+ Orchestrator 中央调度 |
| LLM | DeepSeek（云端 API，mock fallback 模式） |
| 多模态 | Whisper 语音识别（模拟）+ 文本对话 |
| 图像生成 | Stable Diffusion + ControlNet（规划中） |
| 图像检测 | CV 缺陷检测模型（mock 框架已实现） |
| 知识库 | FAQ 预置知识库（RAG 规划中） |

### 6.4 当前 Demo 技术栈

| 层面 | 技术选型 |
|------|---------|
| 结构 | HTML5 |
| 样式 | CSS3（CSS 变量主题、Flexbox/Grid 布局、响应式） |
| 交互 | Vanilla JavaScript (ES5 兼容) |
| 图表 | ECharts 5（热力图）|
| 流程图 | Mermaid 11（架构图/ER图/Gantt 图） |
| Python 环境 | 3.12.13（后续后端开发用） |

### 6.5 现有 Python 依赖（.venv 中已安装）

| 包 | 用途 |
|----|------|
| `fastapi` + `uvicorn` | Web 框架 |
| `asyncpg` | PostgreSQL 异步驱动 |
| `paseto` | PASETO Token 认证 |
| `cryptography` + `pycryptodome` | 加密工具 |
| `pydantic` | 数据验证 |
| `numpy` + `pandas` | 数据分析 |
| `ortools` | 约束优化求解（可能用于布局优化） |
| `pendulum` | 时间日期处理 |
| `pytest` + `coverage` | 测试框架 |

---

## 7. 数据模型

### 7.1 ER 图

```
User ──owns──→ Project ──contains──→ Floor ──contains──→ Room ──has──→ Wall
                  │
    ┌─────────────┼─────────────┬──────────────────┬────────────────┐
    ▼             ▼             ▼                  ▼                ▼
  Budget      Settlement    BOM              ConstructionTask   ProcurementOrder
    │             │           │                  │                  │
    ▼             ▼           ▼                  ▼                  ▼
BudgetLine   SettlementLine  BOMItem          Inspection         OrderLine
    │             │           │                  │                  │
    ▼             ▼           ▼                  ▼                  ▼
 Category    BudgetLine    Product            Issue            BOMItem
                              │
                              ▼
                          Supplier
```

### 7.2 关键实体

**BudgetLine（预算明细）**：
- `category`: 预算类别（civil/finish/kitchen/bathroom/furniture/lighting/appliance/smart_home/soft_decor）
- `estimated_amount`: 预估金额
- `actual_amount`: 实际金额
- `variance_pct`: 偏差百分比
- `confidence`: 价格置信度（quoted/market_ref/historical）

**Settlement（结算单）**：
- `milestone`: 结算里程碑（handover/plumbing/tiling/completion/warranty）
- `contract_amount`: 合同金额
- `actual_amount`: 实际金额
- `payable_amount`: 应付金额
- `status`: 结算状态（draft/under_review/confirmed/paid）

---

## 8. AI Agent 体系

### 8.1 Agent 矩阵

| Agent | 角色 | 核心职责 | 状态 |
|-------|------|---------|------|
| **总控 Agent** Orchestrator | 中央调度者 | 理解用户意图 → 分解任务 → 分派专业 Agent → 监控全局状态 → 人工升级决策 | ✅ 已实现 |
| **设计 Agent** Designer | 设计产出者 | AR 扫描→生成平面图→规范检查→自动标注→生成平立剖→触发渲染 | ✅ 已实现 |
| **预算 Agent** Budget Controller | 财务控制者 | BOM→分项预算→多方案对比→实时追踪→偏差 > 5% 预警 | ✅ 已实现 |
| **采购 Agent** Procurement | 采购执行者 | BOM→匹配供应商→询价→收集报价→比价报告→推荐方案→一键下单 | ✅ 已实现 |
| **施工 Agent** Construction Manager | 施工管理者 | 设计方案→施工计划(Gantt)→每日推送→照片 AI 审核→日报/周报 | ✅ 已实现 |
| **质检 Agent** QA Inspector | 质量检测者 | 照片 vs 设计图纸比对→尺寸偏差检测→工艺缺陷识别→验收报告 | ✅ 已实现 |
| **结算 Agent** Settlement | 结算执行者 | 合同价 + 变更 + 采购 + 验收 → 自动结算 → 异常标记 → 生成对账单 | ✅ 已实现 |
| **客服 Agent** Concierge | 客服接待者 | 7×24 多模态对话（文本+语音+图片）→ 知识问答 → 复杂问题升级 | ✅ 已实现 |

### 8.2 Agent 自主权分级

| 级别 | 描述 | 示例 |
|------|------|------|
| **L1 建议** | Agent 仅提供建议，人类决策 | 设计 Agent 推荐 3 种布局方案，用户选择 |
| **L2 执行+确认** | Agent 自动执行，人类审批 | 采购 Agent 收集报价，用户确认下单 |
| **L3 自主执行** | Agent 完全自主，仅通知结果 | 质检 Agent 自动审核照片，通过则更新进度 |
| **L4 自适应** | Agent 从历史项目学习优化 | 预算 Agent 根据历史数据持续优化模型 |

### 8.3 人机协作关键节点

```
AI 自主处理 ──────────────────────────────────→ 人类决策
    │                                              │
    ├─ 方案推荐 (L1)                                │
    ├─ 物料统计 (L3)               方案确认 ←───────┘
    ├─ 供应商匹配 (L3)                              │
    ├─ 报价收集 (L3)               下单确认 ←───────┘
    ├─ 质检审核 (L3)               验收确认 ←───────┘
    ├─ 结算对账 (L2)               结算确认 ←───────┘
    └─ 异常检测 (L2)               升级处理 ←───────┘
```

---

## 9. 运行方式

### 9.1 后端服务运行

本项目 Phase 1 MVP 已完成实现，后端为 FastAPI 异步服务。

```bash
# 1. 进入项目目录
cd /Users/netsong/Developer/i-home.life

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入可选的 DEEPSEEK_API_KEY（留空则使用 mock 模式）

# 3. 安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. 启动服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. 运行测试 (163 pass / 9 skipped)
python -m pytest tests/ -v

# 6. 运行全链路 Demo
PYTHON=".venv/bin/python" bash scripts/e2e-full.sh

# 7. 数据库迁移 (Alembic, SQLite→PostgreSQL 切换仅需改 .env 的 DATABASE_URL)
alembic revision --autogenerate -m "init"
alembic upgrade head
```

### 9.3 Demo 交互说明

在 [interactive-demo.html](file:///Users/netsong/Developer/i-home.life/interactive-demo.html) 中：

| 操作 | 预期效果 |
|------|---------|
| 输入"把厨房改成开放式加中岛台" | AI 回复方案变更详情，3D 预览更新，预算 +¥8,500 |
| 点击 🍳 开放式厨房 | 同上（快捷操作） |
| 输入/点击"主卧加一个步入式衣帽间" | 衣帽间添加，预算 +¥12,600 |
| 输入/点击"客厅和阳台打通" | 阳台打通，预算 +¥4,200 |
| 输入/点击"帮我看看预算" | 滑出预算仪表盘面板 |
| 点击 📊 预算 | 切换预算仪表盘显示/隐藏 |
| 点击 🔄 重置 | 恢复初始状态 |
| 点击 🎤 语音 | 模拟语音输入流程 |

---

## 10. 开发路线图

```
Phase 1: 设计核心 + AI 基础 (2026-08 ~ 2026-12) ✅ 后端完成
├── 2D CAD 绘图引擎 (web/studio.html Canvas)
├── 3D & 平立剖自动生成 (web/3d-viewer.html Three.js，平立剖待补)
├── 效果图渲染 (基础渲染已实现)
├── 总控 Agent + 设计 Agent v1 ✅
└── iPadOS Alpha 测试 (Flutter 框架级适配)

Phase 2: AR + 预算 + 厨卫 (2026-12 ~ 2027-03) ✅ 后端完成
├── LiDAR/RoomPlan 集成 (surveys 表已建，前端待实现)
├── 预算+结算 Agent ✅
├── 厨卫设计器 + 电器点位规划 (数据层就绪)
├── Android+鸿蒙平板适配 (ohos 配置完成)
└── 封闭 Beta 测试

Phase 3: 采购市场 (2027-04 ~ 2027-06) ✅ 后端完成
├── 供应商入驻+审核 ✅ (12 家供应商)
├── 采购 Agent + 询价比价 ✅
├── 首城 100+ 供应商 BD (运营待推进)
└── 公开 Beta 上线

Phase 4: 施工 + 质检 Agent (2027-07 ~ 2027-08) ✅ 后端完成
├── 施工 Agent + 质检 Agent ✅
├── 工程队入驻+审核 (crews 表已建)
├── 三方协作 IM (chat 表已建)
├── 智能布局动线分析 ✅ (F28)
└── 支付管理 (payments 表已建)

Phase 5: 生态完善 (2027-09 ~ 2027-12) 进行中
├── 客服 Agent ✅
├── 智能家居方案设计器 (规划中)
├── AI 自适应学习 L4 (规划中)
└── GA 正式版
```

### Phase 1 MVP 必须交付

| # | 功能 | 优先级 | 状态 |
|---|------|--------|------|
| 1 | 2D CAD 精确绘图（直线/矩形/圆弧 + 正交锁定 + 对象捕捉 + DXF 导出） | P0 | ⚠️ 部分实现 |
| 2 | 3D 模型生成（2D 墙体拉伸 → 3D + 基础材质） | P0 | ⚠️ 部分实现 |
| 3 | 平立剖自动生成（俯视平面图 + 四向立面正投影） | P0 | ❌ 未实现 |
| 4 | 本地效果图预览（Three.js 实时渲染 + 3 套光照预设） | P0 | ⚠️ 基础渲染 |
| 5 | 总控 Agent v1（多模态对话 + 意图理解 + 任务路由） | P0 | ✅ 已实现 |
| 6 | 设计 Agent v1（自动生成 3 套平面布局 + 自然语言修改指令） | P0 | ✅ 已实现 (9 套布局) |
| 7 | 基础物料库 + BOM（200+ SKU + 自动生成 + Excel 导出） | P1 | ✅ 已实现 (225 SKU) |
| 8 | 手写笔适配 stylus_adapter.dart（Apple Pencil + M-Pencil 压感线宽 + 悬停预览 + 双击切换工具） | P0 | ⚠️ 框架级 |

### 超前实现（超出 Phase 1 范围）

以下功能在 PRD 中标注为 Phase 2-5，但后端已提前实现：

| PRD 标注 | 功能 | 实现状态 |
|---------|------|---------|
| Phase 2 | 预算 Agent + 结算 Agent | ✅ 完整实现 |
| Phase 3 | 采购 Agent + 供应商管理 | ✅ 完整实现 |
| Phase 4 | 施工 Agent + 质检 Agent + IM + 工程队匹配 | ✅ 完整实现 |
| Phase 5 | 客服 Agent | ✅ 完整实现 |
| Phase 5 | 支付管理 | ⚠️ 数据层就绪 |

---

## 11. 约定与规范

### 11.1 技术约定

| 约定 | 说明 |
|------|------|
| **认证** | 使用 PASETO 而非 JWT |
| **部署** | 不使用 Docker，直接二进制部署 |
| **Python 版本** | 3.12.13 |
| **跨平台** | Flutter 统一代码库，P0 优先 iPadOS |
| **代码风格** | Ruff linter（`.ruff_cache` 存在） |

### 11.2 命名规范

| 类型 | 规范 |
|------|------|
| 文件名 | kebab-case（如 `house-design-platform-prd.html`） |
| JS 函数 | camelCase（如 `processAI`, `updateRoom`） |
| CSS 类名 | kebab-case（如 `.chat-panel`, `.budget-bar`） |
| JS 变量 | camelCase（如 `state`, `chartEl`） |

### 11.3 Git 忽略规则

```
# Python
__pycache__/, *.py[cod], *.egg-info/, .eggs/, dist/, build/, .venv/, venv/

# 环境变量
.env, .env.local, *.env

# Flutter
.dart_tool/, .packages, build/, *.jlink

# IDE
.idea/, .vscode/, *.swp, *.swo

# OS
.DS_Store, Thumbs.db

# Serverless
.s/
```

### 11.4 关键术语表

| 术语 | 全称/解释 |
|------|----------|
| BOM | Bill of Materials（物料清单） |
| CAD | Computer-Aided Design（计算机辅助设计） |
| WASM | WebAssembly（浏览器级字节码） |
| RAG | Retrieval-Augmented Generation（检索增强生成） |
| ASR | Automatic Speech Recognition（语音识别） |
| LiDAR | Light Detection and Ranging（激光雷达测距） |
| PASETO | Platform-Agnostic Security Tokens（平台无关安全令牌） |
| DXF | Drawing Exchange Format（CAD 交换格式） |
| DWG | DraWinG（AutoCAD 原生格式） |
| Gantt | 甘特图（项目进度管理图表） |

---

> **本文档由 Code Wiki 分析工具生成，覆盖项目架构、模块职责、关键文件、依赖关系及运行方式等关键信息。**
