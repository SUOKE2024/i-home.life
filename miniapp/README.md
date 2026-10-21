# 索克家居微信小程序（miniapp）

> 索克家居 · 空间健康资产运营商 —— 面向存量空间的「改造交付 + 智能运营」业主端小程序。
> 技术栈 Taro 4.3.0（React 18 + TypeScript），与索克生活 / 索克俱乐部小程序同一 Taro 基线。

## 当前状态（2026-10-21）

| 维度 | 状态 |
|------|------|
| Taro 版本 | 4.3.0（与生活 / 俱乐部统一） |
| 页面 | 9 页全部为实体页，无占位页 |
| 构建 | `npm run build:weapp` 通过，产物 `dist/` |
| 类型检查 | `npm run typecheck` 通过 |
| 数据源 | **全部为本地演示数据**（`src/services/cloud.ts` → `src/data/*.ts`），尚未接入生产后端 |
| AI 管家 | 本地示例问答，页面常驻「演示模式、未接入真实 AI 服务」提示 |
| tabBar 图标 | `*.png`（81×81，透明底）为微信实际渲染文件，`*.svg` 保留为规范源 |

> 诚实边界：本仓当前不发起任何真实网络请求，不构成支付、补贴资格、诊疗或交付承诺。
> 接入真实后端前，不得把演示数据当生产数据对外展示。

## 快速开始

```bash
npm install --legacy-peer-deps   # Taro webpack peer 冲突需此参数
npm run dev:weapp                # 微信小程序开发构建
npm run build:weapp              # 微信小程序生产构建（dist/）
npm run dev:h5                   # H5 本地预览
npm run typecheck                # 类型检查
```

其他平台脚本（`build:alipay` / `build:tt`）保留 Taro 平台插件，但**未接线**：
仓库无对应 `project.alipay.json` / 抖音 appid，提审前需补齐平台工程配置。

## 目录结构

```
src/
├── app.config.ts        # 页面、tabBar（引用 assets/tabbar/*.png）
├── app.tsx              # 入口，启动预热本地数据源
├── pages/               # 9 个页面：首页 / 智控 / 康养 / 项目 / 我的 + 4 个详情页
├── components/          # SectionHeader / StatusTag / ProgressBar
├── data/                # 本地演示数据源（getProjects / getSpaces / estimateSubsidy 等）
├── services/cloud.ts    # 数据层统一入口：按调用名加载 src/data/<name>.ts
├── store/               # Zustand（用户、当前空间）
├── styles/              # theme.scss / variables.scss（暗金主题、750rpx 基准）
└── types/               # 空间 / 项目 / 设备 / 场景 / 适老 / 用户类型
```

## 页面清单

| 页面 | 说明 |
|------|------|
| `pages/index` | 首页：空间健康概览、快捷服务、告警、进行中项目 |
| `pages/smart` | 智控：设备状态与场景执行 |
| `pages/care` | 康养：适老套餐目录与补贴预估（非资格认定） |
| `pages/project` | 项目：六阶段改造进度 |
| `pages/mine` | 我的：用户档案与服务入口 |
| `pages/space-detail` | 空间详情：四维智能就绪度、资产信息、进入智控 |
| `pages/project-detail` | 项目详情：六阶段进度、施工方、预算、下一节点 |
| `pages/elderly-detail` | 套餐详情：价格、适老维度、补贴预估与免责口径 |
| `pages/ai-consult` | AI 管家：本地示例问答（明确标注演示模式） |

## 合规口径

- 健康、补贴相关文案不构成诊疗或资格认定；补贴预估恒带「预估 · 非资格认定」标记。
- 就绪度只统计真实接入数据，未接入维度计 0 分，不做虚增。
