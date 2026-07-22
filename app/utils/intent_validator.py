"""意图契约校验脚本（借鉴索克生活 Feature Validation Pipeline）

用途：
1. CI 校验：新增 agent-router pattern 必须在 intent_contract.json 中登记且 validation_status=validated
2. 启动时校验：app/main.py lifespan 可选调用确保契约完整性
3. 手动校验：python -m app.utils.intent_validator

校验规则：
- 每个 pattern 必须含 pattern_id / agent / validation_status / required_slots / examples
- pattern_id 必须为 snake_case
- validation_status 必须为 validated/draft/deprecated 之一
- examples 至少 1 条
- 与 web/assets/js/agent-router.js 的 patterns 做一致性比对（可选）

退出码：0=通过，1=校验失败
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from app.config import get_settings

settings = get_settings()

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VALID_STATUS = {"validated", "draft", "deprecated"}
_REQUIRED_FIELDS = {"pattern_id", "agent", "validation_status", "required_slots", "examples"}


def load_contract() -> dict:
    """加载 intent_contract.json。"""
    contract_path = Path(__file__).resolve().parents[2] / settings.intent_contract_path
    if not contract_path.exists():
        return {"patterns": [], "validation_rules": {}}
    return json.loads(contract_path.read_text(encoding="utf-8"))


def validate_contract(contract: dict | None = None) -> list[str]:
    """校验意图契约，返回错误列表（空列表表示通过）。

    Args:
        contract: 已加载的契约 dict，None 则重新加载

    Returns:
        errors: 错误消息列表
    """
    if contract is None:
        contract = load_contract()
    errors: list[str] = []
    patterns = contract.get("patterns", [])
    rules = contract.get("validation_rules", {})

    if not patterns:
        errors.append("intent_contract: patterns 为空")
        return errors

    seen_ids: set[str] = set()
    for i, p in enumerate(patterns):
        prefix = f"pattern[{i}]"

        # 必填字段
        missing = _REQUIRED_FIELDS - set(p.keys())
        if missing:
            errors.append(f"{prefix}: 缺失字段 {missing}")
            continue

        pid = p["pattern_id"]

        # ID 唯一性
        if pid in seen_ids:
            errors.append(f"{prefix}: pattern_id '{pid}' 重复")
        seen_ids.add(pid)

        # snake_case
        if rules.get("pattern_id_must_be_snake_case", True) and not _SNAKE_CASE_RE.match(pid):
            errors.append(f"{prefix}: pattern_id '{pid}' 不符合 snake_case")

        # validation_status
        status = p["validation_status"]
        valid_status = rules.get("valid_validation_status") or list(_VALID_STATUS)
        if status not in valid_status:
            errors.append(f"{prefix} '{pid}': validation_status '{status}' 无效，应为 {valid_status}")

        # examples 数量
        min_examples = rules.get("min_examples_per_pattern", 1)
        examples = p.get("examples", [])
        if len(examples) < min_examples:
            errors.append(f"{prefix} '{pid}': examples 少于 {min_examples} 条")

        # required_slots 非空
        if rules.get("required_slots_non_empty", True) and not p.get("required_slots"):
            errors.append(f"{prefix} '{pid}': required_slots 为空")

    return errors


def validate_against_router_js() -> list[str]:
    """与 web/assets/js/agent-router.js 的 patterns 做一致性比对。

    返回不一致的 pattern_id 列表（仅警告，不阻断 CI）。
    """
    errors: list[str] = []
    try:
        router_js = Path(__file__).resolve().parents[2] / "web" / "assets" / "js" / "agent-router.js"
        if not router_js.exists():
            return ["agent-router.js 不存在，跳过一致性比对"]
        content = router_js.read_text(encoding="utf-8")
        # 提取 agent: 'xxx' 或 agent: "xxx" 的值作为 pattern id
        router_ids = set(re.findall(r"agent['\"]?\s*:\s*['\"]([a-z0-9_]+)['\"]", content))
        contract = load_contract()
        contract_ids = {p["pattern_id"] for p in contract.get("patterns", [])}
        only_in_router = router_ids - contract_ids
        only_in_contract = contract_ids - router_ids
        if only_in_router:
            errors.append(f"agent-router.js 有但 intent_contract 缺失: {sorted(only_in_router)}")
        if only_in_contract:
            errors.append(f"intent_contract 有但 agent-router.js 缺失: {sorted(only_in_contract)}")
    except Exception as e:
        errors.append(f"一致性比对失败: {e}")
    return errors


def main() -> int:
    """CI 入口：校验契约，失败返回 1。"""
    print("=" * 60)
    print("i-home.life 意图契约校验 (Feature Validation Pipeline)")
    print("=" * 60)

    contract = load_contract()
    patterns = contract.get("patterns", [])
    print(f"已加载 {len(patterns)} 个 pattern")

    errors = validate_contract(contract)
    if errors:
        print("\n❌ 契约校验失败：")
        for e in errors:
            print(f"  - {e}")
        return 1

    validated = [p for p in patterns if p["validation_status"] == "validated"]
    print(f"\n✅ 契约校验通过：{len(validated)} validated / {len(patterns)} total")

    # 一致性比对（仅警告）
    warnings = validate_against_router_js()
    for w in warnings:
        print(f"  ⚠ {w}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
