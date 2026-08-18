"""Agent 长期记忆服务 — 跨会话记忆的存储、提取与上下文注入

设计要点：
- 记忆以 (user_id, category, memory_key) 为唯一键 upsert，天然去重
- 自动提取为轻量规则匹配（城市/偏好句式），不做 LLM 依赖，保证 mock 模式可用
- 上下文注入按 updated_at 倒序 + importance 排序，受 settings.agent_memory_max_items 限制
- 所有查询强制 user_id 隔离，无 user_id 直接返回空（不泄漏）
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_memory import AgentMemory

logger = logging.getLogger(__name__)

# 记忆类目常量
CATEGORY_PREFERENCE = "preference"
CATEGORY_LOCATION = "location"
CATEGORY_FACT = "fact"
_ALL_CATEGORIES = (CATEGORY_PREFERENCE, CATEGORY_LOCATION, CATEGORY_FACT)

# v1.4.x 记忆作用域常量（借鉴 YC QM Scope）：
# personal=仅本人 / project=项目内共享 / team=团队 / org=全组织
SCOPE_PERSONAL = "personal"
SCOPE_PROJECT = "project"
SCOPE_TEAM = "team"
SCOPE_ORG = "org"
_ALL_SCOPES = (SCOPE_PERSONAL, SCOPE_PROJECT, SCOPE_TEAM, SCOPE_ORG)

# ── 自动提取规则（轻量规则匹配，mock 模式可用）──

_CITY_PATTERN = re.compile(r"([\u4e00-\u9fa5]{2,8}(?:市|县|区))")
# 常见城市名（无「市」后缀的常见表达，如「我在北京」）
_MAJOR_CITIES = (
    "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "重庆", "武汉",
    "西安", "天津", "苏州", "长沙", "郑州", "青岛", "大连", "厦门", "佛山",
    "东莞", "无锡", "宁波", "合肥", "福州", "昆明", "济南", "石家庄",
    "哈尔滨", "沈阳", "长春", "贵阳", "南宁", "海口", "兰州", "太原",
    "乌鲁木齐", "南昌", "银川",
)
# 「小区」等生活词不是行政区名，排除误提取
_CITY_BLACKLIST = ("小区", "园区")
_PREFERENCE_KEYWORDS = (
    "我喜欢", "喜欢", "偏爱", "偏好", "中意", "想要", "追求",
    "不喜欢", "讨厌", "不要", "忌讳",
)
_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?\n]+")

# 偏好句长度限制（过短无信息量，过长截断防 prompt 膨胀）
_PREF_SENTENCE_MIN = 4
_PREF_SENTENCE_MAX = 120


def _truncate(text: str, limit: int = 120) -> str:
    return text[:limit]


def _extract_city(message: str) -> str:
    """提取城市/区县（如「我在北京」「家在杭州西湖区」）"""
    m = _CITY_PATTERN.search(message)
    if m:
        city = m.group(1)
        if any(b in city for b in _CITY_BLACKLIST):
            return ""
        return city
    # 无「市/县/区」后缀时匹配常见城市名（如「我在北京」）
    for city in _MAJOR_CITIES:
        if city in message:
            return city
    return ""


def _extract_preference_sentences(message: str) -> list[str]:
    """提取含偏好关键词的短句（去重保序）"""
    seen: set[str] = set()
    out: list[str] = []
    for sent in _SENTENCE_SPLIT_RE.split(message):
        sent = sent.strip()
        if not sent:
            continue
        if any(kw in sent for kw in _PREFERENCE_KEYWORDS):
            if not (_PREF_SENTENCE_MIN <= len(sent) <= _PREF_SENTENCE_MAX):
                continue
            if sent in seen:
                continue
            seen.add(sent)
            out.append(sent)
    return out


def _key_for(text: str) -> str:
    """由文本生成稳定记忆 key（用于去重）"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ── v1.9.0 记忆冲突门控（防记忆漂移/投毒，SSGM 思路）──

# 冲突判定阈值：相似度低于该值判为冲突（SequenceMatcher.ratio() ∈ [0,1]）
_CONFLICT_SIMILARITY_THRESHOLD = 0.35
# 冲突检测最小长度（过短的记忆无判定价值，直接放行）
_CONFLICT_MIN_LEN = 4


def detect_conflict(old_value: str, new_value: str) -> tuple[bool, float]:
    """记忆冲突检测（纯函数，简单相似度，无需 LLM）。

    相同/包含 → (False, 相似度)；相似度低于阈值且双方长度均 >= 4 → 冲突 (True, 相似度)。
    相似度用 difflib.SequenceMatcher.ratio()（公共子序列占比）。
    """
    if old_value is None:
        old_value = ""
    if new_value is None:
        new_value = ""
    old_value = str(old_value)
    new_value = str(new_value)
    ratio = difflib.SequenceMatcher(None, old_value, new_value).ratio()
    if old_value == new_value:
        return False, ratio
    if len(old_value.strip()) < _CONFLICT_MIN_LEN or len(new_value.strip()) < _CONFLICT_MIN_LEN:
        return False, ratio
    return ratio < _CONFLICT_SIMILARITY_THRESHOLD, ratio


