# 索克家居小程序（miniapp）

> 索克家居 · 空间健康资产运营商 —— 面向存量空间的「改造交付 + 智能运营」业主端小程序。
> 技术栈 Taro 4.3.0（React 18 + TypeScript），与索克生活 / 索克俱乐部同一 Taro 基线。
> 一套代码覆盖微信小程序 / H5 / 支付宝 / 抖音四端。

## 当前状态（2026-10-26 · v1.1.0）

| 维度 | 状态 |
|------|------|
| Taro 版本 | 4.3.0（与生活 / 俱乐部统一） |
| 页面 | 11 页（5 个 tab + 4 个详情 + 条款 + 提交需求），全部实体页 |
| 构建 | `build:weapp` / `build:h5` 通过（dist 724K） |
| 类型检查 | `npm run typecheck` 通过 |
| APPID | `wxe8653cb1e81b6dc1`（索克家居，主体：索克(昆明)联合科技有限责任公司，已写入 `project.config.json`） |
| 数据源 | **真实后端优先**：`https://i-home.life/api`（生产 v1.19.0）；缺省回落 `src/data/*` 演示数据并在界面标注 |
| 登录 | 微信小程序 `wx.login` 静默登录 → `POST /api/auth/miniprogram/login`（**生产已上线并实测**）；手机号走 `getPhoneNumber` code 换号 |
| AI 管家 | 接 `/api/agents/concierge/chat`（真实 LLM）→ 失败降级 `/api/ai-qa/search`（带引用）→ 再降级本地示例 |
| 上线 | 后端通道已通；**卡在平台侧：微信认证（未通过）→ ICP 备案 → 服务器域名 → 代码上传密钥** |

> 诚实边界：H5 / 支付宝 / 抖音端后端暂无对应登录通道，按「访客态 + 演示数据」运行，界面会显示「演示数据」标识；
> 补贴预估非资格认定，健康数据非医疗诊断，AI 回复不构成承诺。

## 数据链路

```
页面 (pages/*)
  └── callFunction(name, payload)          src/services/cloud.ts
        ├── 优先：src/services/api.ts      → Taro.request → https://i-home.life/api
        │        └── src/services/adapters.ts  DTO → 视图模型（枚举逐项对齐后端）
        ├── 会话：src/services/session.ts  静默登录 / 令牌刷新 / 手机号绑定
        └── 降级：src/data/<name>.ts       演示数据（store.dataSource = 'demo'）
```

降级触发条件：未登录 / 该端无登录通道 / 后端 404、5xx / 网络不可达。
后端可访问但该账号无数据时**不降级**，返回真实空集（空态由页面承担）。

## 写链路（提交改造需求）

此前小程序是**纯只读**的：业主看完套餐只能返回，留不下任何线索。现在补上了唯一的写入闭环：

```
首页横幅 / 项目 tab CTA / 套餐详情「预约上门勘测」
  → pages/demand（表单：名称·类型·面积·地址·联系人·手机号·说明）
  → callFunction('submitRenovationDemand')
  → POST /api/projects  → 项目立刻出现在「项目」tab（phase=initiation）
```

三条设计约束：

1. **写操作不降级**。读接口失败可以回落演示数据，但写接口绝不——否则业主会误以为已留资，实际没进派单池。失败会弹窗说明原因。
2. **手机号手填，不依赖微信授权**。未完成微信认证前 `getPhoneNumber` 不可用，手填保证留资通道现在就能跑。
3. **不虚标阶段**。新项目后端落在 `phase=initiation`，列表显示「待勘测」而不是「设计」（适配层 `toProject` 输出 `statusLabel`/`pending`），进度记 0，不做进度虚推。

契约由 `tests/test_mp_demand_submit.py` 锁定：请求体与小程序端逐字段一致，断言 `201`、`phase=initiation`、列表可见、未登录 `401`。

### 线索不能沉底：运营提醒

建单只是把数据写进库。如果运营侧没人知道，页面上的「顾问会与你联系」就是空话（平台此前没有任何外发通道，`/admin` 也没有项目列表）。因此建单后会触发 `app/services/ops_alert_service.py`：

