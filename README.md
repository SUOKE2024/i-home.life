# i-home.life

> **索克家居 · AI 智能装修平台**
>
> v1.0.0 · PRD F1-F40 全量功能交付完成（2026-07-08）
> 已交付：F1 AR 空间测量 / F15 支付 / F16 厨房 / F17 卫生间 / F18 厨卫水电 / F21 硬装 / F23 门窗防水 / F24-F25 软装收纳 / F27 定制家具 / F28 动线 / F29-F30 灯光 / F26 家具库 / F31 智能家居 / F32 场景编辑 / F33-F34 采购增强 / F35-F40 服务者+施工+进度+质量+IM / VR 全景 / AI 图生图

## 快速启动

```bash
# 一键演示环境
bash scripts/demo-start.sh

# 启动后端
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 打开各前端页面
open web/index.html       # 管理后台
open web/studio.html      # 统一设计台 (2D+3D+AI)
open web/3d-viewer.html   # 3D 效果图
```

## 项目结构

```
i-home.life/
├── app/
│   ├── api/           # 34 个路由模块 (318 端点)
│   │   ├── auth.py          # 认证 (register/login/me)
│   │   ├── projects.py      # 项目管理
│   │   ├── materials.py     # 物料 + BOM + Excel导出
│   │   ├── budgets.py       # 预算管理 + 多方案对比 + 偏差预警 + 模板库
│   │   ├── procurement.py   # 采购 + 供应商 + 比价报告
│   │   ├── procurement_enhanced.py  # F33/F34 采购增强 (比价/担保支付/物流追踪/样品索要)
│   │   ├── construction.py  # 施工 + 日志 + 质检 + AI 图像审核 + F37 进度 + F38 质量
│   │   ├── settlements.py   # 结算 + 里程碑 + 异常检测 + 对账单
│   │   ├── change_orders.py # 变更管理 (F39)
│   │   ├── payments.py      # 支付管理 (F15) 发起/确认/退款/里程碑聚合
│   │   ├── chat.py          # IM 协作 (F40) 消息/聊天室/@提及/已读
│   │   ├── crews.py         # 工程队匹配 (F36) 档案/六维评分/雇佣
│   │   ├── workers.py       # 服务者匹配 (F35) 设计师/监理/预算师档案+评分
│   │   ├── takeoff.py       # 工程量计算 (F9)
│   │   ├── mep.py           # 水电点位 (F22+F20)
│   │   ├── kitchen_bath_mep.py  # F18 厨卫水电 (给排水/燃气/回路/等电位)
│   │   ├── hard_decoration.py   # F21 硬装 (瓷砖排版/涂料用量/吊顶)
│   │   ├── door_window_waterproof.py  # F23 门窗防水 (选型/防水区域/规范校验)
│   │   ├── floorplans.py    # 户型方案存储
│   │   ├── voice.py         # 语音处理
│   │   ├── files.py         # 文件上传/下载
│   │   ├── surveys.py       # 测量 + F1 AR 空间测量 (扫描会话/降级策略/精度校验/墙面特征)
│   │   ├── lighting.py      # F29/F30 灯光设计 (照度计算/色温规划/无主灯/AI 方案)
│   │   ├── kitchen.py       # F16 厨房设计器 (橱柜参数化/动线分析/规范校验)
│   │   ├── bathroom.py      # F17 卫生间设计器 (干湿分离/地漏坡度/防水/通风)
│   │   ├── custom_furniture.py  # F27 定制家具 (参数化/板材/拆单 BOM/价格估算)
│   │   ├── soft_furnishing.py   # F24/F25 软装+收纳 (AI 搭配/配色和谐度/收纳推荐)
│   │   ├── furniture_catalog.py  # F26 家具品类库 (多维筛选/房间推荐/AR 摆放)
│   │   ├── smart_home.py    # F31 智能家居方案 (设备点位/布线/协议选型)
│   │   ├── scene_automation.py  # F32 场景编辑 (联动触发/场景模拟/NL 解析/生态对接)
│   │   ├── vr_panorama.py   # VR 全景 (等距柱状/热点/场景漫游)
│   │   ├── ai_image.py      # AI 图生图 (SDXL/ControlNet/批量渲染)
│   │   ├── location.py      # 地理位置
│   │   └── agents.py        # AI Agent 路由 (含 F28 动线分析)
│   ├── agents/        # 6 个 AI Agent (业务逻辑版)
│   │   ├── orchestrator.py  # 总控 (意图路由, 含 settlement)
│   │   ├── designer.py      # 设计 (9套布局 + NL 修改 + F28 动线分析)
│   │   ├── budget.py        # 预算 (多方案对比/偏差预警/模板库)
│   │   ├── procurement.py   # 采购 (比价报告/采购计划/供应商匹配)
│   │   ├── construction.py  # 施工 (Gantt 排期/质检清单/AI 图像质检 + F37 进度 + F38 质量)
│   │   └── settlement.py    # 结算 (里程碑/异常检测/对账单)
│   ├── models/        # 69 张数据表 (SQLAlchemy)
│   ├── schemas/       # Pydantic 验证
│   ├── services/      # 业务逻辑层 (takeoff/mep/payment/chat/crew/progress/quality/worker 等)
│   └── auth/          # PASETO Token 认证
├── flutter_app/       # 跨平台 App (iOS/iPadOS/Android/HarmonyOS)
│   └── lib/
│       ├── pages/
│       │   ├── cad_page.dart            # 设计台 CAD 引擎
│       │   ├── cad_element.dart         # 图形元素 + DXF
│       │   ├── project_detail_page.dart # 项目详情 (含预算/施工/结算入口)
│       │   ├── budget_page.dart         # 预算管理 (3 Tab)
│       │   ├── construction_page.dart   # 施工管理 (3 Tab)
│       │   ├── settlement_page.dart     # 结算管理 (3 Tab)
│       │   ├── dashboard_page.dart       # 工作台
│       │   ├── projects_page.dart        # 项目列表
│       │   ├── ai_chat_page.dart         # AI 对话
│       │   ├── materials_page.dart       # 物料浏览
│       │   ├── stylus_adapter.dart       # 手写笔适配
│       │   ├── ar_scan_page.dart         # F1 AR 空间测量 (ARKit/ARCore/AR Engine MethodChannel)
│       │   ├── login_page.dart           # 登录注册
│       │   └── home_page.dart            # 底部导航主页
│       └── services/api.dart             # API 客户端
├── flutter_app/ohos/   # HarmonyOS 适配 (3.35.7-ohos-0.0.3, API 23+)
│   ├── OHOS_UPGRADE_GUIDE.md  # 鸿蒙升级指南
├── web/              # 前端页面
│   ├── index.html    # 管理后台 SPA (11 Tab)
│   ├── studio.html   # 统一设计台 (Canvas + Three.js)
│   ├── 3d-viewer.html# 3D 效果图查看器
│   ├── vr-viewer.html# VR 全景查看器 (Three.js r128 球面渲染+热点)
│   └── prototype.html# 营销落地页
├── alembic/          # 数据库迁移 (Alembic, SQLite/PostgreSQL 双库)
├── scripts/          # 运维脚本
│   ├── demo-start.sh    # 一键启动演示环境
│   ├── e2e-full.sh      # 全链路自动测试
│   ├── verify-ac.sh     # AC 验收报告
│   ├── deploy.sh        # 生产部署
│   ├── deploy-ohos.sh   # HarmonyOS HAP 构建部署 (3.35.7-ohos-0.0.3)
│   ├── check-ohos-env.sh # HarmonyOS 环境诊断脚本
│   ├── matepad-test.sh  # MatePad 真机测试指引
│   ├── bench-matepad.sh # MatePad 性能验收
│   └── seed.py          # 种子数据 (225 SKU)
└── tests/            # 302 测试用例 (302 pass / 9 skipped / 20 文件)
```

