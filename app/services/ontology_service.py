"""家装领域本体服务（P0，确定性只读，零外部依赖）

加载 ``app/ontology/*.json``，提供领域枚举、加载、检索与开放本体对齐映射：
- ``list_ontologies()``          列出可用本体领域
- ``load_ontology(domain)``      加载指定领域本体（未知/失败返回 None，诚实降级）
- ``get_ontology_alignments``     返回 Brick/BOT/IFC 术语对齐映射
- ``search_ontology``            简单关键词检索（诚实降级：LIKE 匹配，非语义检索）

设计约束（对齐 CLAUDE.md）：
- 确定性、只读、无 DB/网络副作用
- 文件加载用 ``lru_cache`` 避免重复读盘；加载失败仅 log warning 并返回 None
- 不引入 RDF/OWL 推理引擎（模块化单体红线）
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from app.ontology import ONTOLOGY_DOMAINS

logger = logging.getLogger(__name__)

_ONTOLOGY_DIR = Path(__file__).resolve().parents[1] / "ontology"


def _ontology_file(domain: str) -> Path:
    return _ONTOLOGY_DIR / f"{domain}_ontology.json"


def list_ontologies() -> list[str]:
    """列出可用本体领域。"""
    return list(ONTOLOGY_DOMAINS)


@lru_cache(maxsize=8)
def _read_ontology(domain: str) -> dict | None:
    """读盘并解析 JSON（lru_cache 缓存，避免重复 IO）。"""
    path = _ontology_file(domain)
    if not path.exists():
        logger.warning("ontology_file_missing: domain=%s", domain)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("ontology_load_failed: domain=%s error=%s", domain, e)
        return None


def load_ontology(domain: str) -> dict | None:
    """加载指定领域本体；未知领域或加载失败返回 None（诚实降级）。"""
    if domain not in ONTOLOGY_DOMAINS:
        return None
    return _read_ontology(domain)


def get_ontology_alignments(domain: str) -> dict:
    """返回该领域的开放本体对齐映射（Brick/BOT/IFC）。

    遍历本体的概念章节（spatial / element / fixture_furniture / materials），
    提取形如 ``{"bot": ..., "ifc": ..., "brick": ...}`` 的对齐字段。
    无对齐信息返回空 dict。
    """
    data = load_ontology(domain) or {}
    alignments: dict[str, dict] = {}
    for section in ("spatial", "element", "fixture_furniture", "materials"):
        for concept, meta in (data.get(section) or {}).items():
            if not isinstance(meta, dict):
                continue
            aligned = {k: v for k, v in meta.items() if k in ("bot", "ifc", "brick")}
            if aligned:
                alignments[concept] = aligned
    return alignments


def search_ontology(domain: str, query: str) -> list[dict]:
    """简单关键词检索（诚实降级：LIKE 匹配，非语义检索）。

    - ``agent`` 领域在 ``agents`` 列表中检索 id/name/role/capabilities；
    - 其余领域在概念章节（spatial/element/fixture_furniture/materials）中检索
      concept id 与 name。
    - 空 query 返回全部条目。
    """
    data = load_ontology(domain) or {}
    q = (query or "").strip().lower()

    if domain == "agent":
        agents = data.get("agents", []) or []
        if not q:
            return list(agents)
        return [
            a for a in agents
            if isinstance(a, dict) and (
                q in str(a.get("id", "")).lower()
                or q in str(a.get("name", "")).lower()
                or q in str(a.get("role", "")).lower()
                or any(q in str(c).lower() for c in (a.get("capabilities") or []))
            )
        ]

    results: list[dict] = []
    for section in ("spatial", "element", "fixture_furniture", "materials"):
        for concept, meta in (data.get(section) or {}).items():
            if not isinstance(meta, dict):
                continue
            name = str(meta.get("name", concept))
            if not q or q in concept.lower() or q in name.lower():
                results.append({"concept": concept, "_section": section, **meta})
    return results
