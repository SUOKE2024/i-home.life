# Schema Compare Workflow 故障排查（2026-08-06）

> 适用：[.github/workflows/schema-compare.yml](file:///Users/netsong/Developer/i-home.life/.github/workflows/schema-compare.yml)
> 触发方式：每天 02:00 UTC（nightly cron）+ 手动 `workflow_dispatch`
> 功能：`compare_db_schema.py` 对比生产库（`PROD_DATABASE_URL`）与 CI 空库迁移基线（SQLite `alembic upgrade head`），有差异即 job 失败 + 上传 `schema-diff` artifact。

## 一、典型报错："PROD_DATABASE_URL secret 未配置"

workflow 在 `校验生产库 secret 已配置` 步骤会输出：

```
::error::PROD_DATABASE_URL secret 未配置，无法对比生产库。请在 Settings → Secrets 添加只读连接串。
```

### 排查步骤（按序）

1. **确认 secret 是否存在**
   GitHub 仓库 → `Settings` → `Secrets and variables` → `Actions` → 查看 `Repository secrets` 是否有 `PROD_DATABASE_URL`。
   - 无 → 执行配置（见下节"配置步骤"）
2. **确认 secret 作用域**：必须配在**仓库级** Secrets（不是 Environments / Dependabot）。job 无 `environment:` 声明，环境级 secret 不可见。
3. **确认分支**：workflow 文件（`schema-compare.yml`）与 secret 引用均基于**默认分支（main）**。若文件只在未合入的 PR 分支，Actions 不会出现该 workflow。已确认本仓库 `827b180` 已合入 main。
4. **确认 secret 对 pull_request 之外的触发可见**：`schedule`/`workflow_dispatch` 均可读仓库 secret（PR 才有限制，本 workflow 无 PR 触发）。
5. **重试触发**：secret 配置后，`workflow_dispatch` 无需重 push 即可生效（`schedule` 需等下次 cron 或手动触发一次）。

### 配置步骤

```
Settings → Secrets and variables → Actions → New repository secret
  Name:  PROD_DATABASE_URL
  Value: postgresql+asyncpg://readonly_user:password@host:5432/ihome_db
```

- **建议只读账号**（`GRANT CONNECT, SELECT` 即可），避免生产写权限暴露给 CI。
- URL 格式：脚本自动 strip `+asyncpg`/`+aiosqlite` 前缀，两种写法均可：
  - `postgresql+asyncpg://...`（运行时异步驱动）
  - `postgresql://...`（脚本用 psycopg2 同步连接）
- 若生产库有公网限制：需将 GitHub Runner IP 段（`https://api.github.com/meta`）加入白名单。

## 二、配置后仍报错

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| `sqlalchemy.exc.OperationalError: could not connect to server` | 网络不通 / 账号权限 / 密码含特殊字符未 URL 编码 | Runner IP 白名单；密码特殊字符用 `%XX` 编码 |
| `connection refused (port 5432)` | 生产库未对外开放 / 走内网 | 临时放开白名单或改用内网跳板（参考部署架构，阿里云 RDS 白名单加 Runner IP） |
| `ModuleNotFoundError: psycopg2` | 依赖未装 | requirements.txt 已含 `psycopg2-binary`，确认 `pip install -r requirements.txt` 执行 |
| 有差异但不确定是否重要 | 差异即失败是**设计行为** | 对照 [schema-cleanup-20260806.md](file:///Users/netsong/Developer/i-home.life/docs/reports/schema-cleanup-20260806.md) 判断 A/B/C 类，见下方"差异解读" |

## 三、手动触发步骤（workflow_dispatch）

1. GitHub 仓库 → `Actions` → 左侧 `Schema Compare (Prod vs Empty)`
2. `Run workflow` → 分支选 `main` → 绿色确认
3. 运行约 1-2 分钟（含空库迁移 + 对比）
4. 查看结果：
   - `对比生产库 vs 空库` 步骤日志 = 差异明细
   - 页面底部 `Artifacts` → `schema-diff` = 日志文件（保留 14 天）
   - Job 失败 = 有差异（`⚠️ 发现 N 类差异`）；Job 绿 = `✅ 两库表结构完全一致`

## 四、差异解读速查

| compare 输出 | 含义 | 建议 |
|--------------|------|------|
| `🔴 仅 A 有，B 无` | 生产有、空库迁移基线无 → 缺建表迁移或残留表 | 有 model → 补迁移；无 model（如 assets_3d）→ 可 DROP |
| `🔴 列差异` | 同表列不一致 | 残留列可忽略；model 有而库缺 → 补迁移 |
| `🟡 索引差异` | 索引集合/unique 不一致 | 见清理文档 A/B/C 分类，P0 为 unique 缺失 |

## 五、邮件报告说明

- **内建机制（零配置）**：job 失败时 GitHub 自动向仓库通知邮箱（Owner/Watchers）发送失败邮件，含 job 名与日志链接。
- **可选增强（SMTP）**：如需把**完整对比报告**邮件化（含成功时的差异明细），需额外配置 SMTP secret（`SMTP_SERVER`/`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_FROM`）并启用 `dawidd6/action-send-mail`，未配置前保持内建失败通知即可。
