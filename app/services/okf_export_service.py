"""OKF v0.1 兼容知识包导出服务（档位 A：格式对齐，不改数据模型）

借鉴 Google Cloud 2026-06-12 开源的 Open Knowledge Format 规范，把现有
KnowledgeEntry 序列化为供应商中立的 Markdown + YAML frontmatter 知识包。

OKF v0.1 规范符合性：
- 每个 concept 文件有 YAML frontmatter，含必填 `type` 字段
- 保留文件名：index.md（渐进式披露目录）、log.md（变更日志）
- concept 间用标准 Markdown 链接，文件路径 = concept ID
- 消费方对缺失可选字段宽容（容错消费模型）

bundle 目录结构：
  knowledge_bundle/
  ├── index.md                 # 根目录（type: Collection）
  ├── log.md                   # 变更日志（type: Log）
  └── <domain>/
      ├── index.md             # 域目录（type: Collection）
      └── <entry_id>.md        # 单 concept（type: <domain>）

零新依赖：纯 stdlib（tarfile/io/json/datetime），YAML frontmatter 手动序列化。
"""

from __future__ import annotations

import io
import json
import tarfile
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeEntry
from app.services.knowledge_service import KNOWN_DOMAINS

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# OKF bundle 根目录名（tar.gz 内顶层目录）
_BUNDLE_ROOT = "knowledge_bundle"

# OKF v0.1 规范版本
_OKF_VERSION = "0.1"


async def build_okf_bundle(
    db: AsyncSession,
    *,
    domain: str | None = None,
    tenant_id: str | None = None,
    status_filter: str = "published",
) -> bytes:
    """构建 OKF v0.1 兼容知识包，返回 tar.gz 字节流。

    Args:
        db: 异步数据库会话
        domain: 限定知识域（None=全部已知域）
        tenant_id: 租户隔离，语义同 knowledge_service.search_online：
                   None=仅平台公共域（tenant_id IS NULL）；
                   非 None=该租户域 + 平台公共域
        status_filter: published（默认）/ draft / archived / all

    Returns:
        tar.gz 字节流，解压后为 _BUNDLE_ROOT 目录树

    Raises:
        ValueError: domain 不在 KNOWN_DOMAINS 或 status_filter 非法
    """
    if domain is not None and domain not in KNOWN_DOMAINS:
        raise ValueError(f"domain 不合法，可选: {', '.join(KNOWN_DOMAINS)}")
    if status_filter not in ("draft", "published", "archived", "all"):
        raise ValueError("status_filter 可选: draft/published/archived/all")

    entries = await _query_entries(db, domain=domain, tenant_id=tenant_id, status_filter=status_filter)

    # 按域分组
    by_domain: dict[str, list[KnowledgeEntry]] = defaultdict(list)
    for e in entries:
        by_domain[e.domain].append(e)

    # 内存构建 tar.gz
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        _add_text(tar, f"{_BUNDLE_ROOT}/index.md", _build_root_index(by_domain))
        _add_text(tar, f"{_BUNDLE_ROOT}/log.md", _build_log(entries))
        for d, items in by_domain.items():
            _add_text(tar, f"{_BUNDLE_ROOT}/{d}/index.md", _build_domain_index(d, items))
            for entry in items:
                _add_text(tar, f"{_BUNDLE_ROOT}/{d}/{entry.id}.md", _build_concept(entry))

    return buf.getvalue()


async def _query_entries(
    db: AsyncSession,
    *,
    domain: str | None,
    tenant_id: str | None,
    status_filter: str,
) -> list[KnowledgeEntry]:
    """查询条目，过滤逻辑对齐 knowledge_service.list_entries（不含分页）。"""
    stmt = select(KnowledgeEntry).where(KnowledgeEntry.deleted_at.is_(None))
    if domain:
        stmt = stmt.where(KnowledgeEntry.domain == domain)
    if status_filter != "all":
        stmt = stmt.where(KnowledgeEntry.status == status_filter)
    # 租户隔离：None=仅公共域；非 None=该租户 + 公共域
    if tenant_id is not None:
        stmt = stmt.where(
            or_(KnowledgeEntry.tenant_id == tenant_id, KnowledgeEntry.tenant_id.is_(None))
        )
    else:
        stmt = stmt.where(KnowledgeEntry.tenant_id.is_(None))
    stmt = stmt.order_by(KnowledgeEntry.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _add_text(tar: tarfile.TarFile, arcname: str, text: str) -> None:
    """把 UTF-8 文本作为文件加入 tar。"""
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mtime = int(datetime.now(timezone.utc).timestamp())
    tar.addfile(info, io.BytesIO(data))


def _yaml_escape(value: str) -> str:
    """YAML 标量简单转义：含特殊字符则双引号包裹。"""
    if value is None:
        return "null"
    # 含冒号/井号/方括号/换行/首尾空格 → 双引号
    if any(c in value for c in (":", "#", "[", "]", "\n")) or value != value.strip() or not value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _emit_frontmatter(meta: dict) -> str:
    """手动序列化 YAML frontmatter（避免引入 pyyaml 依赖）。

    必填 type；可选 title/resource/tags/timestamp/version/status/source/tenant_id/reviewed_by。
    tags 用行内数组格式 `[a, b]`。
    """
    lines = ["---"]
    for key in ("type", "title", "resource", "tags", "timestamp", "version",
                "status", "source", "tenant_id", "reviewed_by"):
        if key not in meta:
            continue
        val = meta[key]
        if key == "tags":
            if isinstance(val, list):
                inner = ", ".join(_yaml_escape(str(t)) for t in val)
                lines.append(f"tags: [{inner}]")
            else:
                lines.append(f"tags: {val}")
        elif val is None:
            lines.append(f"{key}: null")
        elif isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, (int, float)):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {_yaml_escape(str(val))}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _parse_tags(entry: KnowledgeEntry) -> list[str]:
    """反序列化 tags JSON（容错：解析失败返回空列表）。"""
    if not entry.tags:
        return []
    try:
        tags = json.loads(entry.tags)
        return tags if isinstance(tags, list) else []
    except json.JSONDecodeError:
        return []


