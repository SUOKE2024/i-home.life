# 业务实体结构化数据（JSON-LD）填写模板

> 适用版本：v1.18.0 起 · 对应检查项 `structured_data_business_entity` + `organization_profile_fields`
> 审计端点：`GET /api/ai-visibility`（或本地 `run_ai_visibility_audit()`）
> 背景：`docs/frontier-borrowing-2026-09-25-vibe-business.md` 第二节实测缺口——
> 站点 `index.html` 仅有 `WebSite` + `Organization`，**AI 能知道「是谁」，回答不了「能提供什么」**。

---

## 一、放置位置

粘贴进 [`webapp/index.html`](../../webapp/index.html) 的 `<head>` 内，**与既有 `WebSite + Organization` 块并列**（新增第二个 `<script type="application/ld+json">`，不要覆盖既有块）。

> **本文件是模板，不是内容。** 直接把带占位符的 JSON 上线，会让审计把该项判为 `pass` 而**掩盖真实缺口**——必须填完真实值与经营方确认后再粘贴。

## 二、模板（填完再粘贴）

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://i-home.life/#organization",
      "name": "【填写：工商登记全称】",
      "alternateName": "索克家居 · i-home.life",
      "url": "https://i-home.life/",
      "logo": {
        "@type": "ImageObject",
        "url": "https://i-home.life/logo.png",
        "width": 512,
        "height": 512
      },
      "description": "【填写：一句话业务定位，禁疗效词，见第四节】",
      "address": {
        "@type": "PostalAddress",
        "addressCountry": "CN",
        "addressRegion": "云南省",
        "addressLocality": "【填写：市】",
        "streetAddress": "【填写：工商登记详细地址】"
      },
      "contactPoint": [
        {
          "@type": "ContactPoint",
          "contactType": "customer service",
          "telephone": "【填写：对外客服电话】",
          "email": "【填写：对外联系邮箱】",
          "availableLanguage": ["zh-CN"]
        }
      ],
      "sameAs": [
        "【填写：已认证的官方账号/权威页面 URL，一条一项，没有就整段删除】"
      ],
      "areaServed": {
        "@type": "State",
        "name": "云南省"
      }
    },
    {
      "@type": "Service",
      "@id": "https://i-home.life/#service-renovation",
      "name": "【填写：服务名称，如「空间智能化改造交付」】",
      "serviceType": "【填写：服务类别】",
      "provider": { "@id": "https://i-home.life/#organization" },
      "areaServed": { "@type": "State", "name": "云南省" },
      "description": "【填写：服务说明，须为可核验事实，禁疗效词与承诺性表述】",
      "hasOfferCatalog": {
        "@type": "OfferCatalog",
        "name": "【填写：产品目录名称】",
        "itemListElement": [
          {
            "@type": "Offer",
            "itemOffered": {
              "@type": "Service",
              "name": "【填写：套餐/服务名，如「48 小时厨房焕新」】",
              "description": "【填写：交付内容与工期，须与平台套餐定义一致】"
            },
            "price": "【填写：一口价金额，仅公开定价的套餐才填】",
            "priceCurrency": "CNY",
            "url": "https://i-home.life/【填写：对应页面路径】",
            "availability": "https://schema.org/InStock"
          }
        ]
      }
    },
    {
      "@type": "FAQPage",
      "@id": "https://i-home.life/#faq",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "【填写：客户真实高频问题，如「改造需要搬离居住吗」】",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "【填写：真实答案。无确定答案的问题不要写，宁可少列】"
          }
        }
      ]
    }
  ]
}
```

`@graph` 用 `@id` 互相引用（`provider: {"@id": "#organization"}`），避免在每个节点重复粘贴组织信息。

## 三、字段填写指引

### 3.1 Organization（决定 `organization_profile_fields` 检查结果）

| 字段 | 必填 | 判断口径 | 取值来源 |
|------|------|---------|---------|
| `name` | 是 | 基础字段，缺则该项 fail | 工商登记全称（**用法定全称，不要用品牌简称**） |
| `url` / `logo` | 是 | 同上 | 已上线真实地址与可访问图片（`https://i-home.life/logo.png` 已验证存在） |
| `description` | 否 | 不参与评分 | 一句话定位；若涉康养/疗愈/适老，须带「非医疗诊断」口径（第四节） |
| `address` | **建议填** | 缺则该项停在 warn | 工商登记地址（真实性由经营方保证） |
| `contactPoint` | **建议填** | 缺则停在 warn | 对外客服电话/邮箱 |
| `sameAs` | **建议填** | 缺则停在 warn | 已认证的企业账号、政务/资质公示页、媒体报道页 |
| `areaServed` | 否 | 不参与评分 | 与业务实际服务范围一致 |

> 此项完整（基础 + `sameAs`/`contactPoint`/`address` 齐全）才由 `warn` 转 `pass`（+5 分）。
> `sameAs` 是 AI **交叉校验**的锚点：Ahrefs 对 7.5 万品牌的研究显示品牌全网被提及度与 AI 可见度相关性约为外链的 3 倍——只在这一处写「我们是谁」，AI 无法交叉印证。