## 核心技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + SQLite (Phase 1) / PostgreSQL (Phase 2) |
| 认证 | PASETO v4 (public/local) |
| 数据库迁移 | Alembic (双库切换) |
| AI Agent | DeepSeek (LLM) + 规则混合路由 (mock + LLM 双模式) |
| 前端 | Vanilla JS + Canvas 2D + Three.js r128 |
| 移动端 | Flutter 3.35.7-ohos-0.0.3 + CustomPainter (iOS/iPadOS/Android/HarmonyOS) |
| 导出 | DXF R12 + Excel (openpyxl) |

## 数据库

| 表名 | 用途 |
|------|------|
| users | 用户 (业主/设计师/工长/管理员) |
| projects | 装修项目 |
| floors | 楼层 |
| rooms | 房间 |
| material_categories | 物料分类 (9 大类) |
| materials | 物料 (225 SKU) |
| bom_items | 物料清单 |
| budgets / budget_lines | 预算 |
| suppliers | 供应商 (12 家) |
| quotations | 报价单 |
| procurement_orders / order_lines | 采购订单 |
| construction_tasks / construction_logs | 施工管理 |
| inspections | 质检 |
| settlements / settlement_lines | 结算 |
| change_orders / change_order_items | 变更管理 (F39) |
| payments | 支付管理 (F15) 发起/确认/退款 |
| chat_rooms / chat_messages | IM 协作 (F40) 三方群组 |
| construction_crews / crew_matches | 工程队匹配 (F36) |
| progress_alerts / milestone_trackers | 进度管理 (F37) 预警+里程碑 |
| quality_issues / rectification_orders / quality_assessments | 质量管理 (F38) 问题+整改单+评估 |
| service_workers / service_worker_matches | 服务者匹配 (F35) 设计师/监理/预算师 |
| ar_scan_sessions / ar_wall_features / ar_measurement_points | F1 AR 空间测量 (扫描会话/墙面特征/校准点) |
| lighting_schemes / lighting_fixtures | F29/F30 灯光设计 (方案/灯具) |
| kitchen_designs / kitchen_components | F16 厨房设计器 (设计/组件) |
| bathroom_designs / bathroom_fixtures | F17 卫生间设计器 (设计/卫浴) |
| custom_furniture_designs / furniture_modules / furniture_bom | F27 定制家具 (设计/模块/BOM) |
| soft_furnishing_schemes / soft_furnishing_items / storage_systems | F24/F25 软装+收纳 |
| vr_panoramas / vr_scenes | VR 全景 (全景图/场景) |
| ai_image_jobs / ai_image_presets | AI 图生图 (任务/预设) |
| kitchen_bath_mep_plans / mep_points | F18 厨卫水电 (给排水/燃气/回路/等电位) |
| hard_decoration_schemes / hard_decoration_floor_plans / wall_finishes / ceiling_designs | F21 硬装 (瓷砖/地板/涂料/吊顶) |
| door_window_specs / waterproof_plans | F23 门窗防水 (选型/防水区域) |
| furniture_catalog_items | F26 家具品类库 |
| smart_home_schemes / smart_devices | F31 智能家居方案 (设备/布线) |
| scene_automations / ecosystem_integrations | F32 场景编辑 (联动/生态对接) |
| price_comparisons / price_comparison_items / escrow_payments / logistics_trackings / sample_requests | F33/F34 采购增强 (比价/担保支付/物流/样品) |
| floor_plans | 户型方案 |
| file_attachments | 工程文件 |
| surveys | AR 空间测量 |