def _iso(dt: datetime | None) -> str | None:
    """ISO 8601 时间戳（None → None）。"""
    if dt is None:
        return None
    # 确保 timezone-aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _build_concept(entry: KnowledgeEntry) -> str:
    """构建单 concept 文件内容：YAML frontmatter + Markdown body。"""
    frontmatter = _emit_frontmatter({
        "type": entry.domain,
        "title": entry.title,
        "resource": entry.citation,
        "tags": _parse_tags(entry),
        "timestamp": _iso(entry.updated_at),
        "version": entry.version,
        "status": entry.status,
        "source": entry.source,
        "tenant_id": entry.tenant_id,
        "reviewed_by": entry.reviewed_by,
    })
    body = f"# {entry.title}\n\n{entry.content}\n"
    return frontmatter + "\n" + body


def _build_root_index(by_domain: dict[str, list[KnowledgeEntry]]) -> str:
    """根 index.md：列出各知识域及条目数（渐进式披露）。"""
    frontmatter = _emit_frontmatter({
        "type": "Collection",
        "title": "i-home.life 知识库",
        "description": f"按 OKF v{_OKF_VERSION} 规范导出的知识包",
    })
    lines = ["# i-home.life 知识库", ""]
    lines.append(f"> OKF v{_OKF_VERSION} 兼容知识包，共 {sum(len(v) for v in by_domain.values())} 条概念。")
    lines.append("")
    lines.append("## 知识域")
    lines.append("")
    for d in KNOWN_DOMAINS:
        count = len(by_domain.get(d, []))
        if count == 0:
            lines.append(f"- `{d}/` — 0 条")
        else:
            lines.append(f"- [{d}/]({d}/index.md) — {count} 条")
    lines.append("")
    return frontmatter + "\n".join(lines)


def _build_domain_index(domain: str, entries: list[KnowledgeEntry]) -> str:
    """域 index.md：列出该域所有 concept 文件链接。"""
    frontmatter = _emit_frontmatter({
        "type": "Collection",
        "title": f"{domain} 知识域",
        "description": f"{len(entries)} 条概念",
    })
    lines = [f"# {domain}", ""]
    lines.append(f"共 {len(entries)} 条概念。")
    lines.append("")
    lines.append("## 概念列表")
    lines.append("")
    for e in entries:
        # 链接到 concept 文件，status 标注
        lines.append(f"- [{e.title}]({e.id}.md) — {e.status} v{e.version}")
    lines.append("")
    return frontmatter + "\n".join(lines)


def _build_log(entries: list[KnowledgeEntry]) -> str:
    """log.md：按 updated_at.date() 聚合的变更日志，newest first。"""
    frontmatter = _emit_frontmatter({
        "type": "Log",
        "title": "知识包变更日志",
        "description": f"由 OKF 导出器于 {datetime.now(_BJ_TZ).isoformat()} 生成",
    })
    lines = ["# 变更日志", ""]
    if not entries:
        lines.append("_无条目_")
        lines.append("")
        return frontmatter + "\n".join(lines)

    # 按 updated_at.date() 分组，newest first
    by_date: dict[str, list[KnowledgeEntry]] = defaultdict(list)
    for e in entries:
        dt = e.updated_at or e.created_at
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        by_date[dt.date().isoformat()].append(e)

    for date_str in sorted(by_date.keys(), reverse=True):
        lines.append(f"## {date_str}")
        lines.append("")
        for e in by_date[date_str]:
            lines.append(f"- `{e.domain}/{e.id}` v{e.version} — {e.title} [{e.status}]")
        lines.append("")

    return frontmatter + "\n".join(lines)