| 配置 | 行为 |
|------|------|
| `OPS_ALERT_WEBHOOK` 已填（企业微信群机器人） | 推送 markdown 消息到运营群，含项目名/类型/面积/地址/联系人/完整手机号/`project_id` |
| 未填 | 写 `WARNING` 日志 `new_demand_pending_ops`（手机号脱敏 `138****8000`），可被日志巡检发现 |
| 通道超时/5xx/errcode≠0 | 只记日志，**建单仍返回 201**（需求已落库，不能因通知失败回滚） |

对应测试：`tests/test_ops_alert.py`（6 例，含「通道炸了也要 201」）。

## 后端接口对照

| 页面能力 | 后端接口 |
|---------|---------|
| 空间资产、就绪度 | `GET /api/space-assets`、`/api/space-assets/summary`、`/api/space-assets/{id}/readiness` |
| 改造项目 | `GET /api/projects`、`/api/projects/{id}` |
| 提交改造需求 | `POST /api/projects`（业主自建，见下「写链路」） |
| 智控设备 | `GET /api/smart-home/schemes/project/{pid}` → `/schemes/{sid}/devices`、`POST /devices/{id}/command` |
| 场景自动化 | `GET /api/scene-automation/scenes/project/{pid}`、`POST /scenes/{id}/execute` |
| 适老套餐 | `GET /api/partial-renovation/quick-install/packages` |
| 补贴预估 | `POST /api/elderly-adaptation/subsidy-precheck`（全国基准档案，确定性单值） |
| AI 管家 | `POST /api/agents/concierge/chat`、`POST /api/ai-qa/search`、`GET /api/ai-qa/faq` |
| 登录 / 手机号 | `POST /api/auth/miniprogram/login`、`POST /api/auth/miniprogram/bind-phone`（本次新增） |
| 埋点 | `POST /api/analytics/collect` |

### 联调实证（2026-10-26）

- `POST /api/auth/miniprogram/login` 用假 code 请求生产，微信返回 `40029 invalid code`：
  说明生产端确实持真实 AppID/AppSecret 调到了 `jscode2session`（若未配置会是 502「未配置 APPID/AppSecret」）。
- `POST /api/auth/miniprogram/bind-phone` 未带令牌返回 401，鉴权链正常。
- 凭证获取走 `cgi-bin/stable_token` 而**不是** `cgi-bin/token`：后端 `--workers 4`，老接口每次刷新会作废其他
  worker 持有的 token（仅 5 分钟共存），会打出 40001 刷新风暴。已有用例 `test_access_token_uses_stable_token_and_caches` 守住。

## 快速开始

```bash
npm install --legacy-peer-deps   # Taro webpack peer 冲突需此参数
npm run dev:weapp                # 微信小程序开发构建
npm run build:weapp              # 微信小程序生产构建（dist/）
npm run dev:h5                   # H5 本地预览（同源 /api，需后端本地在 8000）
npm run typecheck                # 类型检查
```

指定后端地址（默认生产域名）：

```bash
TARO_APP_API_BASE=http://127.0.0.1:8000/api npm run dev:weapp
```

## 上线流程

```bash
# 1. APPID 已写入 project.config.json（wxe8653cb1e81b6dc1），无需再注入；
#    若需切换账号：node scripts/prepare-miniprogram.mjs（读 MINIPROGRAM_APP_ID）

# 2. 本地验收
npm run typecheck && npm run build:weapp
# 微信开发者工具打开本目录（miniprogramRoot=dist/）→ 真机预览
# 注意：本机 NODE_OPTIONS 注入了 fs shim，构建须 env -u NODE_OPTIONS npm run build:weapp

# 3. 上传体验版 / 正式版（需代码上传密钥 + IP 白名单）
MINIPROGRAM_APP_ID=wxe8653cb1e81b6dc1 \
MINIPROGRAM_PRIVATE_KEY_PATH=./.secrets/private.key \
node scripts/upload-miniprogram.mjs --version 1.1.0 --desc "接入生产后端与 AI 管家"
```

### 上线待办（需平台侧配置，代码仓无法代劳）

按依赖顺序，前两步不完成后面都走不通：

1. **微信认证（300 元/次，1–5 工作日）** —— 当前账号 `qualification_verify: false`。
   这是硬阻塞：未认证拿不到「手机号快速验证」权限（`getPhoneNumber` 会静默 `fail no permission`），
   也开不了微信支付。注册时走的是对公打款验证，认证需另外申请。入口：小程序后台 → 微信认证。
