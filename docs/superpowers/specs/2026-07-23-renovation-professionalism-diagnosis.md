# 索克家居家装功能专业性诊断与解决方案

> 诊断日期：2026-07-23
> 诊断范围：家装功能全量全链路（需求理解→设计生成→深化设计→报价→采购→施工→交付）
> 方法论：2026 行业最新技术对标 + 源码逐模块核验（主代理亲自 Read，非依赖 subagent 结论）
> 约束遵循：不使用 Docker；PASETO；feature flag 灰度；改动可回滚

---

## 一、2026 行业最新技术基准（网络调研结论）

### 1.1 "空间智能"成为新范式（飞流AI 3.0 / 酷家乐 2026 白皮书）

中国建筑装饰协会《2026 中国智能家装设计行业发展白皮书》首次系统定义"空间智能"三能力，这已成为 2026 家装 AI 的行业门槛：

| 能力 | 定义 | 索克对标 |
|------|------|----------|
| **空间感知** | 软件能"理解"每面墙、每根梁、每个管道的物理属性（尺寸/材质/承重） | ❌ 缺失 |
| **空间推理** | 根据生活习惯自动优化动线/采光/收纳，规避设计错误（沙发挡过道、插座被柜遮挡） | ❌ 缺失 |
| **空间交互** | 设计方案无缝转化为施工指令、采购清单，多角色（业主/设计师/工长）实时协作 | ⚠️ 部分（采购侧已实现，设计→施工指令缺失） |

范式转移：从"像素生成"（出效果图）→"物理感知"（BIM 毫米级坐标，可指导施工）。飞流AI 提供完整链路：需求理解→设计生成→深化设计→报价计算→产品购买→施工协同→线下交付。

### 1.2 AI 渲染：从"幻觉债"到"几何锁定"（2026 强制标准）

- **Geometry Locking 强制化**：2023-2025 的"幻觉债"已结算，顶级工具用 ControlNet 架构把几何约束当硬边界（不 hallucinate 墙、不擦承重柱）
- **Material Permanence**：材质一致性，可指定具体材料不漂移
- **专业工具栈**：Rendair AI（sketch-to-image + 模型保留）/ Luma AI（Gaussian Splatting 站点扫描）/ Rayon（2D 协同平面图）/ Midjourney（概念）
- **关键洞察**：行业已放弃"单一魔法按钮"，转向"多工具链式协作"，每阶段用专门引擎

### 1.3 BIM 算量：正向设计算量 + AI 一键建模

- **EasyBIM 2026**："正向设计算量"——工程量反馈前移到设计阶段（传统是施工图后翻模算量，滞后且重复），覆盖土建+钢筋算量
- **Vibe BIM**：MLLM + 图神经网络(GNN) + 语义规则 + 过程化几何引擎，从 2D 图纸/PDF 一键生成 IFC BIM 模型，断线容错、隐式信息 LLM 补全
- **鲁班数字精装**：1:1 BIM 布尔运算精准算工程量，智能匹配企业定额自动生成预决算，模型即图纸（改模型图纸自动更新），效率提升近 10 倍
- **开源底座**：ifcopenshell（IFC4）、FreeCAD BIM 工作流（60+ 构件类型、碰撞检测、自动施工图）

### 1.4 AR/VR + LiDAR：实景捕获到物料 takeoff

- **Kaleidoscope / CamPlan / magicplan**：LiDAR/RoomPlan 扫描→户型图→材料 takeoff（油漆/瓷砖/地板/干墙自动算量）→承包商 PDF（含墙明细表/测量报告/热负荷）
- **Hover**：手机照片→可测量 3D 模型→真实品牌材料设计→材料 takeoff→下单，"两点击材料清单"
- **核心价值**：扫描即测量，测量即算量，算量即下单——消灭"先买错后重买"

### 1.5 智能家居：设计阶段就要规划（2026 落地指南）

- 装修水电预埋是关键时机（砸墙代价 3-5 倍）：每个开关底盒留零线、取消传统双控布线、Cat6 到每个房间
- **Matter 协议**：跨品牌"翻译官"，2026 设备快速增长，优先选 Matter 兼容避免生态锁定
- 智能点位（传感器/开关/门锁/窗帘电机/安防）必须在设计阶段定位，不能后期 retrofit

---

## 二、索克家居全链路诊断（源码逐模块核验）

> 价值链对标飞流AI：需求理解→设计生成→深化设计→报价→采购→施工→交付

