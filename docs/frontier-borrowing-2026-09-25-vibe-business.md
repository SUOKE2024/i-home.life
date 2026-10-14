# 从 Vibe Coding 到 Vibe Business 的评估与落地（v1.18.0）

> 评估日期：2026-09-25 · 触发：数智前线《万小智，让AI从网站生成走向企业经营》（凤凰网科技转载，2026-09-24）
> **落地状态（2026-09-25）：P0/P1/P2 三项全量落地（v1.18.0）**，第四节列诚实遗留。
> 回归测试：`tests/test_ai_visibility.py` + `tests/test_remediation_plan.py` + `tests/test_content_freshness.py`（66 用例）
> 落地实现：`app/services/ai_visibility_service.py`（P0）·
> `app/services/remediation_plan_service.py` + `app/models/remediation_plan.py`（P1）·
> `app/services/content_freshness_service.py`（P2）· 端点统一挂 `app/api/ai_visibility.py`
> 填写模板：`docs/guides/structured-data-template.md`（业务实体结构化数据，模板含占位符，**不得直接上线**）
> 原文出处：https://tech.ifeng.com/c/8wemV6sPHYT （2026-09-24 15:20 发布）

---

## 一、原文事实与核心观点（核验，非解读）

### 1.1 原文事实

| 事实 | 原文依据 |
|------|---------|
| 生成式 AI 用户规模 | CNNIC 第 57 次报告：截至 2025-12 我国生成式 AI 用户 **6.02 亿**（一年前 2.49 亿） |
| 品牌被提及度与 AI 可见度 | Ahrefs 对 **7.5 万个品牌**研究的结论：相关性约为**外链的 3 倍** |
| 存量站点的经营常态 | 万小智（阿里云 AI 建站与经营平台）：**已上线网站数量无明显增长，页面数量增长较快** |
| 用户构成 | 万小智累计服务用户 **36 万，企业用户占 73%** |
| 产品演进 | 万小智 3.0 在云栖大会发布，主张**从 Vibe Coding 走向 Vibe Business**；2.0 解决「建站到上线（域名/解析/备案）」，3.0 承接**上线之后的获客、内容、客服与经营分析** |

客户访谈中的真实痛点（原文引用）：
- 「最大的问题是流量」（锐扬科技 CEO 杨扬，问题出现在**上线后**）
- 「一忙起来内容就有点顾不上，网站很容易长草」（煊远致和新能源运营总监何娇娇）
- 「AI 为什么没有提到我们？」（阿里云中小企业应用运营总监孙晓杰转述客户咨询的变化：从问排名转向问 AI 是否知道自己）

### 1.2 四条可工程化的主张

1. **生成不是终点**：一句话建站的演示在生成时结束，企业困扰在上线后开始；「网站生成完成不是 AI 工作的终点，正在成为企业经营的起点」。
2. **分发入口迁移到 AI**：官网从「给人看的名片」变成「**同时给搜索引擎、AI 和客户看的企业说明书**」；被 AI 获取与理解需要信息**可抓取、有据可查、持续更新**（GEO 语境）。
3. **「诊断 ≠ 解决」**：一份几十项的 GEO/SEO 报告，经营者看不懂、也推不动修改；万小智 3.0 的做法是**诊断 → 修改清单 → 用户确认 → 执行 → 发布 → 复检**，且把诊断能力开放给存量第三方站点（只诊断不改）。
4. **自动化边界按「能否回滚」判据**：高频、重复、规则明确的任务交给 AI；涉及**企业事实、品牌承诺、发布权限、经营决策**的留在人手里。原文判据是「**不只看它能不能做，还要看做错以后用户能不能发现、能不能改回来**」；改动只碰「说明书」层面（结构/样式/链接），不动「承重墙」，逐条确认 + 版本留存 + 一键回滚。「绕过别人的系统去改文件，叫风险，不叫能力」。

### 1.3 与项目的定位同构关系

项目对外定位「空间健康资产运营商 —— 一次改造交付，**长期健康运营**」，装修全链路（设计→算量→报价→采购→施工→质检→结算）是**交付底座**（相当于原文的 Vibe Coding 段）。原文主张的「生成之后才是经营」与本项目「交付之后才是运营」是同一判断的两个行业版本。**差距不在定位，而在「对外可见度」这一维从未被度量过**。

---

## 二、本项目实测缺口（2026-09-25，由 P0 审计实测得出）

首次运行 `run_ai_visibility_audit()` 得 **70/100（部分就绪）**，四维得分：可抓取 30/30、可理解 25/25、**可引用 9.5/25**、**新鲜度 6/20**。

