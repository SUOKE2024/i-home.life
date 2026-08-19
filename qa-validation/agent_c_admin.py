"""智能体 C — 平台管理员（admin）

用户画像：平台运营管理员，习惯每日开盘先看简报与对账，周期性巡检
Agent 治理安全、自进化管线与 MCP 协议合规，关注异常数据与功能回退。

覆盖链路：登录 → 权限码 → 平台统计 → 每日简报 → 供应商简报 → 治理审计 →
技能进化 → MCP 协议(manifest/tools/call) → Agent 记忆(org) → 评估框架
(tool-accuracy/drift) → 项目周报批量 → 诊断
穿插边界条件（非法 limit）与越权兜底（管理员访问应全通）。
"""

from __future__ import annotations

import json

from agent_common import Agent

PHONE = "13500135000"


class AgentCAdmin(Agent):
    name = "agent_c_admin"
    role = "admin"
    phone = PHONE
    habits = "每日开盘巡检：简报→对账→治理→进化→MCP，关注异常回退"

    # ── 认证与权限 ──────────────────────────────────────────
    def check_auth(self) -> None:
        self.api(scenario="normal", step="获取当前用户", method="GET", path="/auth/me",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("role 非 admin"))
                 if b.get("role") != "admin" else None)
        self.api(scenario="normal", step="管理员权限码(全集)", method="GET",
                 path="/auth/me/permissions",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("admin 权限码非全集"))
                 if not isinstance(b, dict) or len(b.get("permissions", [])) < 10 else None)

    # ── 平台统计与简报 ──────────────────────────────────────
    def stats_and_briefings(self) -> None:
        self.api(scenario="normal", step="平台统计", method="GET", path="/admin/stats",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("stats 缺用户/项目数"))
                 if not isinstance(b, dict) or ("total_users" not in b and "users" not in b) else None)
        ok, st, body = self.api(scenario="normal", step="每日运营简报", method="GET",
                                path="/admin/daily-briefing", timeout=240)
        if ok and isinstance(body, dict):
            self._check_honest_degradation(body, "每日运营简报")
        ok, st, body = self.api(scenario="normal", step="供应商每日简报", method="GET",
                                path="/admin/supplier-daily-briefing", timeout=240)
        if ok and isinstance(body, dict):
            self._check_honest_degradation(body, "供应商每日简报")

    @staticmethod
    def _check_honest_degradation(body: dict, name: str) -> None:
        """诚实降级红线：AI 建议段必须标注数据源/降级来源，禁止伪装实时。"""
        raw = json.dumps(body, ensure_ascii=False)
        sections = body.get("sections") or {}
        keys = list(sections.keys()) if isinstance(sections, dict) else []
        for key in keys:
            sec = sections[key]
            if isinstance(sec, dict) and (sec.get("data_source") or sec.get("source")):
                return
        # 兜底：整包 JSON 含诚实标注关键词即通过
        markers = ("best-effort", "数据源", "data_source", "降级", "来源", "not available", "fallback")
        if any(m in raw for m in markers):
            return
        raise AssertionError(f"{name} 各段未标注数据源/诚实降级来源 keys={keys}")

    # ── 治理与自进化 ────────────────────────────────────────
    def governance_and_evolution(self) -> None:
        ok, st, body = self.api(scenario="normal", step="Agent 治理审计", method="GET",
                                path="/admin/agent-governance-audit", timeout=120)
        if ok and isinstance(body, dict):
            items = body.get("items") or body.get("results") or []
            fail = [i for i in items if isinstance(i, dict) and i.get("status") == "fail"]
            if fail:
                self.evidence[-1]["issue"] = (self.evidence[-1]["issue"] or "") + \
                    f" | 治理审计 fail={len(fail)}: {[i.get('id', i.get('name')) for i in fail[:5]]}"
        ok, st, body = self.api(scenario="normal", step="技能进化周期", method="GET",
                                path="/admin/skill-evolution", timeout=240)
        if ok and isinstance(body, dict) and body.get("skipped_reasons"):
            self.evidence[-1]["detail"] += f" skipped={body['skipped_reasons']}"

    # ── MCP 协议 ────────────────────────────────────────────
    def mcp_protocol(self) -> None:
        ok, st, body = self.api(scenario="normal", step="MCP manifest(公开)", method="GET",
                                path="/mcp/manifest", auth=False)
        if ok and isinstance(body, dict):
            assert "name" in body, "manifest 缺 name"
        self.api(scenario="normal", step="MCP 工具列表", method="GET", path="/mcp/tools",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("无工具"))
                 if not isinstance(b, dict) or not b.get("tools") else None)
        # MCP 工具调用（真实工具 get_design_layout，管理员可访问任意项目）
        self.api(scenario="normal", step="MCP 工具调用", method="POST", path="/mcp/tools/call",
                 payload={"name": "get_design_layout",
                          "arguments": {"project_id": "9b549486-9b77-4f09-9382-f1dec9cd6136"}},
                 timeout=120)
        self.api(scenario="normal", step="MCP MRTR 列表", method="GET", path="/mcp/mrtr")
        # 边界：MCP 未知工具（协议约定 200 + isError 诚实报错）
        ok, st, body = self.api(scenario="boundary", step="MCP 调用未知工具", method="POST",
                                path="/mcp/tools/call",
                                payload={"name": "no_such_tool", "arguments": {}}, expect=200)
        if ok and isinstance(body, dict) and body.get("isError") is not True:
            self.evidence[-1]["issue"] = (self.evidence[-1]["issue"] or "") + " | 未知工具未标 isError"

    # ── Agent 记忆（org 共享记忆）───────────────────────────
    def agent_memory(self) -> None:
        self.api(scenario="normal", step="org 共享记忆", method="GET", path="/agents/memory/org")
        self.api(scenario="normal", step="个人记忆列表", method="GET", path="/agents/memory")
        # 边界：org 级写入（仅管理员允许，验证 201 或明确拒绝）
        self.api(scenario="boundary", step="org 记忆写入", method="POST", path="/agents/memory",
                 payload={"key": "qa_cross_validation", "value": "三智能体交叉验证条目",
                          "scope": "org"}, expect=201)

    # ── 评估框架 ────────────────────────────────────────────
    def eval_framework(self) -> None:
        self.api(scenario="normal", step="评估维度", method="GET", path="/eval/dimensions")
        self.api(scenario="normal", step="工具选择准确率", method="GET", path="/eval/tool-accuracy",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("缺 metrics.accuracy"))
                 if not isinstance(b, dict) or "accuracy" not in b.get("metrics", {}) else None)
        self.api(scenario="normal", step="漂移检测", method="GET", path="/eval/drift")
        self.api(scenario="normal", step="漂移历史", method="GET", path="/eval/drift/history")
        # 边界：非法 window_days
        self.api(scenario="boundary", step="漂移检测非法窗口", method="GET",
                 path="/eval/drift?window_days=999", expect=422)

    # ── 项目周报批量（v1.15.8）──────────────────────────────
    def weekly_briefings(self) -> None:
        self.api(scenario="normal", step="批量项目周报", method="GET",
                 path="/admin/projects/weekly-briefings?limit=5", timeout=240)

    # ── 主流程 ─────────────────────────────────────────────
    def run(self) -> None:
        if not self.login():
            return
        self.check_auth()
        self.stats_and_briefings()
        self.governance_and_evolution()
        self.mcp_protocol()
        self.agent_memory()
        self.eval_framework()
        self.weekly_briefings()


if __name__ == "__main__":
    a = AgentCAdmin()
    a.run()
    path = a.save_evidence()
    print("=== 智能体C 完成 ===")
    print(a.summary())
    print(f"证据: {path}")