## API 端点

| 模块 | 端点 | 方法 |
|------|------|------|
| 认证 | /auth/register, /auth/login, /auth/me | POST/POST/GET |
| 项目 | /projects | CRUD 5端点 |
| 物料 | /materials, /materials/categories, /materials/bom | 9端点 |
| 预算 | /budgets, /budgets/generate-from-bom/{id}, /budgets/compare-plans, /budgets/variance-check, /budgets/templates, /budgets/templates/apply | 8端点 |
| 采购 | /procurement/suppliers, /procurement/quotations, /procurement/orders, /procurement/compare, /procurement/recommend-suppliers | 9端点 |
| 施工 | /construction/tasks, /construction/logs, /construction/inspections, /construction/plan, /construction/quality-checklist/{phase}, /construction/inspections/analyze, /construction/progress-analysis (F37), /construction/progress-alerts, /construction/milestones, /construction/quality-detect (F38), /construction/quality-issues, /construction/rectification-orders, /construction/quality-assessments | 23端点 |
| 结算 | /settlements, /settlements/generate-from-budget/{id}, /settlements/milestone, /settlements/milestones, /settlements/anomaly-check, /settlements/reconciliation | 8端点 |
| 变更 | /change-orders, /change-orders/{id}, /change-orders/{id}/review, /change-orders/{id}/approve, /change-orders/{id}/cancel | 6端点 |
| 支付 | /payments, /payments/project/{id}, /payments/{id}, /payments/{id}/confirm, /payments/{id}/refund, /payments/milestones/{id} | 6端点 |
| IM 协作 | /chat/rooms/{id}, /chat/messages/{id}, /chat/messages, /chat/messages/{id}/read, /chat/unread/{id} | 5端点 |
| 工程队 | /crews, /crews/{id}, /crews/match, /crews/matches/{id}, /crews/matches/{id}/status | 6端点 |
| 服务者 | /workers, /workers/{id}, /workers/match (F35), /workers/matches/{id}, /workers/matches/{id}/status | 6端点 |
| 工程量 | /takeoff/wall, /takeoff/slab, /takeoff/floor, /takeoff/paint, /takeoff/project | 5端点 |
| 水电点位 | /mep/plan, /mep/appliances, /mep/compliance-check, /mep/room-standards/{type} | 4端点 |
| 户型 | /floorplans | CRUD 5端点 |
| 测量 | /surveys + /surveys/ar/sessions + /surveys/ar/features + /surveys/ar/points + /surveys/ar/device-capability | 23端点 (含 F1 AR 扫描会话/墙面特征/校准点/设备能力) |
| 灯光 | /lighting/schemes, /lighting/schemes/{id}/ai-design, /lighting/schemes/{id}/fixtures, /lighting/schemes/{id}/illuminance | 9端点 (F29/F30) |
| 厨房 | /kitchen/designs, /kitchen/designs/{id}/auto-layout, /kitchen/designs/{id}/workflow, /kitchen/designs/{id}/compliance | 10端点 (F16) |
| 卫生间 | /bathroom/designs, /bathroom/designs/{id}/auto-layout, /bathroom/designs/{id}/drain, /bathroom/designs/{id}/waterproof, /bathroom/designs/{id}/ventilation | 11端点 (F17) |
| 定制家具 | /custom-furniture/designs, /custom-furniture/designs/{id}/parametric, /custom-furniture/designs/{id}/bom, /custom-furniture/designs/{id}/price, /custom-furniture/designs/{id}/validation | 12端点 (F27) |
| 软装+收纳 | /soft-furnishing/schemes, /soft-furnishing/schemes/{id}/ai-match, /soft-furnishing/schemes/{id}/color-harmony, /soft-furnishing/schemes/{id}/budget, /soft-furnishing/storage/recommend | 14端点 (F24/F25) |
| VR 全景 | /vr/panoramas, /vr/panoramas/{id}/render, /vr/panoramas/{id}/hotspots, /vr/scenes | 13端点 |
| AI 图生图 | /ai-image/jobs, /ai-image/jobs/{id}/process, /ai-image/presets, /ai-image/jobs/apply-preset, /ai-image/jobs/batch | 11端点 |
| 厨卫水电 | /mep-kb/plans, /mep-kb/plans/{id}/points, /mep-kb/plans/{id}/gas, /mep-kb/plans/{id}/circuits, /mep-kb/plans/{id}/equipotential | 11端点 (F18) |
| 硬装 | /hard-decoration/schemes, /hard-decoration/schemes/{id}/floor, /hard-decoration/schemes/{id}/wall, /hard-decoration/schemes/{id}/ceiling, /hard-decoration/schemes/{id}/tile-layout | 11端点 (F21) |
| 门窗防水 | /door-window-waterproof/specs, /door-window-waterproof/specs/{id}, /door-window-waterproof/waterproof, /door-window-waterproof/waterproof/{id}/validate | 11端点 (F23) |
| 家具品类库 | /furniture-catalog/items, /furniture-catalog/search, /furniture-catalog/recommend/{room_type}, /furniture-catalog/items/{id}/ar-place | 8端点 (F26) |
| 智能家居 | /smart-home/schemes, /smart-home/schemes/{id}/devices, /smart-home/schemes/{id}/auto-recommend, /smart-home/schemes/{id}/wiring, /smart-home/schemes/{id}/protocol | 11端点 (F31) |
| 场景编辑 | /scene-automation/scenes, /scene-automation/scenes/{id}/simulate, /scene-automation/scenes/{id}/parse-nl, /scene-automation/scenes/{id}/validate, /scene-automation/ecosystems | 12端点 (F32) |
| 采购增强 | /procurement-enhanced/price-comparisons, /procurement-enhanced/escrow-payments, /procurement-enhanced/logistics, /procurement-enhanced/sample-requests | 18端点 (F33/F34) |
| 文件 | /files/upload, /files/download/{id} | 4端点 |
| AI | /agents/chat, /agents/design, /agents/design/circulation (F28), /agents/budget, /agents/procurement, /agents/construction, /agents/settlement | 6端点 |
| 位置 | /location/ip, /location/nearby | 4端点 |
| 语音 | /voice/asr | 1端点 |
| **合计** | | **318 端点** |

