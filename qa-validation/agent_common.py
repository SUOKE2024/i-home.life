"""智能体验证公共框架 — i-home.life 三智能体交叉验证

每个智能体 = 一个模拟真实用户角色的独立进程，通过真实 HTTP API 驱动业务链路，
将每一步操作（端点/载荷/响应/数据快照/结论）记录为证据 JSONL。
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# 目标环境：默认本地开发；生产验证设 IHOME_QA_BASE=https://i-home.life/api
# IHOME_QA_DELAY=请求间隔秒数（生产限流 60/min/IP，节流防 429）
BASE = os.environ.get("IHOME_QA_BASE", "http://127.0.0.1:8000/api")
REQUEST_DELAY = float(os.environ.get("IHOME_QA_DELAY", "0"))
EVIDENCE_DIR = Path(__file__).parent / "evidence"

ISSUE_COUNTER = {"n": 0}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class Agent:
    """模拟用户角色的验证智能体基类：登录 + 记录证据 + 一致性断言。"""

    name: str = "agent"
    role: str = "role"
    phone: str = ""
    password: str = "123456"
    habits: str = ""

    def __init__(self) -> None:
        self.token: str | None = None
        self.user_id: str | None = None
        self.evidence: list[dict] = []
        self.project_ids: list[str] = []
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # ── 基础设施 ──────────────────────────────────────────────
    def record(self, *, scenario: str, step: str, method: str, path: str,
               status: int | None, ok: bool, detail: str = "", issue: str | None = None,
               data: dict | None = None) -> None:
        self.evidence.append({
            "ts": now_iso(), "agent": self.name, "role": self.role, "phone": self.phone,
            "scenario": scenario, "step": step, "method": method, "path": path,
            "status": status, "ok": ok, "detail": detail, "issue": issue,
            "data": data or {},
        })

    def issue(self, code: str) -> str:
        ISSUE_COUNTER["n"] += 1
        return f"ISSUE-{ISSUE_COUNTER['n']:03d}({code})"

    def request(self, method: str, path: str, payload: dict | None = None,
                timeout: int = 90, auth: bool = True) -> tuple[int, dict | list | str]:
        """执行 HTTP 请求并返回 (status, body)。"""
        from urllib.parse import quote
        if REQUEST_DELAY:
            time.sleep(REQUEST_DELAY)
        # 路径中的非 ASCII（如中文查询参数）自动百分号编码
        url = BASE + quote(path, safe="/?:&=%")
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                try:
                    return resp.status, json.loads(raw)
                except json.JSONDecodeError:
                    return resp.status, raw[:2000]
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")
            try:
                return e.code, json.loads(raw)
            except json.JSONDecodeError:
                return e.code, raw[:2000]
        except Exception as e:  # noqa: BLE001
            return -1, f"NETWORK_ERROR: {e}"

    def api(self, *, scenario: str, step: str, method: str, path: str,
            payload: dict | None = None, expect: int = 200, check: callable | None = None,
            timeout: int = 90, auth: bool = True) -> tuple[bool, int, dict | list | str]:
        """请求 + 记录证据 + 期望校验，返回 (ok, status, body)。"""
        status, body = self.request(method, path, payload, timeout=timeout, auth=auth)
        ok = status == expect
        detail, issue = "", None
        if ok and check:
            try:
                check(body)
            except AssertionError as e:
                ok, issue = False, self.issue("FAILED_CHECK")
                detail = f"数据校验失败: {e}"
        elif not ok:
            detail = self._describe_err(status, body, expect)
            if status not in (400, 401, 403, 404, 409, 422) or status == expect:
                issue = self.issue("UNEXPECTED_STATUS")
            else:
                issue = "expected_rejection"
        self.record(scenario=scenario, step=step, method=method, path=path,
                    status=status, ok=ok, detail=detail or self._summarize(body),
                    issue=issue)
        return ok, status, body

    @staticmethod
    def _describe_err(status: int, body: dict | list | str, expect: int) -> str:
        if isinstance(body, dict) and body.get("detail"):
            return f"期望{expect} 实得{status} detail={body['detail']}"
        return f"期望{expect} 实得{status} body={str(body)[:200]}"

    @staticmethod
    def _summarize(body: dict | list | str) -> str:
        if isinstance(body, dict):
            keys = list(body.keys())[:8]
            return f"响应字段: {keys}"
        if isinstance(body, list):
            return f"响应列表 {len(body)} 项"
        return str(body)[:200]

    # ── 登录 ──────────────────────────────────────────────────
    def login(self) -> bool:
        status, body = self.request("POST", "/auth/login",
                                    {"phone": self.phone, "password": self.password}, timeout=30)
        ok = status == 200
        if ok:
            self.token = body["access_token"]
            self.user_id = body["user"]["id"]
        self.record(scenario="auth", step="登录", method="POST", path="/auth/login",
                    status=status, ok=ok,
                    detail=f"角色={self.role} 手机={self.phone} 用户={body.get('user', {}).get('name')}"
                    if ok else self._describe_err(status, body, 200),
                    issue=None if ok else self.issue("LOGIN_FAILED"))
        return ok

    # ── 证据输出 ──────────────────────────────────────────────
    def save_evidence(self) -> Path:
        out = EVIDENCE_DIR / f"{self.name}_evidence.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for row in self.evidence:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return out

    def summary(self) -> dict:
        total = len(self.evidence)
        ok = sum(1 for r in self.evidence if r["ok"])
        issues = [r for r in self.evidence if r["issue"] and not r["issue"].startswith("expected")]
        return {"agent": self.name, "role": self.role, "steps": total,
                "passed": ok, "failed": total - ok, "issues": [r["issue"] for r in issues]}
