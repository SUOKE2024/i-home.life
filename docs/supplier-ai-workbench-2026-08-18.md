# 供应链/服务商生态 AI 工作台 — 设计与落地报告（2026-08-18）

> 版本：v1.15.4 · 目标：让 `supplier` 角色获得「可管理、可运营 + AI 协助」的专属工作台，
> 并修复角色触达体系中的真实授权缺口。原则：复用既有底座（业务 API / 25 Agent / 组件家族），
> 模块化单体内渐进落地，不引入新服务。

## 1. 触达体系复评结论（落地前基线）

- 前端三端均为「登录后全量展示」，无角色差异化导航；
- 后端 `PermissionChecker` 权限码体系休眠（`app/api/` 零使用），`DEFAULT_ROLE_PERMISSIONS`
  不被任何运行时路径消费，也无 `/me/permissions` 菜单出口；
- **授权缺口（P0）**：`app/api/products.py` 创建产品条件 `role != "supplier" and not is_verified`
  允许任何已认证用户发布产品（已认证设计师/业主可越权，未认证供应商反可直通）。

## 2. Phase 1 — 权限安全（后端）

- **`app/rbac.py`**：
  - `PermissionChecker` 升级为「admin 直通 → DB `RolePermission` 行 → `DEFAULT_ROLE_PERMISSIONS`
    默认映射兜底 → 403」四级判定（默认映射兜底使权限码体系无 seed 即生效，DB 行可增删覆盖）；
  - `DEFAULT_ROLE_PERMISSIONS["supplier"]` 扩展 `product:write / order:read / quote:write /
    fulfillment:update / settlement:read`；
  - 新增 `get_default_permission_codes / get_all_permission_codes / get_effective_permission_codes`
    （生效权限码 = 默认映射 ∪ DB 行，admin 返回全集）。
- **`app/api/products.py`**：创建产品门控改为 `role in ("supplier", "admin")`（修复缺口；
  实名认证属平台审核策略，由身份认证流程独立管理，不双重拦截）。
- **`app/api/auth.py`**：新增 `GET /auth/me/permissions` 菜单出口（返回 `{role, permissions}`），
  供三端按角色渲染导航；admin 管理端点（`/admin/roles/{role}/permissions`）可动态调整。
- **测试** `tests/test_supplier_rbac.py`（8 用例）：已认证设计师创建产品 403（缺口复现）、
  业主 403、供应商放行、三种角色 `/me/permissions` 映射、PermissionChecker 默认映射兜底
  （直调真实 checker 判定逻辑）。

## 3. Phase 2 — Console 供应商工作台（可管理、可运营）

- **`context/UserContext.tsx`**：AuthGate 校验 token 成功后注入用户上下文（含 role/sub_role）。
- **`SideNav.tsx`**：`NavGroup` 增 `adminOnly`/`roles` 白名单；「管理后台」组仅 admin 可见；
  新增「供应商」组（供应商工作台 /supplier，仅 supplier/admin 可见）。admin 恒见全部，
  后端 403 兜底（双层防御）。
- **`pages/SupplierWorkbenchPage.tsx`**：
  - 看板三卡（真实 API，失败诚实显示 `—`）：我的产品 `GET /api/products/mine`、交付单
    `GET /api/b2b/delivery`、生效权限码 `GET /auth/me/permissions`（stat-value 等宽数字）；
  - 六模块入口：产品/物料/采购与交付/资金托管/预算/设置（复用既有页面，不造新后端）；
  - 布局复用 `SuokeLayout` + B 端深色工程台 token。
- **冗余清理**：删除 `PlaceholderHome.tsx` + `/tokens` 占位路由（批次 1 验证页，自述已被
  WorkbenchPage 取代，且色板注释含废弃 #6B6978）。

## 4. Phase 3 — AI 协助 + Flutter 角色导航

- **Console AI 经营助手**（工作台内嵌）：复用 `apiClient.streamChat` 路由
  `agent_type=procurement`，预设提示词（寻源匹配/产品文案/履约答疑/经营简报）+ 自由输入，
  SSE token 增量渲染；error/done 无文本时诚实降级（不生成占位假回复）。走 harness 链路
  自动落 trace/Case/Skill 自进化。
- **Flutter**：`home_page` 拉取 `/auth/me` 角色（best-effort），supplier 底部导航渲染
  供应商 tab 集（首页/交付 `/b2b-delivery`/产品 `/products`/我的），其余角色保持默认
  四 tab；交付/产品页已在 v1.15.3 路由表中注册可达。

## 5. 验证与门禁

| 门禁 | 结果 |
|------|------|
| pytest 全量 | 2506 passed + 2 skipped + 4 xfailed（2499 基线 + 7 新用例，无回归） |
| 定向回归 | test_auth/test_auth_security_fixes/test_admin 48 passed |
| pre-commit / mypy | 全绿（含 flake8 新测试文件）/ 374 文件 0 issue |
| console 构建（tsc + vite） | 通过 |
| flutter analyze | 0 issues |

## 6. 版本与文档

- 版本 1.15.3 → 1.15.4 全链路同步（config/.env×4/MCP SERVER_VERSION/Flutter
  1.15.4+53/webapp+lock+version.json/console 1.15.4.0+lock/ci×3/deploy/测试断言×3）；
- 本文档 + CHANGELOG 1.15.4 节 + README/CODE_WIKI 状态行。

## 7. 遗留（诚实标注，留待后续）

> v1.15.6 已闭环两项：供应商每日经营简报（`GET /api/admin/supplier-daily-briefing`，
> FC 定时触发器复用 daily-briefing 模式）与 B2B 端点角色语义（创建/流转限
> contractor/supplier/admin，业主/设计师 403）。剩余：

- 供应商子角色（品类供应商/物流服务商等）仅做数据约定（`sub_role` 字段），未做独立权限区分；
- 供应商简报当前为「平台聚合」视角（单份全生态报告），未做 per-supplier 定制推送
  （工作台内 AI 助手可手动触发个人经营问答，FC 简报为全局版）；
- 工作台未接入 A2UI 卡片流与文件上传（复用 WorkbenchPage 已有能力属后续增强项）。
