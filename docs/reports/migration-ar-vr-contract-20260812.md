# AR/VR 三端契约统一 + AR API 拆分 — 迁移指南

> 日期：2026-08-12 · 涉及版本：v1.14.x（Unreleased）
> 背景：AR/VR/XR 全景全量全链路评估发现 6 处契约不一致，本次统一三端事实标准，
> 并将 F1 AR 空间测量 API 自 surveys.py 拆分独立模块。**后端 API 路径与响应结构零变更**，
> 存量客户端不受影响；本文档面向后续开发与历史数据兼容说明。

---

## 1. 变更总览

| 变更 | 类型 | 存量影响 |
|---|---|---|
| AR API 拆分 `app/api/ar_scan.py` | 后端代码组织 | 无（路径/响应不变） |
| 转场类型收敛 `fade/warp/none` + Literal 校验 | 契约收紧 | 旧值 dissolve/slide 将被 422 拒绝 |
| 热点坐标统一球面 `{yaw, pitch}` | 前端表单对齐 | 服务端兼容旧 x/y/z 数据 |
| 状态枚举三端对齐 | 前端展示映射 | 无 |

---

## 2. AR API 拆分（后端开发者）

**变更前**：F1 AR 空间测量路由全部挂在 `app/api/surveys.py`（前缀 `/surveys/ar/*`）。
**变更后**：新建 `app/api/ar_scan.py`（`APIRouter(prefix="/surveys/ar")`），
`app/main.py` 中 `include_router(ar_scan.router)`（位于 surveys.router 之后），
`surveys.py` 仅保留 Survey 测量记录本体。

- 路由清单（全部原路径保留）：`POST /device-capability`、`/sessions` CRUD、
  `/sessions/{id}/start|process|accuracy|apply`、`/features`、`/points`
- 对客户端：**零迁移动作**（URL 前缀 `/api/surveys/ar/*` 未变）
- 对后端维护者：改 AR 相关 API 请编辑 `app/api/ar_scan.py`，勿回写 surveys.py

---

## 3. 三端契约统一

### 3.1 状态枚举（前端展示映射）

后端事实标准（`app/models/vr_panorama.py`）：

- 全景图 `status`：`queued / rendering / completed / failed`
- VR 场景 `status`：`active / archived`

三端映射表：

| 后端值 | Flutter 标签 | console 标签 | webapp 标签 |
|---|---|---|---|
| queued | 排队中 | 排队中 | 排队中 |
| rendering | 渲染中 | 渲染中 | 渲染中 |
| completed | 已完成 | 已完成 | 已完成 |
| failed | 失败 | 失败 | 失败 |
| active | 生效中 | — | — |
| archived | 已归档 | — | — |

> 旧前端值 `draft/processing/published/rendered/pending` 已从映射中移除；
> console 保留 `pending` 兜底兼容历史数据，新增代码请勿使用旧值。

### 3.2 热点坐标：笛卡尔 → 球面（推荐 yaw/pitch）

后端 `HotspotPosition`（`app/schemas/vr_panorama.py`）：

```
yaw:   水平方位角（度），0=正北，顺时针为正，范围 [-360, 360]
pitch: 俯仰角（度），0=水平，正值抬头，范围 [-90, 90]
```

创建热点请求示例：

```json
// 变更前（x/y/z 笛卡尔，已废弃）
{ "type": "panorama", "label": "进入主卧",
  "position": { "x": 1.5, "y": 0.0, "z": 2.0 },
  "target_panorama_id": "..." }

// 变更后（yaw/pitch 球面，推荐）
{ "type": "panorama", "label": "进入主卧",
  "position": { "yaw": 45.0, "pitch": 0.0 },
  "target_panorama_id": "..." }
```

- 服务端仍兼容读取旧 `{x, y, z}` 热点（列表展示按字段自动分支）
- 全景查看器（webapp Three.js / Flutter 预览）均按 yaw/pitch 渲染热点
- **新代码必须提交 yaw/pitch**；历史数据如需在查看器展示，建议脚本转换为球面坐标

### 3.3 转场类型：fade / warp / none（后端强制校验）

后端 `VRSceneCreate/VRSceneUpdate.transition_type` 已加 `Literal["fade", "warp", "none"]`
校验——提交 `dissolve/slide` 等旧值将返回 422。

| 值 | 含义 |
|---|---|
| fade | 淡入淡出（过渡 1.5s） |
| warp | 穿梭（过渡 0.8s） |
| none | 无转场 |

---

## 4. 各端迁移动作清单

| 端 | 已落地位置 | 后续注意 |
|---|---|---|
| Flutter | `vr_panorama_page.dart`：状态映射/转场 dropdown/yaw·pitch 表单/场景卡移除 `thumbnail_url` 读取 | 新增场景转场只传 fade/warp/none |
| console | `VRPanoramaPage.tsx`：状态标签对齐 | 新增状态映射对齐上表 |
| webapp | `VirtualTour.jsx`：状态徽标；`ARScan.jsx`：设备能力检测 | 热点按 yaw/pitch 提交 |
| 后端 | `schemas/vr_panorama.py` Literal 校验；`app/api/ar_scan.py` 拆分 | 改 AR 路由去 ar_scan.py |

---

## 5. 兼容性与回滚

- **回滚**：`app/api/ar_scan.py` 删除 + main.py 移除 include 即可回到 surveys.py 内嵌形态
  （路径不变，无数据迁移）
- **转场 Literal 校验**：如遇存量客户端仍提交 dissolve/slide，需先升级客户端再保留校验；
  紧急回滚可移除 `Literal` 约束（不推荐，会重新引入契约漂移）
- **热点旧数据**：x/y/z 热点的查看器展示为"位置不可映射"，仅信息展示不受影响

---

## 6. 相关文件

- 后端：`app/api/ar_scan.py`（新）、`app/api/surveys.py`、`app/main.py`、
  `app/schemas/vr_panorama.py`、`app/models/vr_panorama.py`
- 前端：`flutter_app/lib/pages/vr_panorama_page.dart`、
  `console-src/src/pages/VRPanoramaPage.tsx`、
  `webapp/src/pages/VirtualTour.jsx`、`webapp/src/pages/ARScan.jsx`
- 测试：`tests/test_vr_panorama.py`（新增 `test_create_scene_rejects_invalid_transition`）
