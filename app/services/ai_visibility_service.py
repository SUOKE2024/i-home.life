"""站点 AI 可见度（GEO）就绪度审计（v1.18.0）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
「AI 让网站生成变得非常容易，但围绕企业自有阵地的长期经营仍缺解法」「官网正在
从一张给人看的名片，变成一份同时给搜索引擎、AI 和客户看的企业说明书」。
本模块把这套判断落到**平台自身对外阵地**（webapp 静态产物）的可核验检查上。

方法（确定性，零 LLM / 零外部网络）：
四维加权评分 —— 可抓取 30 / 可理解 25 / 可引用 25 / 新鲜度 20，共 100 分。
所有结论均由静态产物（robots.txt / sitemap.xml / index.html / llms.txt）确定性
解析得出，每项附 `evidence` 实测值，不做推断。

诚实红线（与 CLAUDE.md「诚实降级」一致，不可绕过）：
- **不做真实模型探测**：不调用 ChatGPT / Claude / Perplexity 等任何平台，不声称
  已出现在任何 AI 回答中；本审计只回答「站点是否具备被 AI 抓取/理解/引用的**条件**」。
- **不承诺效果**：AI 引用/排名由第三方平台算法决定，本审计不构成任何效果承诺。
- `llms.txt` 为业界**先行的非标准约定**（无 IETF/W3C 标准），缺失只计入就绪度，
  不宣称为标准合规要求。
- sitemap 的 `lastmod` 是**站点自报时间**，不等于平台实测抓取时间。
- 前置产物缺失时该项记 `unknown`（计 0 分）并标注，不猜为通过。
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# app/services/xxx.py → parents[2] = 仓库根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = "app/services/ai_visibility_service.py"

DISCLAIMER = (
    "本审计为站点静态产物的确定性检查（平台自检），**不构成任何 AI 引用、收录或排名承诺**；"
    "未调用任何 AI 平台做真实可见度探测。"
)

METHOD = "static_artifact_deterministic_audit"

# ── 四维权重（合计 100）──

DIMENSIONS: list[dict] = [
    {"key": "crawler_access", "name": "可抓取", "weight": 30,
     "desc": "AI 爬虫能否访问站点公开内容（robots.txt 策略 + sitemap 可发现）"},
    {"key": "machine_readable", "name": "可理解", "weight": 25,
     "desc": "页面是否有机器可读的标题、摘要、语言与结构化数据"},
    {"key": "citable", "name": "可引用", "weight": 25,
     "desc": "是否有可被引用的事实（业务实体结构化数据、内容页、时间戳完整性）"},
    {"key": "freshness", "name": "新鲜度", "weight": 20,
     "desc": "内容是否在更新（sitemap 自报时间 + AI 友好摘要文件）"},
]

# ── AI 爬虫声明对照表（业界通行 UA 名，非标准清单）──
# 用途：检查 robots.txt 是否显式声明 AI 检索类爬虫的访问策略。
# 说明：robots.txt 为约定格式（RFC 9309），AI 爬虫 UA 名由各厂商公布，可能变化。
AI_CRAWLERS: tuple[str, ...] = (
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",
    "ClaudeBot", "Claude-User", "Claude-SearchBot",
    "PerplexityBot", "Perplexity-User",
    "Google-Extended", "Applebot-Extended",
    "Bytespider", "CCBot", "meta-externalagent",
)

# 可引用的业务实体类型（仅有 WebSite/Organization 只说明「是谁」，不足以回答「能提供什么」）
BUSINESS_ENTITY_TYPES: tuple[str, ...] = (
    "Service", "Product", "Offer", "FAQPage", "Question", "Article", "CaseStudy", "LocalBusiness",
)

# 内容页判定：非应用外壳的静态 HTML（排除 Vite 产物入口与控制台 SPA 入口）
_CONTENT_PAGE_EXCLUDE = {"index.html"}
_CONTENT_PAGE_EXCLUDE_DIRS = {"console", "assets"}


def _now() -> datetime:
    return datetime.now(timezone(timedelta(hours=8), name="Asia/Shanghai"))


def _now_iso() -> str:
    return _now().isoformat()


# ════════════════════════════════════════════════════════════════
# 产物定位
# ════════════════════════════════════════════════════════════════


def _first_existing(rel_paths: list[str]) -> Path | None:
    for rel in rel_paths:
        p = PROJECT_ROOT / rel
        if p.exists():
            return p
    return None


def _rel(path: Path) -> str:
    """相对仓库根的展示路径（仓库外路径回退绝对路径，供显式 static_root 场景）。"""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def resolve_artifacts(static_root: str | None = None) -> dict:
    """定位站点静态产物。

    **先定目录，再在同一个目录内取全部产物** —— 不逐个文件跨目录回退，否则会读到
    「robots 取自 dist、llms.txt 取自 public」这类混合产物集，使审计结论不可信
    （v1.18.0 修复）。

    - 未指定 `static_root`：构建产物优先 `webapp/dist` → 回退 `webapp/public`。
    - `index.html` 回退 `webapp/index.html`：**仅当 `public_dir` 就是源码态
      `webapp/public`**（源码态入口在 webapp/ 根而非 public/ 内）。按目录身份判定，
      与是否显式传参无关，故同一 `static_root` 的读取结果恒一致（复检可比）。
    - 指定 `static_root`：**只在该目录内定位**（复检复用清单记录的目录，保证可比）。
    """
    if static_root:
        public_dir = _first_existing([static_root])
    else:
        public_dir = _first_existing(["webapp/dist", "webapp/public"])

    def _in_dir(*names: str) -> Path | None:
        if public_dir is None:
            return None
        for name in names:
            candidate = public_dir / name
            if candidate.exists():
                return candidate
        return None

    index_html = _in_dir("index.html")
    if index_html is None and public_dir == PROJECT_ROOT / "webapp" / "public":
        index_html = _first_existing(["webapp/index.html"])

    return {
        "public_dir": public_dir,
        "public_dir_rel": _rel(public_dir) if public_dir else None,
        "index_html": index_html,
        "robots": _in_dir("robots.txt"),
        "sitemap": _in_dir("sitemap.xml"),
        "llms": _in_dir("llms.txt"),
    }


# ════════════════════════════════════════════════════════════════
# 解析器（全部为纯函数，便于单测）
# ════════════════════════════════════════════════════════════════


def parse_robots(text: str) -> dict:
    """解析 robots.txt 为 {sitemaps, groups}。

    groups: {ua_lower: [rule,...]}，键为 UA 名小写（`*` 即通配组）；连续多个
    `User-agent` 行共享其后同一套规则（RFC 9309 分组语义）。
    """
    sitemaps: list[str] = []
    groups: dict[str, list[str]] = {}
    current_agents: list[str] = []
    current_rules: list[str] = []

    def _flush() -> None:
        for agent in current_agents:
            groups.setdefault(agent.lower(), []).extend(current_rules)

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "sitemap":
            sitemaps.append(value)
        elif field == "user-agent":
            if current_agents and current_rules:
                # 上一组（UA + 规则）结束；连续的 UA 行共享同一套规则
                _flush()
                current_agents, current_rules = [], []
            current_agents.append(value)
        elif field in ("allow", "disallow") and current_agents:
            current_rules.append(f"{field}:{value}")
    _flush()
    return {"sitemaps": sitemaps, "groups": groups}


def _blocks_all(ua_rules: list[str]) -> bool:
    """该 UA 组是否整站禁止（Disallow: / 且无 Allow: /）。"""
    def _is_root(rule: str) -> bool:
        return rule.split(":", 1)[1].strip() == "/"

    disallow_all = any(_is_root(r) for r in ua_rules if r.startswith("disallow:"))
    allow_all = any(_is_root(r) for r in ua_rules if r.startswith("allow:"))
    return disallow_all and not allow_all


def parse_sitemap(xml_text: str) -> dict:
    """解析 sitemap.xml，返回 {urls: [{loc, lastmod}], error}。"""
    try:
        root = ET.fromstring(xml_text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries = root.findall(".//sm:url", ns) or root.findall(".//url")
        urls = []
        for e in entries:
            loc = (e.findtext("sm:loc", default="", namespaces=ns) or e.findtext("loc", default="")).strip()
            lastmod = (e.findtext("sm:lastmod", default="", namespaces=ns) or e.findtext("lastmod", default="")).strip()
            if loc:
                urls.append({"loc": loc, "lastmod": lastmod or None})
        return {"urls": urls, "error": None}
    except ET.ParseError as e:  # 诚实报错，不静默当作空 sitemap
        return {"urls": [], "error": f"sitemap 解析失败：{e}"}


_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)


def parse_jsonld(html: str) -> dict:
    """提取 index.html 中的 JSON-LD 块，返回 {blocks, types, error}。"""
    blocks: list[dict] = []
    errors: list[str] = []
    for raw in _JSONLD_RE.findall(html):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError as e:
            errors.append(f"JSON-LD 解析失败：{e}")
            continue
        blocks.extend(data if isinstance(data, list) else [data])

    def _types(node) -> set[str]:
        found: set[str] = set()
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                found.add(t)
            elif isinstance(t, list):
                found.update(x for x in t if isinstance(x, str))
            for v in node.values():
                found |= _types(v)
        elif isinstance(node, list):
            for v in node:
                found |= _types(v)
        return found

    types: set[str] = set()
    for b in blocks:
        types |= _types(b)
    return {"blocks": blocks, "types": sorted(types), "error": "; ".join(errors) or None}


def _age_days(lastmod: str | None, now: datetime | None = None) -> float | None:
    if not lastmod:
        return None
    try:
        dt = datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return max(0.0, ((now or _now()) - dt).total_seconds() / 86400.0)


def count_content_pages(public_dir: Path | None) -> int:
    """统计非应用外壳的静态内容页（排除 index.html / console / assets）。"""
    if not public_dir or not public_dir.is_dir():
        return 0
    n = 0
    for p in public_dir.rglob("*.html"):
        rel = p.relative_to(public_dir)
        if rel.name in _CONTENT_PAGE_EXCLUDE:
            continue
        if set(rel.parts[:-1]) & _CONTENT_PAGE_EXCLUDE_DIRS:
            continue
        n += 1
    return n


# ════════════════════════════════════════════════════════════════
# 检查项定义（weight 合计 100；remediation 供修复清单模块消费）
# ════════════════════════════════════════════════════════════════

CHECKS: list[dict] = [
    # ── 可抓取 30 ──
    {"id": "robots_txt_present", "dimension": "crawler_access", "weight": 8,
     "title": "robots.txt 存在",
     "remediation": None},
    {"id": "sitemap_declared_in_robots", "dimension": "crawler_access", "weight": 6,
     "title": "robots.txt 声明 sitemap",
     "remediation": {"action": None, "tier": "confirm",
                     "rationale": "sitemap 地址属站点自报事实，须人工确认后修改 robots.txt"}},
    {"id": "ai_crawler_policy", "dimension": "crawler_access", "weight": 8,
     "title": "显式声明 AI 检索类爬虫访问策略",
     "remediation": {"action": "update_robots_ai_agents", "tier": "auto",
                     "rationale": "仅在 robots.txt 追加 AI 爬虫声明块，不改既有规则，可备份回滚"}},
    {"id": "sitemap_present", "dimension": "crawler_access", "weight": 8,
     "title": "sitemap.xml 存在且可解析",
     "remediation": None},

    # ── 可理解 25 ──
    {"id": "index_html_present", "dimension": "machine_readable", "weight": 5,
     "title": "站点入口 HTML 存在",
     "remediation": None},
    {"id": "title_present", "dimension": "machine_readable", "weight": 5,
     "title": "页面 title 非空",
     "remediation": {"action": None, "tier": "human_only",
                     "rationale": "标题承载品牌表述，属企业事实，须人工定稿"}},
    {"id": "meta_description", "dimension": "machine_readable", "weight": 5,
     "title": "meta description 非空且长度合理（20~200 字）",
     "remediation": {"action": None, "tier": "human_only",
                     "rationale": "摘要承载业务表述，属企业事实，AI 不得代写"}},
    {"id": "html_lang", "dimension": "machine_readable", "weight": 3,
     "title": "<html lang> 已声明",
     "remediation": {"action": None, "tier": "confirm",
                     "rationale": "语言声明可在人工确认后批量补全"}},
    {"id": "structured_data_present", "dimension": "machine_readable", "weight": 4,
     "title": "存在 JSON-LD 结构化数据",
     "remediation": {"action": None, "tier": "confirm",
                     "rationale": "结构化数据补全涉及品牌字段取值，须人工确认"}},
    {"id": "noscript_text_fallback", "dimension": "machine_readable", "weight": 3,
     "title": "无 JS 时可读的文本兜底（noscript）",
     "remediation": {"action": None, "tier": "human_only",
                     "rationale": "兜底文案属对外表述，须人工撰写"}},

    # ── 可引用 25 ──
    {"id": "structured_data_business_entity", "dimension": "citable", "weight": 8,
     "title": "结构化数据含业务实体（Service/Product/Offer/FAQ 等）",
     "remediation": {"action": None, "tier": "human_only",
                     "rationale": "业务实体字段（服务范围/价格逻辑/案例）属企业事实，AI 不得编造"}},
    {"id": "organization_profile_fields", "dimension": "citable", "weight": 5,
     "title": "组织实体字段完整（名称 + 网址 + logo + sameAs/联系方式）",
     "remediation": {"action": None, "tier": "human_only",
                     "rationale": "资质与联系方式属企业事实，须人工核实后再写入"}},
    {"id": "sitemap_lastmod_complete", "dimension": "citable", "weight": 7,
     "title": "sitemap 全部 URL 带 lastmod",
     "remediation": {"action": None, "tier": "confirm",
                     "rationale": "lastmod 为站点自报时间，须人工确认后刷新"}},
    {"id": "public_content_pages", "dimension": "citable", "weight": 5,
     "title": "存在可抓取的公开内容页（非应用外壳）",
     "remediation": {"action": None, "tier": "human_only",
                     "rationale": "内容页承载服务说明与案例，属企业事实与发布权限，须人工产出"}},

    # ── 新鲜度 20 ──
    {"id": "sitemap_lastmod_freshness", "dimension": "freshness", "weight": 12,
     "title": "sitemap 最新 lastmod 在 30 天内",
     "remediation": {"action": None, "tier": "confirm",
                     "rationale": "刷新自报时间须确认真有内容更新，不得空刷"}},
    {"id": "llms_txt_present", "dimension": "freshness", "weight": 8,
     "title": "llms.txt（AI 友好站点摘要）存在",
     "remediation": {"action": "write_llms_txt", "tier": "auto",
                     "rationale": "由站点既有公开信息确定性生成，新增文件不改既有产物，可回滚（删除即还原）"}},
]

# 白名单：可被平台自动执行的修复动作（仅「说明书层」——不改既有内容、不碰承重墙）
AUTO_REMEDIATION_ACTIONS: tuple[str, ...] = ("write_llms_txt", "update_robots_ai_agents")

_LEVELS = ((85, "ready", "就绪", "关键可抓取/可理解项均达标，可进入内容持续运营阶段"),
           (60, "partial", "部分就绪", "存在影响 AI 获取与理解的结构性缺口，建议按修复清单逐项处理"),
           (0, "insufficient", "未就绪", "存在阻断性缺口，AI 难以获取或理解站点内容"))


def _level_for(score: int) -> tuple[str, str, str]:
    for threshold, key, name, note in _LEVELS:
        if score >= threshold:
            return key, name, note
    return "insufficient", "未就绪", ""


def _check(cid: str, status: str, evidence, **extra) -> dict:
    meta = next(c for c in CHECKS if c["id"] == cid)
    item = {
        "id": cid,
        "dimension": meta["dimension"],
        "title": meta["title"],
        "weight": meta["weight"],
        "status": status,
        "evidence": evidence,
    }
    item.update(extra)
    return item


def _robots_checks(robots_text: str | None) -> tuple[list[dict], dict]:
    if robots_text is None:
        return [
            _check("robots_txt_present", "fail", "未找到 robots.txt"),
            _check("sitemap_declared_in_robots", "unknown", "robots.txt 缺失，无法判定"),
            _check("ai_crawler_policy", "fail", "robots.txt 缺失，AI 爬虫策略未声明"),
        ], {"declared": [], "sitemap_declared": False}

    parsed = parse_robots(robots_text)
    groups = parsed["groups"]
    star = groups.get("*", [])
    blocked_ai = [ua for ua, rules in groups.items() if ua != "*" and _blocks_all(rules)]
    declared = [
        ua for ua in AI_CRAWLERS
        if any(g.lower() == ua.lower() for g in groups)
    ]
    site_blocked = _blocks_all(star)

    checks = [_check("robots_txt_present", "pass", f"robots.txt 可读（{len(robots_text)} 字节）")]

    if parsed["sitemaps"]:
        checks.append(_check("sitemap_declared_in_robots", "pass",
                             f"已声明 {len(parsed['sitemaps'])} 个 sitemap：{parsed['sitemaps'][0]}"))
    else:
        checks.append(_check("sitemap_declared_in_robots", "fail",
                             "robots.txt 未声明 Sitemap 指向"))

    if blocked_ai:
        checks.append(_check("ai_crawler_policy", "fail",
                             f"以下 AI 爬虫被整站禁止：{blocked_ai}"))
    elif site_blocked:
        checks.append(_check("ai_crawler_policy", "fail",
                             "`User-agent: *` 整站禁止抓取（Disallow: / 且无 Allow: /）"))
    elif declared:
        checks.append(_check("ai_crawler_policy", "pass",
                             f"已显式声明 {len(declared)} 个 AI 爬虫：{declared}"))
    else:
        checks.append(_check("ai_crawler_policy", "warn",
                             "未显式声明任何 AI 检索类爬虫（仅靠 `User-agent: *` 兜底，策略意图不明确）"))

    return checks, {"declared": declared, "sitemap_declared": bool(parsed["sitemaps"]),
                    "site_blocked": site_blocked, "blocked_ai": blocked_ai}


def _sitemap_checks(art: dict) -> tuple[list[dict], dict]:
    """sitemap 存在性与可解析性检查（解析失败诚实报错）。"""
    if not art["sitemap"]:
        return [_check("sitemap_present", "fail", "未找到 sitemap.xml")], {"urls": [], "error": None}

    meta = parse_sitemap(art["sitemap"].read_text(encoding="utf-8"))
    if meta["error"]:
        return [_check("sitemap_present", "fail", meta["error"])], meta
    if not meta["urls"]:
        return [_check("sitemap_present", "fail", "sitemap 可解析但无 URL 条目")], meta
    return [_check("sitemap_present", "pass", f"可解析，含 {len(meta['urls'])} 条 URL")], meta


def _html_checks(art: dict) -> tuple[list[dict], dict]:
    """index.html 的可理解性检查（title / description / lang / JSON-LD / noscript）。"""
    checks: list[dict] = []
    if art["index_html"] is None:
        checks.append(_check("index_html_present", "fail", "未找到站点入口 index.html"))
        for cid in ("title_present", "meta_description", "html_lang",
                    "structured_data_present", "noscript_text_fallback"):
            checks.append(_check(cid, "unknown", "index.html 缺失，无法判定"))
        return checks, {"blocks": [], "types": [], "error": None}

    html = art["index_html"].read_text(encoding="utf-8")
    checks.append(_check("index_html_present", "pass", f"{_rel(art['index_html'])}（{len(html)} 字节）"))

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title_text = title.group(1).strip() if title else ""
    checks.append(_check("title_present", "pass" if title_text else "fail",
                         f"title={title_text[:80]!r}" if title_text else "未找到非空 <title>"))

    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.S | re.I)
    desc_text = desc.group(1).strip() if desc else ""
    if not desc_text:
        checks.append(_check("meta_description", "fail", "未找到非空 meta description"))
    elif 20 <= len(desc_text) <= 200:
        checks.append(_check("meta_description", "pass", f"长度 {len(desc_text)} 字"))
    else:
        checks.append(_check("meta_description", "warn", f"长度 {len(desc_text)} 字（建议 20~200 字）"))

    lang = re.search(r"""<html[^>]+lang=["']([^"']+)["']""", html, re.I)
    checks.append(_check("html_lang", "pass" if lang else "fail",
                         f"lang={lang.group(1)}" if lang else "未声明 <html lang>"))

    jsonld = parse_jsonld(html)
    if jsonld["blocks"]:
        checks.append(_check("structured_data_present", "pass",
                             f"JSON-LD {len(jsonld['blocks'])} 块，类型：{jsonld['types']}"))
    elif jsonld["error"]:
        checks.append(_check("structured_data_present", "fail", jsonld["error"]))
    else:
        checks.append(_check("structured_data_present", "fail", "未找到 application/ld+json"))

    noscript = re.search(r"<noscript[^>]*>(.*?)</noscript>", html, re.S | re.I)
    noscript_text = re.sub(r"<[^>]+>", "", noscript.group(1)).strip() if noscript else ""
    checks.append(_check("noscript_text_fallback", "pass" if len(noscript_text) >= 20 else "fail",
                         f"noscript 纯文本 {len(noscript_text)} 字" if noscript_text
                         else "无 noscript 文本兜底（禁 JS 的抓取方只能读到空壳）"))
    return checks, jsonld


_ORG_TYPES = ("Organization", "LocalBusiness")
# 组织实体完整度字段：基础三项（缺即 fail）+ 交叉佐证三项（缺即 warn）
_ORG_REQUIRED_FIELDS = ("name", "url", "logo")
_ORG_EXTRA_FIELDS = ("sameAs", "contactPoint", "address")


def _collect_org_nodes(blocks: list) -> list[dict]:
    """递归收集组织实体候选节点（含 `@graph` 容器与任意层级嵌套）。

    单一 `Organization` 节点可出现在：顶层、`@graph` 数组内、`WebSite.publisher`
    （历史写法）。按首次出现顺序返回去重后的候选，供完整度择优。
    """
    found: list[dict] = []
    seen: set[int] = set()

    def _walk(node) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, dict):
            return
        node_type = node.get("@type")
        if node_type in _ORG_TYPES or (isinstance(node_type, list) and set(node_type) & set(_ORG_TYPES)):
            if id(node) not in seen:
                seen.add(id(node))
                found.append(node)
        for value in node.values():
            _walk(value)

    _walk(blocks)
    return found


def _pick_org(nodes: list[dict]) -> dict | None:
    """择优：字段最完整者优先（同分取首次出现），使 `@graph` 写法与扁平写法等价。"""
    if not nodes:
        return None
    fields = _ORG_REQUIRED_FIELDS + _ORG_EXTRA_FIELDS

    def _score(node: dict) -> int:
        return sum(1 for f in fields if node.get(f))

    return max(nodes, key=_score)


def _citable_checks(jsonld: dict) -> list[dict]:
    """业务实体与组织字段完整度（AI 可引用的事实的结构性前提）。"""
    checks: list[dict] = []
    biz = sorted(set(jsonld["types"]) & set(BUSINESS_ENTITY_TYPES))
    if biz:
        checks.append(_check("structured_data_business_entity", "pass", f"业务实体类型：{biz}"))
    elif jsonld["types"]:
        checks.append(_check("structured_data_business_entity", "fail",
                             f"仅有 {jsonld['types']}，缺少业务实体（回答不了「能提供什么」）"))
    else:
        checks.append(_check("structured_data_business_entity", "unknown", "无结构化数据，无法判定"))

    org = _pick_org(_collect_org_nodes(jsonld["blocks"]))
    if org is None:
        return checks + [_check("organization_profile_fields", "fail", "未找到 Organization 实体")]

    missing = [f for f in _ORG_REQUIRED_FIELDS if not org.get(f)]
    extra_missing = [f for f in _ORG_EXTRA_FIELDS if not org.get(f)]
    if not missing and not extra_missing:
        checks.append(_check("organization_profile_fields", "pass", "名称/网址/logo/资质关联字段齐全"))
    elif not missing:
        checks.append(_check("organization_profile_fields", "warn",
                             f"基础字段齐全，缺 {extra_missing}（AI 交叉校验依赖第三方佐证）"))
    else:
        checks.append(_check("organization_profile_fields", "fail", f"组织实体缺 {missing}"))
    return checks


def _lastmod_checks(urls: list[dict], now: datetime) -> list[dict]:
    """sitemap 时间戳完整性与新鲜度（「长草」风险）。"""
    if not urls:
        return [_check("sitemap_lastmod_complete", "unknown", "无 sitemap URL 可判定"),
                _check("sitemap_lastmod_freshness", "unknown", "无 sitemap URL 可判定")]

    with_lastmod = [u for u in urls if u["lastmod"]]
    if len(with_lastmod) == len(urls):
        complete = _check("sitemap_lastmod_complete", "pass", f"{len(urls)}/{len(urls)} 带 lastmod")
    elif with_lastmod:
        complete = _check("sitemap_lastmod_complete", "warn", f"{len(with_lastmod)}/{len(urls)} 带 lastmod")
    else:
        complete = _check("sitemap_lastmod_complete", "fail", "全部 URL 缺 lastmod")

    ages = [(a, u) for u in with_lastmod if (a := _age_days(u["lastmod"], now)) is not None]
    if not ages:
        return [complete, _check("sitemap_lastmod_freshness", "unknown", "lastmod 均无法解析为时间")]

    age, newest_url = min(ages, key=lambda pair: pair[0])
    ev = f"最新 lastmod={newest_url['lastmod']}（{age:.1f} 天前，站点自报时间）"
    if age <= 30:
        fresh = _check("sitemap_lastmod_freshness", "pass", ev)
    elif age <= 90:
        fresh = _check("sitemap_lastmod_freshness", "warn", ev)
    else:
        fresh = _check("sitemap_lastmod_freshness", "fail",
                       ev + "；超过 90 天未更新，内容存在「长草」风险")
    return [complete, fresh]


def _score(checks: list[dict]) -> tuple[int, str, str, str, dict]:
    """四维加权计分（pass 满分 / warn 半分 / fail·unknown 零分）。"""
    by_dim = {d["key"]: {"key": d["key"], "name": d["name"], "weight": d["weight"],
                         "desc": d["desc"], "earned": 0, "max": 0} for d in DIMENSIONS}
    for c in checks:
        dim = by_dim[c["dimension"]]
        dim["max"] += c["weight"]
        if c["status"] == "pass":
            dim["earned"] += c["weight"]
        elif c["status"] == "warn":
            dim["earned"] += c["weight"] / 2
    for dim in by_dim.values():
        dim["earned"] = round(dim["earned"], 1)
        dim["ratio"] = round(dim["earned"] / dim["max"], 3) if dim["max"] else 0.0

    score = round(sum(dim["earned"] for dim in by_dim.values()))
    level_key, level_name, level_note = _level_for(score)
    return score, level_key, level_name, level_note, by_dim


def _remediation_candidates(checks: list[dict]) -> list[dict]:
    """非 pass 且定义了修复动作的检查项 → 清单候选（供修复清单模块消费）。"""
    candidates = []
    for c in checks:
        if c["status"] == "pass":
            continue
        rem = next(m for m in CHECKS if m["id"] == c["id"]).get("remediation")
        if not rem:
            continue
        candidates.append({
            "source_check_id": c["id"],
            "title": c["title"],
            "status": c["status"],
            "dimension": c["dimension"],
            "action": rem["action"],
            "tier": rem["tier"],
            "rationale": rem["rationale"],
            "evidence": c["evidence"],
        })
    return candidates


def run_ai_visibility_audit(static_root: str | None = None, now: datetime | None = None) -> dict:
    """执行站点 AI 可见度就绪度审计（确定性，只读，无副作用）。"""
    now = now or _now()
    art = resolve_artifacts(static_root)
    checks: list[dict] = []

    robots_text = art["robots"].read_text(encoding="utf-8") if art["robots"] else None
    robots_checks, robots_meta = _robots_checks(robots_text)
    checks.extend(robots_checks)

    sitemap_checks, sitemap_meta = _sitemap_checks(art)
    checks.extend(sitemap_checks)

    html_checks, jsonld_meta = _html_checks(art)
    checks.extend(html_checks)
    checks.extend(_citable_checks(jsonld_meta))
    checks.extend(_lastmod_checks(sitemap_meta["urls"], now))

    n_pages = count_content_pages(art["public_dir"])
    if art["public_dir"] is None:
        checks.append(_check("public_content_pages", "unknown", "未定位到静态产物目录"))
    elif n_pages > 0:
        checks.append(_check("public_content_pages", "pass", f"公开内容页 {n_pages} 个"))
    else:
        checks.append(_check("public_content_pages", "fail",
                             "无公开内容页——站点为纯应用外壳，抓取方读不到服务说明与案例"))

    if art["llms"]:
        checks.append(_check("llms_txt_present", "pass",
                             f"{_rel(art['llms'])}（{art['llms'].stat().st_size} 字节）"))
    else:
        checks.append(_check("llms_txt_present", "fail",
                             "未找到 llms.txt（AI 友好的站点摘要文件；业界先行约定，非正式标准）"))

    score, level_key, level_name, level_note, by_dim = _score(checks)
    candidates = _remediation_candidates(checks)

    return {
        "generated_at": _now_iso(),
        "module": MODULE_PATH,
        "method": METHOD,
        "model_probing": False,
        "static_root": art["public_dir_rel"],
        "index_html": (_rel(art["index_html"]) if art["index_html"] else None),
        "artifacts": {
            "robots_txt": bool(art["robots"]),
            "sitemap_xml": bool(art["sitemap"]),
            "index_html": bool(art["index_html"]),
            "llms_txt": bool(art["llms"]),
        },
        "score": score,
        "level": level_key,
        "level_name": level_name,
        "level_note": level_note,
        "dimensions": list(by_dim.values()),
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "pass": sum(1 for c in checks if c["status"] == "pass"),
            "warn": sum(1 for c in checks if c["status"] == "warn"),
            "fail": sum(1 for c in checks if c["status"] == "fail"),
            "unknown": sum(1 for c in checks if c["status"] == "unknown"),
        },
        "robots": robots_meta,
        "structured_data_types": jsonld_meta["types"],
        "sitemap_url_count": len(sitemap_meta["urls"]),
        "content_page_count": n_pages,
        "remediation_candidates": candidates,
        "limitations": [
            "不做真实模型探测：未调用任何 AI 平台，无法证明站点是否已被引用",
            "分数为站点自身条件评估（静态产物确定性检查），与第三方平台算法无关，不构成效果承诺",
            "llms.txt 为业界先行约定（无正式标准），缺失仅计入就绪度",
            "sitemap lastmod 为站点自报时间，不等于平台实测抓取时间",
            "「公开内容页」按静态 HTML 计数，不覆盖由后端服务端渲染的公开页面",
        ],
        "disclaimer": DISCLAIMER,
    }
