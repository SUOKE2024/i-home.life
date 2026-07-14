# 实现规划：AI 自治运营群聊工作台

**关联设计**：`docs/superpowers/specs/2026-07-12-ai-autonomous-im-workbench-design.md`
**日期**：2026-07-12

---

## 任务依赖图

```
[T1 基础设施] ──┬─→ [T2 首页 index.html]     ─┐
                ├─→ [T3 登录页 login.html]    │
                ├─→ [T4 工作台 workbench.html] ├─→ [T7 验收]
                └─→ [T5 设置页 settings.html]  ┘
[T6 壁纸复制] ────────────────────────────────┘
```

T1 + T6 必须先完成（提供 CSS/JS/壁纸），然后 T2-T5 可并行。

---

## T1：基础设施（CSS + JS 模块）

### T1.1 创建 `web/assets/css/workbench.css`

共享样式：暗色金调设计 token（沿用 index.html `:root` 变量）+ 工作台布局 + 消息气泡 + 卡片 + 响应式断点（≤1024/≤768/≤480）+ 无障碍（焦点样式、prefers-reduced-motion）+ 壁纸叠加层。

### T1.2 创建 `web/assets/js/api-client.js`

PASETO 自动管理：
- `ApiClient.get/post(url, data)` — 自动附加 `Authorization: Bearer <PASETO>` 头
- `ApiClient.refreshToken()` — 401 时自动刷新
- `ApiClient.login(phone, code)` — 登录获取 PASETO
- `ApiClient.getCurrentUser()` — GET /api/auth/me
- `ApiClient.getMessages(projectId, limit)` — 历史消息
- `ApiClient.decideApproval(id, decision)` — 审批
- `ApiClient.chat(message)` — 自然语言路由

### T1.3 创建 `web/assets/js/im-client.js`

WebSocket 客户端：
- `IMClient.connect(paseto)` — 建立连接
- `IMClient.onMessage(callback)` — 注册消息回调
- `IMClient.send(message)` — 发送消息
- 自动重连（指数退避，最多 5 次）
- 心跳保活（30s）

### T1.4 创建 `web/assets/js/agent-router.js`

自然语言意图识别：
- `AgentRouter.route(text)` — 返回 `{agent, confidence, payload}`
- 关键词匹配 + 简单意图分类（预算/设计/施工/采购/质检/结算/客服/总控）
- 置信度 < 0.7 时返回总控 Agent 澄清

### T1.5 创建 `web/assets/js/message-renderers.js`

7 类消息卡片渲染器：
- `renderText(msg)` — 文本气泡
- `renderTaskCard(msg)` — 任务清单卡片
- `renderPhotoMessage(msg)` — 照片网格
- `renderApprovalCard(msg)` — 审批卡片
- `renderDocumentMessage(msg)` — 文档消息
- `renderBudgetCard(msg)` — 预算卡片
- `renderQuoteCard(msg)` — 比价卡片
- `renderSystemNotice(msg)` — 系统通知
- `renderAgentCollaboration(msg)` — Agent 协作链路

---

## T2：首页 `web/index.html`（重塑）

### 结构
1. Hero 区：LOGO + 主标语 + 副标语
2. 全链路时间轴：6 阶段横向
3. 4 角色入口卡片（2×2 网格）→ 点击跳 login.html?role=owner/designer/supplier/foreman
4. 底部辅助入口：产品方案 / Demo / 我们的故事 / 登录

### 验收
- AC-1：4 张卡片可点击跳转 login.html
- 响应式：≤480 单列、≤768 单列、≤1024 双列
- 无障碍：语义角色、ARIA、键盘导航、焦点样式

---

## T3：登录页 `web/login.html`（新建）

### 结构
1. 卡片式登录表单：手机号 + 验证码（4 位）
2. "获取验证码"按钮（60s 倒计时）
3. 调用 `ApiClient.login(phone, code)` 获取 PASETO
4. 登录成功 → 读取 URL 参数 `role` → 跳转 `workbench.html?role=xxx`
5. 登录失败 → 显示错误提示

### 验收
- AC-2：PASETO 登录成功后跳转 workbench.html
- 响应式 + 无障碍

---

## T4：工作台 `web/workbench.html`（新建）

### 结构
1. 顶栏：‹ 返回 + 群名 + 副标题（阶段 Day N）+ ⋯ 设置
2. 消息流区（可滚动，背景壁纸叠加层）
3. 底栏：+ 附件 / 输入框 / 🎤 语音

### 逻辑
1. 加载时：从 URL 读 `role` + 调用 `ApiClient.getCurrentUser()` 确认身份
2. 调用 `ApiClient.getMessages(projectId, 50)` 加载历史消息
3. 调用 `IMClient.connect(paseto)` 建立 WebSocket
4. `IMClient.onMessage(msg => renderMessage(msg))` 实时渲染
5. 用户输入 → `AgentRouter.route(text)` 或直接 `ApiClient.chat(text)` → 等待 Agent 回复
6. 壁纸：从 18 张随机选一张（sessionStorage），如 localStorage.wallpaper 存在则优先用
7. 角色视角差异：根据 `role` 高亮待办消息 + 显隐操作按钮

### 消息渲染
- 调用 `message-renderers.js` 中对应渲染器
- Agent 消息左侧（带头像+颜色），业主/当前用户右侧
- 审批卡片：业主显示"同意/整改"按钮，其他角色显示"已知悉"

### 验收
- AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12

---

## T5：设置页 `web/settings.html`（新建）

### 结构
1. 账户：头像 / 昵称 / 角色 / 手机号 / 修改密码
2. 通知：4 个开关（待审批/施工日报/质检异常/Agent 协作）
3. 偏好：深色模式 / 语言 / 勿扰时段 / **壁纸选择器**（18 缩略图 + 随机模式开关）
4. 其他：项目档案 / 帮助 / 关于 / 退出登录

### 壁纸选择器
- 18 张缩略图网格 + 1 个"随机模式"选项
- 点击具体壁纸 → `localStorage.wallpaper = 'IMG_xxxx.webp'`
- 选择随机 → `localStorage.removeItem('wallpaper')`
- 实时预览（可选）

### 验收
- AC-9（壁纸应用）
- 响应式 + 无障碍

---

## T6：壁纸资源复制

```bash
mkdir -p web/assets/images/wallpaper
cp /Users/netsong/Developer/suoke_life/assets/images/wallpaper/IMG_*.webp web/assets/images/wallpaper/
```

18 张壁纸从 suoke_life 复制到 web 项目内，避免跨项目依赖。

---

## T7：验收检查

逐条核对 AC-1 ~ AC-12，记录通过/失败。

---

## 执行顺序

1. **阶段 1（同步）**：T1（基础设施）+ T6（壁纸复制）— 主代理直接做
2. **阶段 2（并行）**：T2 + T3 + T4 + T5 — 4 个 Task subagent 并行
3. **阶段 3**：T7 验收 — 主代理核对

---

## 技术约束清单

- ✅ PASETO 不用 JWT
- ✅ API 前缀 /api
- ✅ 不使用 Docker
- ✅ 响应式断点 ≤1024/≤768/≤480
- ✅ 无障碍：语义角色 / ARIA / 键盘导航 / 焦点样式
- ✅ prefers-reduced-motion
- ✅ WebSocket < 3 秒跨端同步
- ✅ 版本号 1.0.0