### 2.1 链路断点总览

```
需求理解 ✅ → 设计生成 ❌ → 深化设计 ❌ → 报价 ❌ → 采购 ✅ → 施工 ⚠️ → 交付 ⚠️
   chat        design_       IFC/takeoff    BOM?       procurement  construction  settlement
               deepening     (stub)        (断链)     (专业)
               (CRUD list)
```

**核心结论：链路在中段（设计→深化→报价）断裂，恰是家装专业性的心脏。两端（采购/施工）反而专业，呈现"哑铃型"不均衡。**

### 2.2 严重缺陷逐项（附 file:line 证据）

#### 缺陷 D1：AI 渲染是纯 stub，制造"幻觉债"（最严重）

**证据**：[app/services/ai_render_service.py](file:///Users/netsong/Developer/i-home.life/app/services/ai_render_service.py)

- L96-104 `render_2d` 返回 `placeholder_image_url = placehold.co/800x600/png?text=AI+Render+...` —— **占位图，非真实渲染**
- L150-161 `render_3d` 返回硬编码 `reconstruction_params = {"method":"3dgs","iterations":30000,...}` —— **这些参数从未执行，3D 高斯泼溅不存在**
- L326-336 `_detect_room_type` = `room_types[len(photo_data) % len(room_types)]` —— **用照片字节数取模伪造房间类型**
- L261-315 `_get_mock_response` —— 无 API key 时返回 `model_used: "mock-sd-xl"`
- 无任何 Stable Diffusion / ControlNet / 真实图像生成调用

**专业性差距**：2026 行业已强制 Geometry Locking + Material Permanence，索克连基础图像生成都没有，停留在"prompt 文本 + 占位图"。这直接违背白皮书"从像素生成到物理感知"的范式转移。

#### 缺陷 D2：IFC 导出几何有效但空间无意义

**证据**：[app/services/ifc_export_service.py](file:///Users/netsong/Developer/i-home.life/app/services/ifc_export_service.py)

- L283 `placement = _create_local_placement(f, point=(float(i * 5000), 0.0, 0.0), ...)` —— **所有墙体在 X 轴一字排开，5m 间隔，非真实户型坐标**
- L310 梁 `point=(i*5000, len(walls)*3000, 2800)` —— 几何位置与设计无关
- L441 `export_design_to_ifc` 从 floorplan.data 解析 walls，但 placement 仍是 `point=(i*5000, 0, 0)` —— **读了户型数据却丢弃坐标**
- 无 Pset 属性集（防火等级/热阻/材质），无 MEP 水电管线，无门窗洞口扣减

**专业性差距**：飞流AI "BIM 毫米级坐标，可指导施工"；索克 IFC 几何体有效但摆放是假的，无法用于施工协调/碰撞检测/算量。

#### 缺陷 D3：工程量计算是无状态计算器，与设计/BOM 断链

**证据**：[app/api/takeoff.py](file:///Users/netsong/Developer/i-home.life/app/api/takeoff.py)

- L43-103 全部端点接收 `WallTakeoffRequest(length, height, thickness)` —— **手工输入参数，不读项目/户型/BOM**
- 无持久化、无项目关联、无 `project_id`

**证据**：[flutter_app/lib/pages/takeoff_page.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/takeoff_page.dart)

- L40-46 `_priceBrick=380 / _priceConcrete=450 / _priceRebar=5...` —— **价格硬编码在前端**
- L364-371 总造价用前端硬编码单价计算

**专业性差距**：鲁班/EasyBIM 是"正向设计算量"（从 BIM 模型布尔运算），索克是"手工输入长宽高 + 前端硬编码单价"。价格应来自材料库 Material 表，工程量应从户型几何自动派生。

#### 缺陷 D4：设计深化是 CRUD 列表，无真实设计工具

**证据**：[flutter_app/lib/pages/design_deepening_page.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/design_deepening_page.dart)

- L87-91 `createPlan` 提交 `data: '{}'` —— **设计方案 data 字段是空 blob**
- L222-316 列表只展示 name/area/rooms/height —— 无墙体绘制、无家具布置、无门窗定位
- L36 `_api.get('/floorplans/project/...')` —— 纯记录管理

**对照**：[flutter_app/lib/pages/cad_page.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/pages/cad_page.dart) 有基础 2D 绘图（CustomPaint + DrawingElement 线/矩形 + 正交锁 L71-75），但：
- 绘制的"线"不成为"墙"（无厚度/材质/门窗洞口），是非参数化涂鸦
- 与 floorplan.data / IFC / takeoff 无数据流通

**专业性差距**：酷家乐"10 分钟全案、模型即图纸"；索克设计页是空记录 + 独立涂鸦工具，两者不连通。

#### 缺陷 D5：施工图自动生成完全缺失

**证据**：`grep -rn "施工图|construction_draw|drawing_gen|2d_draw" app/ flutter_app/lib/` —— **零命中**

- 无从 3D/BIM 模型自动生成平/立/剖面图的能力
- 无标注自动读取构件属性
- 无"改模型图纸自动更新"的关联性

**专业性差距**：鲁班"生成施工图效率提高近 10 倍"、酷家乐"模型即是图纸避免反复修改"、EasyBIM"画图即建模建模即出图"——这是 2026 行业基本盘，索克缺失。

### 2.3 已具备的专业能力（不均衡的"长板"）

为公正起见，以下模块经核验是**真专业实现**，证明团队有专业交付能力：

| 模块 | 证据 | 专业度 |
|------|------|--------|
| 采购增强 | [app/api/procurement_enhanced.py](file:///Users/netsong/Developer/i-home.life/app/api/procurement_enhanced.py) L1-790 | ⭐⭐⭐⭐⭐ 担保支付全生命周期+物流追踪+样品索要+AI比价，IDOR 防护完备 |
| 硬装模块 | [app/api/hard_decoration.py](file:///Users/netsong/Developer/i-home.life/app/api/hard_decoration.py) L1-80+ | ⭐⭐⭐⭐ 瓷砖排版/涂料用量/吊顶设计 + 协作者权限(F40) |
| BOM 模型 | [app/models/material.py](file:///Users/netsong/Developer/i-home.life/app/models/material.py) L49-73 | ⭐⭐⭐ BOMItem 含 room_id 关联 + status 状态机 + CheckConstraint 校验 |
| AR 扫描 | flutter_app/lib/pages/ar_scan_page.dart (3621 行) | ⭐⭐⭐⭐ 深度实现，待核验扫描→户型链路 |
| 自定义家具 BOM | app/services/custom_furniture_service.py:385 `generate_bom` | ⭐⭐⭐ 家具级 BOM 生成 |

**关键洞察**：采购侧（bom_id → 比价 → 担保 → 物流）链路完整且专业，但**生成 bom_id 的上游**（从设计/户型自动生成 BOM）是断点。`material_service.generate_bom_for_project` 存在但需核验是否读取户型几何（D3/D4 暗示未连通）。

### 2.4 feature flag 全开但背后是 stub（架构隐患）

**证据**：[app/config.py](file:///Users/netsong/Developer/i-home.life/app/config.py)

- L105 `ai_render_enabled: bool = True`
- L127 `filament_enabled: bool = True`
- L132 `opencascade_enabled: bool = True`

flag 默认 True，但 `ai_render_service` 是 stub（D1）、filament(3D渲染)/opencascade(CAD内核) 实际接入情况待核验。**这违背项目约定"长线技术决策需 feature flag 灰度"——flag 应保护真实实现而非掩盖 stub。**

---

## 三、五大核心问题总结

| 编号 | 问题 | 严重度 | 对标差距 |
|------|------|--------|----------|
| **P1** | AI 渲染纯 stub（占位图+伪随机），制造幻觉债 | 🔴 致命 | 2026 已强制 Geometry Locking |
| **P2** | 设计→BOM→报价链路断裂，工程量手工输入+前端硬编码价 | 🔴 致命 | 行业正向设计算量，索克逆向手工 |
| **P3** | IFC 导出空间坐标造假，无法指导施工 | 🟠 严重 | 飞流 BIM 毫米级可施工 |
| **P4** | 无施工图自动生成，模型与图纸不关联 | 🟠 严重 | 鲁班/酷家乐模型即图纸 |
| **P5** | 2D CAD 是非参数化涂鸦，不生成 BIM 构件 | 🟡 中等 | EasyBIM 画图即建模 |

**根因诊断**：项目按"模块齐全度"推进（已有 60+ API 端点、50+ Flutter 页面），但按"价值链贯通度"评估则中段断裂。专业性不足的本质是**重广度轻深度、重端点轻链路**——procurement 这种"末端闭环"做得好，而"设计→算量→报价"这种"中段贯通"没做。

---

## 四、解决方案（分层、feature flag、可回滚）

### 4.1 总体策略：补中段、贯通链路、对标空间智能

```
[L0 观测] 诊断基线 + 链路贯通度自动化测试
    ↓
[L1 数据贯通] 设计→几何→BOM→算量→报价 单一数据源(SSOT)
    ↓
[L2 真实能力] AI 渲染去 stub + IFC 真实坐标 + 施工图生成
    ↓
[L3 空间智能] 空间感知/推理/交互 三能力（对标飞流）
```

### 4.2 L1 数据贯通层（最高优先级，解决 P2）

#### S1：建立"户型几何单一数据源(SSOT)"

- **目标**：floorplan.data 成为唯一权威几何源，takeoff/IFC/BOM 全部从它派生
- **改动**：
  - `material_service.generate_bom_for_project` 改为读取 floorplan.data 几何（墙体面积/地面面积/门窗洞口）自动派生 BOM 项
  - `takeoff` 端点新增 `project_id` 参数，从 floorplan 几何自动取参，废弃手工输入
  - 前端 `takeoff_page.dart` 硬编码价格迁移到 Material 表 `unit_price` 字段
- **feature flag**：`bom_from_geometry_enabled`（默认 False，灰度切换）
- **回滚**：flag=False 回退到手工 BOM 录入

#### S2：工程量正向算量引擎

- **目标**：从 floorplan 几何布尔运算算工程量（对标鲁班/EasyBIM 正向设计算量）
- **改动**：
  - 新增 `app/services/quantity_takeoff_service.py`：输入 floorplan.data，输出按房间/分项的工程量
  - 墙体：长度×高度−门窗洞口=净面积→涂料/壁纸/瓷砖算量
  - 地面：房间面积×损耗系数→瓷砖/地板块数
  - 吊顶：房间面积→吊顶板材算量
- **feature flag**：`forward_takeoff_enabled`
- **对标**：鲁班"1:1 BIM 布尔运算精准算工程量"

### 4.3 L2 真实能力层（解决 P1/P3/P4/P5）

#### S3：AI 渲染去 stub，接入真实几何锁定渲染

- **目标**：消灭占位图，接入 ControlNet 几何锁定 + Material Permanence
- **改动**：
  - `ai_render_service` 新增真实渲染后端选项：
    - 选项A（推荐）：接入开源 Stable Diffusion + ControlNet（canny/depth），本地或 GPU 服务
    - 选项B：接入第三方 API（如 Rendair/Replicate），prompt 保留现有 LLM 生成逻辑
  - `_detect_room_type` 替换为真实视觉模型（CLIP/BLIP 分类）
  - 3D 渲染：接入真实 3D Gaussian Splatting 或退化为"2D 多视角"诚实降级（不伪造 reconstruction_params）
- **feature flag**：`real_ai_render_enabled`（保留 `ai_render_enabled` 作 mock 兜底）
- **回滚**：flag=False 回退到现有 stub（占位图），保证不崩
- **对标**：2026 Geometry Locking 强制标准

#### S4：IFC 导出真实坐标 + 属性集

- **目标**：IFC 可指导施工（对标飞流毫米级）
- **改动**：
  - `ifc_export_service.export_design_to_ifc`：墙体 placement 用 floorplan.data 的真实 start/end 坐标（已有 L431-436 的 length 计算，扩展为完整 placement）
  - 新增 Pset_WallCommon（防火等级/热阻/材质）、Pset_DoorCommon
  - 新增 IfcRelVoidsElement 门窗洞口扣减
  - 接入 MEP（mep_service）数据导出 IfcDistributionFlowElement 水电管线
- **feature flag**：`ifc_real_placement_enabled`
- **对标**：飞流"BIM 毫米级坐标可指导施工"

#### S5：施工图自动生成

- **目标**：从 floorplan/structural 模型自动生成平/立/剖面图（对标鲁班/酷家乐）
- **改动**：
  - 新增 `app/services/construction_drawing_service.py`：
    - 平面布置图：从 floorplan.data 渲染 2D 俯视（墙体/门窗/家具标注）
    - 立面图：按墙面投影生成
    - 水电图：叠加 MEP 管线
  - 输出 SVG/PDF（前端 cad_page 的 CADPainter 可复用渲染逻辑）
  - "模型即图纸"：floorplan.data 改动 → 图纸自动重生成
- **feature flag**：`construction_drawing_enabled`
- **对标**：鲁班"模型即图纸避免反复修改，效率提升近 10 倍"

#### S6：2D CAD 参数化升级

- **目标**：画线即建墙（对标 EasyBIM"画图即建模"）
- **改动**：
  - `cad_page.dart` 的 DrawingElement 升级为 BIM 构件：线→墙(带厚度/材质/层高)，矩形→房间(带功能/面积)
  - 绘制时同步写入 floorplan.data，触发 S2 算量 + S5 施工图重生成
- **feature flag**：`parametric_cad_enabled`
- **对标**：EasyBIM"画图即建模，建模即出图"

### 4.4 L3 空间智能层（对标飞流，中长期）

#### S7：空间感知——户型结构理解

- 从 AR 扫描/ar_scan_service 的点云/照片识别承重墙、梁、管道（对标飞流物理空间智能引擎）
- 结构化存档水电管线、隐蔽工程（对标酷家乐 Aholo 3D 高斯泼溅"房屋数字档案"）
- **feature flag**：`spatial_perception_enabled`

#### S8：空间推理——设计错误规避

- 规则引擎：沙发挡过道、插座被柜遮挡、门开启半径碰撞、采光遮挡
- 动线/收纳/采光自动优化建议
- **feature flag**：`spatial_reasoning_enabled`

#### S9：空间交互——多角色施工协同

- 设计方案→施工指令→采购清单 转化（采购侧已具备，补设计→施工指令）
- 业主/设计师/工长实时协作（F40 协作者权限已具备，补方案评论/批注在线流转）
- **feature flag**：`spatial_interaction_enabled`

---

## 五、实施优先级与里程碑

| 阶段 | 任务 | 优先级 | 依赖 | 预估 |
|------|------|--------|------|------|
| **M1** | S1 SSOT 数据贯通 + S2 正向算量 | P0 | 无 | 解决 P2，链路贯通 |
| **M2** | S3 AI 渲染去 stub | P0 | M1 | 解决 P1，消除幻觉债 |
| **M3** | S4 IFC 真实坐标 + S5 施工图生成 | P1 | M1 | 解决 P3/P4 |
| **M4** | S6 参数化 CAD | P1 | M1/M3 | 解决 P5 |
| **M5** | S7-S9 空间智能三能力 | P2 | M1-M4 | 对标飞流，差异化 |

---

## 六、验收标准（链路贯通度）

新增自动化测试，验证"设计→算量→报价→采购"全链路数据流通：

1. **SSOT 测试**：修改 floorplan.data 一面墙 → BOM 项数量自动更新 → 报价金额自动更新
2. **算量准确性测试**：给定标准户型几何，工程量与手工核算误差 < 3%
3. **渲染真实性测试**：AI 渲染返回真实图像（非 placehold.co），含 Geometry Locking（墙体不被 hallucinate）
4. **IFC 可施工性测试**：导出 IFC 在第三方 BIM viewer 中墙体位置与 floorplan 一致
5. **施工图关联性测试**：改 floorplan → 施工图自动重生成，无人工干预

---

## 七、与 v1.1.27 性能工程的衔接

v1.1.27 已建立 L3 观测框架、索引迁移、缓存装饰器、feature flag 体系。本次专业性提升应复用：

- 复用 feature flag 机制（新增 7 个 flag：bom_from_geometry / forward_takeoff / real_ai_render / ifc_real_placement / construction_drawing / parametric_cad / spatial_*）
- 复用 cache_decorator 缓存算量结果（floorplan 未变则算量走缓存）
- 复用 slow_query_log 监控 SSOT 派生查询性能
- 复用 verify_project_access / verify_project_collaborator_access 做新增端点的越权防护
- 版本定为 v1.2.0（专业性大版本），所有改动配套回滚脚本

---

## 附：调研来源

- 飞流AI 3.0 / 2026 中国智能家装设计行业白皮书（空间智能定义）
- 酷家乐 2026.7 产品动态 / AI+大家居全链路（Aholo 3D 高斯泼溅、算量2.0）
- Adobe 2026 AI Interior Design Survey（49% 美国人已用 AI，省 $371）
- Rendair/Luma AI/Rayon 2026 专业工具栈
- EasyBIM 2026（正向设计算量）、Vibe BIM（MLLM+GNN 一键建模）、鲁班数字精装（布尔运算算量）
- ifcopenshell / FreeCAD BIM 工作流（IFC4 标准）
- Kaleidoscope/CamPlan/Hover（LiDAR→takeoff→下单）
- 2026 智能家居落地指南（Matter 协议、装修预埋）