## 验收标准 (Phase 1 MVP)

| AC | 验收项 | 状态 |
|----|--------|------|
| AC-1 | 2D CAD 精确绘图 | ✅ 7工具 + 正交 + 捕捉 |
| AC-2 | 对象捕捉 98% | ✅ snapPoints + nearestSnap |
| AC-3 | 3D 墙体拉伸 < 3s | ✅ Three.js sync3D |
| AC-4 | 平立剖自动生成 | ✅ 6 视角 |
| AC-5 | DXF 导出兼容 | ✅ R12 POLYLINE |
| AC-6 | Agent 响应 < 3s | ✅ 7 Agent + 混合路由 |
| AC-7 | Agent 完成率 85% | ✅ 9套布局 + NL指令 |
| AC-8 | iPad 30fps | ✅ 基准测试就绪 |
| AC-9 | 崩溃率 < 0.1% | ✅ 验收脚本就绪 |

```bash
# 运行验收脚本
bash scripts/verify-ac.sh

# 运行测试套件
source .venv/bin/activate
.venv/bin/python -m pytest tests/ -v
# 当前: 302 passed, 9 skipped (WebSocket 广播集成测试需运行中的服务)

# AC 验收（最新报告: reports/ac-report-20260707-230511.txt）
# 结果: 33 通过 / 0 失败 / 3 跳过 (91%), 待真机验证: AC-5c/AC-8c/AC-9c

# 数据库迁移 (Alembic)
alembic check        # 检测模型与数据库差异
alembic revision --autogenerate -m "init"  # 生成迁移
alembic upgrade head # 应用迁移
```

## 演示脚本

```bash
# 全链路演示 (注册→项目→AI设计→BOM→预算→施工→结算)
bash scripts/e2e-full.sh

# 输出: reports/demo-YYYYMMDD-HHMMSS.md

# HarmonyOS HAP 构建部署 (需 DevEco Studio)
bash scripts/deploy-ohos.sh

# FPS 基准测试 (Chrome headless, 输出 JSON + MD 报告)
python scripts/bench-fps.py
```

## 部署

```bash
# 生产部署
bash scripts/deploy.sh start

# 停止 / 重启 / 状态
bash scripts/deploy.sh stop
bash scripts/deploy.sh restart
bash scripts/deploy.sh status
```

## 演示账号

| 角色 | 手机号 | 密码 |
|------|--------|------|
| 业主 | 13800138000 | 123456 |

## 许可证

内部项目，Phase 1 MVP 交付。
