"""三智能体交叉验证运行器 — 顺序执行（避免共享库写冲突）并汇总。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agent_common import EVIDENCE_DIR
from agent_a_homeowner import AgentAHomeowner
from agent_b_supplier import AgentBSupplier
from agent_c_admin import AgentCAdmin


def main() -> int:
    agents = [AgentAHomeowner(), AgentBSupplier(), AgentCAdmin()]
    reports = []
    for agent in agents:
        agent.run()
        path = agent.save_evidence()
        reports.append(agent.summary())
        print(json.dumps(agent.summary(), ensure_ascii=False), flush=True)
        print(f"  证据: {path}", flush=True)

    # 汇总
    total = sum(r["steps"] for r in reports)
    passed = sum(r["passed"] for r in reports)
    failed = total - passed
    issues = []
    for row_path in sorted(EVIDENCE_DIR.glob("*_evidence.jsonl")):
        with row_path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("issue") and not str(row["issue"]).startswith("expected"):
                    issues.append({
                        "agent": row["agent"], "step": row["step"], "scenario": row["scenario"],
                        "path": row["path"], "status": row["status"], "issue": row["issue"],
                        "detail": row["detail"][:300],
                    })

    summary = {
        "total_steps": total, "passed": passed, "failed": failed,
        "issues": issues,
    }
    out = Path(__file__).parent / "run_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 汇总 ===")
    print(f"总步骤: {total}  通过: {passed}  失败: {failed}  发现问题: {len(issues)}")
    for i in issues:
        print(f"  [{i['issue']}] {i['agent']} {i['step']} -> {i['detail'][:120]}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