| 缺口 | 实测证据 | 对应原文判断 |
|------|---------|-------------|
| 结构化数据缺**业务实体** | `index.html` 仅有 `WebSite` + `Organization` + `ImageObject`，无 `Service`/`Product`/`Offer`/`FAQPage` —— AI 能知道「是谁」，回答不了「能提供什么」 | 「官网是同时给搜索引擎、AI 和客户看的企业说明书」 |
| 组织实体缺交叉佐证字段 | Organization 有 name/url/logo，缺 `sameAs` / `contactPoint` / `address` | 「AI 交叉校验依赖第三方佐证」（Ahrefs：提及度相关性 ≈ 外链 3 倍） |
| **无公开内容页** | `webapp/dist` 下非外壳静态 HTML = **0**（仅 index.html 与 console/index.html），站点是纯应用外壳，抓取方读不到服务说明与案例 | 「静态的网站无法制造全网提及」 |
| **内容长草** | `sitemap.xml` 的 9 条 URL `lastmod` 全部冻结在 **2026-08-08**（实测 48.3 天未更新） | 「一忙起来内容就有点顾不上，网站很容易长草」 |
| 无 `llms.txt` | 全仓库不存在该文件（含 webapp/public、webapp/dist） | AI 友好的站点摘要缺失 |
| AI 爬虫策略不完整 | robots.txt 仅显式声明 `GPTBot` / `CCBot`（且仅 `Disallow: /api/`），未声明 ClaudeBot / PerplexityBot / Google-Extended / Applebot-Extended / Bytespider / meta-externalagent | 「企业资料能否被获取、核验和准确理解」 |

`/projects`、`/budget`、`/quality` 等 sitemap URL 是登录后才渲染的路由 —— 抓取方拿到的是空壳，属于上表「无公开内容页」的同一根因。

---

## 三、落地三项（三个独立 flag，默认 True，关闭即 503 诚实降级）

> **v1.18.0 落地后自查修复两处**（由「填写业务实体模板」需求触发，实测暴露）：
> 1. **产物跨目录混合**（严重）：`resolve_artifacts` 原按「逐个文件跨候选目录回退」定位，会读出 `robots.txt` 取自 `webapp/dist`、`llms.txt` 取自 `webapp/public` 的**混合产物集**，结论不可信。已改为**先定目录、再在该目录内取全部产物**；`index.html` 回退 `webapp/index.html` 仅当 `public_dir` 就是源码态 `webapp/public`（按目录身份判定，与是否显式传参无关 → 同一 `static_root` 读取结果恒一致，复检可比）。
> 2. **`@graph` 容器下的 Organization 未被识别**：原实现只在**顶层**找 `@type`，导致标准 `@graph` 写法（含 `@id` 互相引用）被误报「未找到 Organization 实体」。已改为递归收集（覆盖 `@graph` / `publisher` / 任意嵌套 / `@type` 数组），并按**字段完整度择优**，使 `@graph` 写法与扁平写法等价。
>
> 相应新增 6 条回归用例（`tests/test_ai_visibility.py`）。**两处均影响审计结论可信度**，属必修项。

### 3.1 P0 站点 AI 可见度就绪度审计（`ai_visibility_audit_enabled`）

`GET /api/ai-visibility`（平台管理员）。四维加权 100 分：**可抓取 30 / 可理解 25 / 可引用 25 / 新鲜度 20**，16 个检查项，每项输出 `status`（pass/warn/fail/unknown）+ **实测证据** + 维度归属。

- 解析器为纯函数：`parse_robots`（RFC 9309 分组语义：连续多个 `User-agent` 行共享同一套规则）、`parse_sitemap`、`parse_jsonld`（含解析失败诚实报错，不静默当空）、`_age_days`。
- 产物定位：**先定目录、再在该目录内取全部产物**（构建产物优先 `webapp/dist` → 回退 `webapp/public`）；显式传 `static_root` 时只在该目录内定位，保证「审计 → 复检」可比。
- **诚实红线（三重）**：`model_probing=False` —— **不调用任何 AI 平台**；disclaimer 恒带「不构成任何 AI 引用、收录或排名承诺」；`limitations` 明列 5 条（不做真实模型探测 / 分数与平台算法无关 / llms.txt 为业界先行约定无正式标准 / sitemap lastmod 为站点自报时间 / 内容页按静态 HTML 计数不覆盖 SSR 页面）。
- 前置产物缺失 → 该项记 `unknown` **计 0 分**并标注，不猜为通过。

### 3.2 P1 修复清单闭环（`remediation_plan_enabled`）

承接原文最强调的断点「诊断完成，并不意味着问题得到解决」：

| 端点 | 作用 |
|------|------|
| `POST /api/remediation-plans` | 按当前审计生成清单并落库（`remediation_plans` 表，迁移 `m7a8b9c0d1e2`），**不执行任何改动** |
| `GET /api/remediation-plans` / `{id}` | 清单列表 / 详情（含 tier、rationale、evidence） |
| `POST /{id}/apply` | 执行白名单条目，**须显式 `confirm=True`**（否则 422） |
| `POST /{id}/verify` | 复检：重新跑审计逐条比对源检查项是否转 `pass`（默认只复检**已执行**条目） |
| `POST /{id}/rollback` | 按执行前**文件全文备份**还原（新增文件回滚即删除） |

