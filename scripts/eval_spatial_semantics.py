"""空间语义金标评测脚本（P1，方向 C）

对标 2026 空间智能（SpatialLM / 3D-FRONT）的确定性评测脚手架：
1. **本体对齐检查**：`spatial_semantics_service` 的 `ROOM_TYPE_ALIASES` 是否与
   `app/ontology/renovation_ontology.json` 的 `room_types` 一致。
2. **确定性用例**：对样例 floorplan 跑 `analyze_spatial_semantics` /
   `build_spatial_foundation`，验证房间类型/区域聚合/空间底座输出正确。
3. **外部金标（诚实边界）**：3D-FRONT（学术免费）/ SpatialLM-Dataset（CC-BY-NC-4.0）
   的完整基准需外部下载数据集，本脚本仅预留入口并如实标注，不伪装外部基准结果。

运行：`.venv/bin/python scripts/eval_spatial_semantics.py`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.spatial_semantics_service import (  # noqa: E402
    ROOM_TYPE_ALIASES,
    analyze_spatial_semantics,
    build_spatial_foundation,
)


def _check_ontology_alignment() -> list[str]:
    """检查空间语义 room 类型与本体 room_types 对齐。"""
    onto_path = (
        Path(__file__).resolve().parents[1]
        / "app" / "ontology" / "renovation_ontology.json"
    )
    onto = json.loads(onto_path.read_text(encoding="utf-8"))
    onto_room_types = set(onto.get("spatial", {}).get("room_types", {}).keys())
    missing = set(ROOM_TYPE_ALIASES.keys()) - onto_room_types
    return [f"空间语义含本体未定义的房间类型: {sorted(missing)}"] if missing else []


_SAMPLE_FLOORPLANS = [
    {
        "name": "两室一厅",
        "rooms": [
            {"name": "客厅", "type": "living_room", "area": 20, "x": 0, "y": 0, "w": 5, "h": 4},
            {"name": "主卧", "area": 12, "x": 5, "y": 0, "w": 4, "h": 3},
            {"name": "厨房", "area": 6, "x": 0, "y": 4, "w": 3, "h": 2},
            {"name": "卫生间", "area": 4, "x": 3, "y": 4, "w": 2, "h": 2},
        ],
    },
]


def _run_cases() -> tuple[int, int]:
    """对样例 floorplan 跑空间语义 + 空间底座，验证输出自洽。"""
    passed = 0
    failed = 0
    for fp in _SAMPLE_FLOORPLANS:
        sem = analyze_spatial_semantics(fp)
        foundation = build_spatial_foundation(fp)
        ok = (
            sem["room_count"] == len(fp["rooms"])
            and foundation["room_count"] == len(fp["rooms"])
        )
        if ok:
            passed += 1
            print(
                f"[PASS] {fp['name']}: rooms={sem['room_count']} "
                f"wet={sem['zones']['wet_zones']} adjacency={len(foundation['adjacency'])}"
            )
        else:
            failed += 1
            print(
                f"[FAIL] {fp['name']}: sem_rooms={sem['room_count']} "
                f"foundation_rooms={foundation['room_count']} expected={len(fp['rooms'])}"
            )
    return passed, failed


def main() -> int:
    print("== 空间语义金标评测 ==")
    align_issues = _check_ontology_alignment()
    if align_issues:
        for issue in align_issues:
            print(f"[FAIL] 本体对齐: {issue}")
        return 1
    print("[PASS] 本体对齐: 空间语义 room 类型 ⊆ 本体 room_types")

    passed, failed = _run_cases()
    print(f"== 用例: {passed} passed, {failed} failed ==")
    print(
        "[NOTE] 外部金标（3D-FRONT 学术免费 / SpatialLM-Dataset CC-BY-NC-4.0）"
        "需下载数据集后接入；本脚本仅做确定性本体对齐 + 样例自检，不伪装外部基准结果。"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