2. **ICP 备案** —— 未完成认证时无法进入备案流程；备案是上线前置条件。
3. **服务器域名** —— `request 合法域名` 增加 `https://i-home.life`。
   ⚠️ 该配置**无法通过接口写入**（`wxa/modify_domain` 仅对第三方平台开放，自调用返回 40014），只能后台手工加。
4. **服务类目** —— 现为「工具 / 健康管理」（287/618，注册时选的）。若按「改造交付 + 智能运营」口径运营，
   建议改为生活服务（家政/维修）或房地产（装修）类，类目不符会被审核驳回。
5. **隐私保护指引** —— 须声明 openid、手机号、设备信息、健康数据、对话内容，否则相关接口运行时被拦。
6. **代码上传密钥** —— 后台「开发管理 → 开发设置」生成并下载，放 `miniapp/.secrets/private.key`（已在 .gitignore），
   同时把本机出口 IP 加白名单。
7. **封面素材** —— `src/services/adapters.ts` 中 `COVER_BY_FORMAT` 现为第三方占位图，需替换为自有 CDN（后端 space_assets 暂无封面上传字段）。
8. **订阅消息** —— 施工节点与健康告警推送需在小程序后台申请模板，当前仅站内展示。
9. **运营提醒 webhook** —— 后端 `.env` 填 `OPS_ALERT_WEBHOOK`（企业微信群机器人地址）后重启服务。
   不填也能跑（只写日志），但业主提交的需求**不会主动通知任何人**，需人工巡检日志或定期查库。

## 目录结构

```
src/
├── app.config.ts        # 页面、tabBar（引用 assets/tabbar/*.png）
├── config/env.ts        # API 基址、超时、存储键、演示降级开关
├── pages/               # 11 页：首页/智控/康养/项目/我的 + 4 详情 + 条款 + 提交需求
├── components/          # SectionHeader / StatusTag / ProgressBar / DataSourceBadge
├── services/
│   ├── request.ts       # Taro.request + PASETO + 401 单飞刷新
│   ├── session.ts       # 静默登录 / 会话恢复 / 手机号绑定 / 退出
│   ├── api.ts           # 后端接口封装（字段类型对齐 OpenAPI）
│   ├── adapters.ts      # DTO → 视图模型（枚举翻译、派生口径标注）
│   └── cloud.ts         # 数据层总入口：真实优先 + 演示降级
├── data/                # 演示数据源（降级用，保留 src/data/<name>.ts 约定）
├── store/               # Zustand（用户、当前空间、数据来源、会话态）
├── styles/              # theme.scss / variables.scss（暗金主题、750rpx 基准）
└── types/               # 空间 / 项目 / 设备 / 场景 / 适老 / 健康 / 用户类型
scripts/
├── prepare-miniprogram.mjs   # 注入 APPID、校正工程配置
└── upload-miniprogram.mjs    # miniprogram-ci 上传（体验版/正式版）
```

## 合规口径

- 健康、补贴文案不构成诊疗或资格认定；补贴预估恒带「预估 · 非资格认定」标记；后端给出确定性单值时展示单值，不渲染伪区间。
- 就绪度只统计真实接入数据，未接入维度计 0 分；列表页四维权重与后端 `compute_smart_readiness` 一致（30/25/25/20）。
- 项目进度按后端 `phase` 阶段推断展示（后端未下发完成率），详情页以阶段状态为准。
- 演示数据必须在界面可见标识（`DataSourceBadge`），不得作为生产数据对外展示。
- **真实动作不降级**。设备控制（`controlDevice`）与场景执行（`executeScene`）走 `requireLive()`，
  演示态下按钮直接禁用并提示「演示数据 · 设备未真实接入」，不会出现「已开启」而设备没动的情况。
- **详情页不冒充归属**。带 `id` 打开详情但不存在时明确报「不存在或无权查看」，
  不回落列表第一条（否则多资产业主会看到别人的空间/项目）。
- **内部编码不外露**。`retrofit_package_code`（如 `PKG-ELDERLY-FULL`）只用于反查套餐名，不直接渲染给业主。
- **不承诺无法兑现的服务**。文案不写「1 个工作日内联系」这类无人落地执行的 SLA。