**三级自动化边界**（`classify_tier`，确定性规则，无 LLM）：

| tier | 判据 | 示例条目 |
|------|------|---------|
| `auto` | 白名单动作 + 可逆 + 不改企业事实 | 生成 `llms.txt`、追加 robots.txt AI 爬虫声明块 |
| `confirm` | 可逆但不涉事实的站点配置改动，须逐条人工确认 | 刷新 sitemap `lastmod`、补 `<html lang>` |
| `human_only` | 涉及**企业事实 / 品牌承诺 / 发布权限 / 经营决策**，平台只出清单不代做 | 业务实体结构化数据、内容页、案例与联系方式 |

- **只碰「说明书层」**：白名单只有 `write_llms_txt`（新增文件，内容由站点**既有公开元数据**确定性生成，**无时间戳**故重复执行不产生差异）与 `update_robots_ai_agents`（**追加**声明块，既有规则逐字保留）；应用代码与后端不在写入范围。
- **越界写拒绝**：`_safe_target` 限定写入根为仓库内 `webapp/`，`static_root` 等用户可控输入无法把写入引到仓库外（测试覆盖）。
- `llms.txt` 内容不含任何新增业务声明，末尾恒标注「生成器：`app/services/remediation_plan_service.py`」。

### 3.3 P2 公开内容新鲜度（「长草」）监测（`content_freshness_monitor_enabled`）

`GET /api/content-freshness`（平台管理员）。按 `updated_at` + **半衰期口径复用 `memory_decay_half_life_days`**（默认 30 天，不另造一套）做确定性指数衰减 `freshness = 0.5 ** (年龄/半衰期)`；状态阈值：`fresh ≥ 0.5` / `aging ≥ 0.25` / `stale < 0.25`。

- 监测对象：项目（案例/交付记录）、空间资产台账（运营状态）、**已发布**产品/服务（`status='published'`，草稿与归档不计入对外内容）。
- 输出每类计数、最旧条目、待更新清单（含 `priority` high/medium）与建议；**只出清单不代写**（对外表述更新属 human_only 纪律）。
- 诚实红线：陈旧度是**代理指标**（平台无对外内容发布记录表），不声称某条内容「已发布/已下线」；无数据的类型记 `insufficient_data` 并标注「不据此判为内容不合格」，**不返回 0 伪装全部新鲜**。

---

## 四、诚实遗留（不声称已具备）

- **G1 真实 AI 可见度探测**：本版本不做任何模型探测（原文的「AI 为什么没有提到我们」需第三方工具或平台 API 才能回答），因此无法证明站点是否已被引用；P0 只回答「是否具备被获取/理解/引用的**条件**」。
- **G2 公开内容生产**：`public_content_pages = 0`（无服务说明页/案例页/FAQ）是当前最大可引用缺口，但内容承载企业事实与品牌承诺，**平台不代写**（human_only）；需业务侧产出后由 P0 复测。
- **G3 组织实体的第三方佐证**：`sameAs`（工商/资质/媒体主页）需要真实外部账号与资质信息，属人工核实后写入，本版本只标注缺失。
- **G4 存量第三方站点经营**：原文万小智对第三方站点「只诊断不改」；本项目当前只有自有站点（`webapp/`），无第三方站点写入路径，故未实现该能力（预留 `ALLOWED_WRITE_ROOTS` 单源，未来接入须先立**授权**语义）。
- **G5 内容更新自动化**：P2 只提示不生产（同 G2 纪律）；原文的「基于企业档案自动成文」涉及事实编造风险，本项目不采纳自动成文，只在 `content_publisher` 既有能力内 best-effort。
- **G6 GEO 效果度量**：原文引用的 Ahrefs「提及度 ≈ 外链 3 倍」是第三方研究结论，本项目**未接入任何 AI 可见度监测工具**，不据此做效果承诺。

---

## 五、工程纪律（改本模块须遵守）

1. `AUTO_REMEDIATION_ACTIONS` 是**唯一**白名单；新增自动动作必须同时满足「可逆 + 不改企业事实 + 执行后可确定性复检」三条，并在 `CHECKS[].remediation.rationale` 写明理由。
2. `_safe_target` 的写入根不可放宽到仓库外；`allowed_root` 仅服务层内部/测试可传，**HTTP 层永不传**。
3. 审计的 `model_probing=False` 与 disclaimer 属诚实红线，不得移除；新增检查项须挂实测 `evidence`，禁止写推测性结论。
4. `remediation_plans.status` 五值单源在 `app/models/remediation_plan.py` `REMEDIATION_PLAN_STATUSES`，与 CheckConstraint、迁移三处逐字一致（改一处须同步其余两处）。
5. 版本号/基线同步见 `.claude/templates/version-bump.md`；新增测试后须 `python scripts/check_test_baseline.py --update` 校准。