def build_conflict_gate_result(mem: AgentMemory) -> dict:
    """将带冲突标记的 ORM 对象转换为可返回给调用方的 dict。

    无冲突时返回 {"conflict": False}；有冲突时返回旧/新值与人工复核提示。
    """
    if not getattr(mem, "conflict_detected", False):
        return {"conflict": False}
    return {
        "conflict": True,
        "old_value": getattr(mem, "conflict_old_value", ""),
        "new_value": getattr(mem, "conflict_new_value", ""),
        "message": "记忆冲突检测：存在与新值冲突的旧记忆，已保留旧值待人工复核（conflict gate）",
    }


# ── 读写 ──


async def save_memory(
    db: AsyncSession,
    user_id: str,
    category: str,
    key: str,
    value: str,
    source: str = "manual",
    importance: int = 1,
    scope: str = SCOPE_PERSONAL,
    project_id: str | None = None,
    gate_conflict: bool = False,
) -> AgentMemory:
    """保存/更新一条记忆（(user_id, category, scope, project_id, key) 唯一 upsert）。

    用户在多次会话中重复表达同一偏好时更新 value 与 updated_at，
    保证注入时取到最新表达。

    v1.4.x 记忆作用域（借鉴 YC QM Scope）：
    - scope=project 时必须提供 project_id，否则回退 personal 并告警
    - personal 作用域 project_id 落库为空串，保证唯一约束生效

    v1.9.0 记忆冲突门控（memory_conflict_gate_enabled + gate_conflict=True）：
    - 检测到新旧值冲突时保留旧值（不覆盖），在 ORM 对象上附加
      conflict_detected / conflict_old_value / conflict_new_value 临时属性，
      调用方可用 build_conflict_gate_result(mem) 读取；
    - flag 关闭或 gate_conflict 未显式开启时保持原 upsert 行为（零回归）。
    """
    from sqlalchemy import select as _select

    if category not in _ALL_CATEGORIES:
        category = CATEGORY_FACT
    if scope not in _ALL_SCOPES:
        scope = SCOPE_PERSONAL
    if scope == SCOPE_PROJECT and not project_id:
        logger.warning(
            "agent_memory.save_memory: scope=project 但缺 project_id，回退 personal (user=%s)",
            user_id,
        )
        scope = SCOPE_PERSONAL
    project_id = project_id or ""

    value = _truncate(value)

    stmt = _select(AgentMemory).where(
        AgentMemory.user_id == user_id,
        AgentMemory.category == category,
        AgentMemory.scope == scope,
        AgentMemory.project_id == project_id,
        AgentMemory.memory_key == key,
    )
    result = await db.execute(stmt)
    mem = result.scalar_one_or_none()
    if mem is None:
        mem = AgentMemory(
            user_id=user_id,
            category=category,
            memory_key=key,
            memory_value=value,
            source=source,
            importance=importance,
            scope=scope,
            project_id=project_id,
        )
        db.add(mem)
    else:
        # v1.9.0 冲突门控：flag 开启 + 调用方显式请求 + 新旧值判为冲突 → 保留旧值待人工复核
        conflict_enabled = get_settings().memory_conflict_gate_enabled
        if conflict_enabled and gate_conflict:
            is_conflict, _ratio = detect_conflict(mem.memory_value, value)
            if is_conflict:
                mem.conflict_detected = True
                mem.conflict_old_value = mem.memory_value
                mem.conflict_new_value = value
                await db.commit()
                await db.refresh(mem)
                return mem
        mem.memory_value = value
        mem.source = source
        mem.importance = importance
    await db.commit()
    await db.refresh(mem)
    return mem