### 3.2 Service / Offer（决定 `structured_data_business_entity`）

平台**已有**的可公开服务口径（填写时请对齐，勿另造）：

| 服务线 | 代码单源 | 说明 |
|--------|---------|------|
| 存量空间 AI 智能化改造 | `app/models/space_asset.py` `BUSINESS_FORMATS` | 药膳小院 / 森林药浴 / 康养研学 / 节气旅居（**前四项**与索克生活 lodge 业态单源对齐）+ 疗愈度假 / 文旅点位 / 适老住宅 / other |
| 局部焕新一口价套餐 | `partial_renovation_service.QUICK_INSTALL_PACKAGES` | PKG-48H-KITCHEN / PKG-48H-BATHROOM / PKG-7D-WALL |
| 适老改造套餐 | 同上 | PKG-ELDERLY-BATH / PKG-ELDERLY-ROOM / PKG-ELDERLY-FULL（`elderly_theme=true`） |
| 智能家居集成与场景自动化 | `app/api/smart_home.py` / `app/api/scene_automation.py` | 生态桥真机接入程度以 `/api/ecosystem/status` 的 `implemented` 标记为准 |
| 长期运营（台账/能耗/主动简报） | `space_asset_service` / `app/api/energy.py` / `app/agents/orchestrator.py` | 资产状态机 + 就绪度评分 + 能耗监测 + 周期性简报 |

**价格（`Offer.price`）**：只能填**已对外定价**的一口价套餐。合同价、按方案报价、成本区间**一律不得写入**——写错价格是可被公开引用的错误事实。

### 3.3 FAQ（可选，但 GEO 收益最高）

只写**有确定答案**的问题（工期、是否需搬离、交付范围、是否需要现场条件）。没有把握的问题宁可少列：AI 引用的是一段被当作事实的文字，写错比不写代价大。

## 四、诚实红线（违反即不得上线）

1. **健康声明合规**：涉康养/疗愈/适老的服务说明与 FAQ **禁用疗效词**（治疗/治愈/根治/消炎/抗癌/降压/降糖/降血脂/控糖/减肥/排毒/疗效/处方/有效率 等，词表见 `app/services/health_claim_compliance.py` `PROHIBITED_CLAIM_WORDS`）。
   - **`CAUTION_CLAIM_WORDS` 为另一档**：养生/调理/助眠/改善睡眠/增强免疫/缓解疲劳 等属「保健调理语义」，**放行但必须附加免责声明**——写进结构化数据时同样要带，否则被认为是对外承诺。
   - 所有健康相关输出必须携带「非医疗诊断」口径（`STANDARD_HEALTH_DISCLAIMER`：不构成医疗诊断或治疗建议，不替代执业医师面诊）。平台不做医疗诊断/处方/疗效承诺。
2. **不得宣称补贴结论**：适老相关表述不得出现「已获补贴 / 已通过核定」，补贴口径恒为「预估 · 非资格认定」（`elderly_subsidy_service`）。
3. **轻资产红线**：不得用任何表述暗示平台**持有或运营不动产**。Service 描述用「改造交付 + 智能运营服务」口径，不得写「我们运营某康养基地」。
4. **不得编造事实**：案例、资质、合作品牌、数据、客户评价、奖项——**没有可核验来源就不写**。`sameAs` 只填真实存在且属于本主体的页面。
5. **`maturity_level` 纪律同理**：不得在结构化数据里声明未评定的等级/认证（如「国标 X 级」）。

## 五、填写后验证

粘贴后复跑审计，确认两项转 pass：

```bash
# 本地（无需启动服务）
.venv/bin/python -c "
from app.services.ai_visibility_service import run_ai_visibility_audit
r = run_ai_visibility_audit()
print('score', r['score'], r['level_name'])
for c in r['checks']:
    if c['id'] in ('structured_data_business_entity', 'organization_profile_fields'):
        print(c['status'], c['id'], c['evidence'])
"
# 生产：GET /api/ai-visibility（平台管理员）
```

预期：`structured_data_business_entity` → `pass`（+8 分）；`organization_profile_fields` → `pass`（+5 分）；
`remediation_candidates` 相应减少两条。填完仍未 pass 说明字段名/嵌套写错（见下表）。

## 六、常见错误

| 现象 | 原因 |
|------|------|
| `structured_data_present` 仍 pass 但 `structured_data_business_entity` fail | 新块 JSON 语法错误（审计会报 `JSON-LD 解析失败`，不会静默） |
| `organization_profile_fields` 停在 warn | `sameAs`/`contactPoint`/`address` 三项未齐 |
| `Organization` 未识别 | 只写 `WebSite` 内嵌 `publisher` 且 `publisher` 缺字段；用 `@graph` 独立 `Organization` 节点最稳 |
| 分数上涨但审计仍报缺业务实体 | 把 `Service` 写成了 `WebSite` 的子字段（未被 `@type` 扫描识别为独立业务实体） |

> 提醒：结构化数据只解决「AI 能读懂站点说什么」，**不承诺被引用**（审计 `model_probing=False`，不调用任何 AI 平台）。真正影响引用的是持续更新——见 `GET /api/content-freshness` 的「长草」清单。