async def get_user_memories(
    db: AsyncSession,
    user_id: str,
    categories: list[str] | None = None,
    limit: int = 20,
    scope: str | None = None,
    project_id: str | None = None,
) -> list[AgentMemory]:
    """获取用户记忆（按 updated_at 倒序），并记录访问统计。

    categories 为空时返回全部类目。调用方必须传入有效 user_id。
    v1.4.x：scope 为空时返回全部作用域（兼容旧行为）；指定 scope 时
    仅返回该作用域记忆；project 作用域可再按 project_id 过滤。
    """
    if not user_id:
        return []
    stmt = select(AgentMemory).where(AgentMemory.user_id == user_id)
    if categories:
        stmt = stmt.where(AgentMemory.category.in_(categories))
    if scope:
        stmt = stmt.where(AgentMemory.scope == scope)
        if scope == SCOPE_PROJECT and project_id:
            stmt = stmt.where(AgentMemory.project_id == project_id)
    stmt = stmt.order_by(desc(AgentMemory.updated_at)).limit(limit)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    # 访问统计（best-effort，失败不影响主流程）
    try:
        now = datetime.now(timezone.utc)
        for m in rows:
            m.access_count = (m.access_count or 0) + 1
            m.last_accessed_at = now
        await db.commit()
        # onupdate=func.now() 的 updated_at 在 flush 后会被标记为过期；
        # 异步上下文访问过期列会触发惰性刷新报 MissingGreenlet，故显式 refresh
        for m in rows:
            await db.refresh(m)
    except Exception:
        logger.debug("agent_memory.access_stat_update_failed", exc_info=True)
    return rows


async def delete_memory(db: AsyncSession, user_id: str, memory_id: str) -> bool:
    """删除用户的一条记忆（强隔离 user_id）"""
    from sqlalchemy import delete as _delete

    result = await db.execute(
        _delete(AgentMemory).where(
            AgentMemory.id == memory_id,
            AgentMemory.user_id == user_id,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def get_org_memories(db: AsyncSession, limit: int = 20) -> list[AgentMemory]:
    """v1.15.7 组织级共享记忆（信通院记忆分级「跨 Agent 共享」对齐）。

    返回 scope=org 的记忆（平台管理员写入、全平台成员可读——org 为平台
    天然成员域）。team 级共享因项目无 Team 实体暂缓（P2 路线图，诚实标注）。
    只读 + 访问统计（与 get_user_memories 同构）。
    """
    stmt = (
        select(AgentMemory)
        .where(AgentMemory.scope == SCOPE_ORG)
        .order_by(desc(AgentMemory.updated_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    try:
        now = datetime.now(timezone.utc)
        for m in rows:
            m.access_count = (m.access_count or 0) + 1
            m.last_accessed_at = now
        await db.commit()
        for m in rows:
            await db.refresh(m)
    except Exception:
        logger.debug("agent_memory.org_access_stat_update_failed", exc_info=True)
    return rows


async def build_memory_context(
    db: AsyncSession,
    user_id: str,
    limit: int | None = None,
    scope: str | None = None,
    project_id: str | None = None,
) -> str:
    """构建长期记忆注入上下文（供 chat 端点拼接 user_ctx）。

    v1.4.x：可指定 scope/project_id 仅注入对应作用域的记忆
    （如项目维度记忆：scope=SCOPE_PROJECT + project_id=xxx）。
    """
    settings = get_settings()
    if not settings.agent_memory_enabled or not user_id:
        return ""
    max_items = limit or settings.agent_memory_max_items
    rows = await get_user_memories(db, user_id, limit=max_items, scope=scope, project_id=project_id)
    if not rows:
        return ""
    lines = []
    for m in rows:
        tag = {
            CATEGORY_PREFERENCE: "偏好",
            CATEGORY_LOCATION: "位置",
            CATEGORY_FACT: "事实",
        }.get(m.category, "记忆")
        lines.append(f"- [{tag}] {m.memory_value}")
    return "【用户长期记忆】\n" + "\n".join(lines)


# ── 自动提取 ──


async def extract_and_store_memories(
    db: AsyncSession,
    user_id: str,
    message: str,
    source: str = "chat",
    scope: str = SCOPE_PERSONAL,
    project_id: str | None = None,
) -> int:
    """从用户消息中自动提取并保存长期记忆（best-effort）。

    提取内容：
    - 城市/区县 → category=location, key=city
    - 含偏好关键词的短句 → category=preference, key=sha256(text)[:16]

    v1.4.x：scope/project_id 透传给 save_memory，支持项目维度记忆提取
    （借鉴 YC QM Scope，chat 在项目频道时记忆归属项目）。

    Returns:
        本次实际保存/更新的记忆条数
    """
    settings = get_settings()
    if not settings.agent_memory_enabled or not settings.agent_memory_extract_enabled:
        return 0
    if not user_id or not message:
        return 0

    saved = 0
    try:
        city = _extract_city(message)
        if city:
            await save_memory(
                db, user_id, CATEGORY_LOCATION, "city", city, source=source,
                scope=scope, project_id=project_id,
            )
            saved += 1
        for sent in _extract_preference_sentences(message):
            await save_memory(
                db, user_id, CATEGORY_PREFERENCE, _key_for(sent), sent,
                source=source, scope=scope, project_id=project_id,
            )
            saved += 1
    except Exception as e:
        logger.warning("agent_memory.extract_failed: %s", e)
    return saved
