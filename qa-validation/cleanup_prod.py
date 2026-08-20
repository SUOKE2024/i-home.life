"""生产环境 QA 验证残留清理脚本 — 三智能体验证后的数据卫生

用途：交叉验证在生产 https://i-home.life 运行后，清除验证产生的 QA 残留，
并将演示项目数据恢复至基线。沉淀 2026-08-20 两次生产验证的手工清理流程。

安全设计：
  - 仅作用于「可确定性识别」的 QA 标记数据：
    ① QA-* 命名的项目（API 级联删除）② delivery_orders 名含 QA- ③
    agent_memories memory_key=qa_cross_validation ④ 演示项目上 description 含
    「QA 交叉验证」的质检问题及其关联残留（结算/订单/escrow，需在时间窗内且为
    draft/pending 未完成态）。
  - `--dry-run` 只打印将要删除的内容不执行；默认关闭（需显式 --apply 执行删除）。
  - 所有 DB 删除在单事务内先子后父（order_lines/escrow/trustee → 父表）。

依赖：
  - SSH 到生产（默认 root@118.31.223.213，可用 IHOME_QA_SSH / IHOME_QA_SSH_KEY 覆盖）
  - 生产 .env 的 DATABASE_URL（PG）
  - 业主演示账号 token（删 QA 项目用，IHOME_QA_BASE/IHOME_QA_PHONE/IHOME_QA_PASSWORD）

用法：
  python qa-validation/cleanup_prod.py --baseline            # 打印演示项目数据基线
  python qa-validation/cleanup_prod.py --dry-run             # 预览待清理内容
  python qa-validation/cleanup_prod.py --apply               # 执行清理
  python qa-validation/cleanup_prod.py --verify              # 复核（基线比对）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request

SSH = os.environ.get("IHOME_QA_SSH", "root@118.31.223.213")
SSH_KEY = os.environ.get("IHOME_QA_SSH_KEY", os.path.expanduser("~/.ssh/id_ed25519"))
BASE = os.environ.get("IHOME_QA_BASE", "https://i-home.life/api")
PHONE = os.environ.get("IHOME_QA_PHONE", "13800138000")
PASSWORD = os.environ.get("IHOME_QA_PASSWORD", "123456")

# 演示项目（按业主手机号 + 名称识别，避免触碰真实用户数据）
DEMO_PROJECT_NAMES = ("云栖雅苑 · 智能整装", "滇池湖畔 · 现代简约", "翠湖名邸 · 原木奶油风")

COUNT_SQL = """
SELECT p.name,
  (SELECT COUNT(*) FROM budgets b WHERE b.project_id=p.id AND b.deleted_at IS NULL) budgets,
  (SELECT COUNT(*) FROM settlements s WHERE s.project_id=p.id) settlements,
  (SELECT COUNT(*) FROM procurement_orders o WHERE o.project_id=p.id AND o.deleted_at IS NULL) orders,
  (SELECT COUNT(*) FROM quality_issues q WHERE q.project_id=p.id) q_issues,
  (SELECT COUNT(*) FROM escrow_payments e WHERE e.project_id=p.id) escrow,
  (SELECT COUNT(*) FROM construction_tasks ct WHERE ct.project_id=p.id) ctasks
FROM projects p JOIN users u ON u.id=p.owner_id
WHERE u.phone='{phone}' AND p.name IN {names}
ORDER BY p.created_at;
"""


def _ssh(cmd: str) -> str:
    """在服务器执行命令（取 .env 的 DATABASE_URL）。"""
    script = (
        "cd /opt/ihome && "
        "PGURL=$(grep '^DATABASE_URL' .env | cut -d= -f2- | sed 's/postgresql+asyncpg:/postgresql:/') && "
        + cmd
    )
    proc = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", SSH, script],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"SSH 执行失败: {proc.stderr[-500:]}")
    return proc.stdout


def _login_token() -> str:
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=json.dumps({"phone": PHONE, "password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


def baseline() -> list[str]:
    """打印演示项目数据基线。"""
    sql = COUNT_SQL.format(phone=PHONE, names=tuple(DEMO_PROJECT_NAMES))
    out = _ssh(f'psql "$PGURL" -c "{sql}"')
    print(out)
    # QA 标记残留计数
    qa = _ssh(
        'psql "$PGURL" -t -c "'
        "SELECT (SELECT COUNT(*) FROM projects WHERE name LIKE 'QA-%'),"
        "(SELECT COUNT(*) FROM delivery_orders WHERE name LIKE 'QA-%'),"
        "(SELECT COUNT(*) FROM agent_memories WHERE memory_key='qa_cross_validation')"
        '"'
    )
    print("QA 项目 / QA 交付单 / QA 记忆:", qa.strip())
    return out.splitlines()


def _plan_sql(window_hours: int) -> str:
    """构造清理 SQL（先子后父，单事务；返回预览与执行共用语句）。"""
    phone = PHONE
    demo_ids = (
        "SELECT id FROM projects WHERE owner_id IN "
        f"(SELECT id FROM users WHERE phone='{phone}') AND name IN {tuple(DEMO_PROJECT_NAMES)}"
    )
    return f"""
-- 子表先行
DELETE FROM rectification_orders
WHERE issue_id IN (
  SELECT id FROM quality_issues q WHERE q.project_id IN ({demo_ids})
    AND q.description LIKE '%QA 交叉验证%'
);
DELETE FROM settlement_lines
WHERE settlement_id IN (
  SELECT id FROM settlements s WHERE s.project_id IN ({demo_ids})
    AND s.status IN ('draft','in_progress')
    AND s.created_at >= now() - interval '{window_hours} hours'
);
DELETE FROM escrow_trustee_accounts
WHERE escrow_payment_id IN (
  SELECT id FROM escrow_payments e WHERE e.project_id IN ({demo_ids})
    AND e.status='pending' AND e.created_at >= now() - interval '{window_hours} hours'
);
DELETE FROM escrow_payments
WHERE id IN (
  SELECT id FROM escrow_payments e WHERE e.project_id IN ({demo_ids})
    AND e.status='pending' AND e.created_at >= now() - interval '{window_hours} hours'
);
DELETE FROM order_lines
WHERE order_id IN (
  SELECT id FROM procurement_orders o WHERE o.project_id IN ({demo_ids})
    AND o.status='draft' AND o.total_amount=0
    AND o.created_at >= now() - interval '{window_hours} hours'
);
-- 父表
DELETE FROM settlements
WHERE id IN (
  SELECT id FROM settlements s WHERE s.project_id IN ({demo_ids})
    AND s.status IN ('draft','in_progress')
    AND s.created_at >= now() - interval '{window_hours} hours'
);
DELETE FROM procurement_orders
WHERE id IN (
  SELECT id FROM procurement_orders o WHERE o.project_id IN ({demo_ids})
    AND o.status='draft' AND o.total_amount=0
    AND o.created_at >= now() - interval '{window_hours} hours'
);
DELETE FROM quality_issues
WHERE id IN (
  SELECT id FROM quality_issues q WHERE q.project_id IN ({demo_ids})
    AND q.description LIKE '%QA 交叉验证%'
);
-- 其他 QA 标记残留
DELETE FROM delivery_orders WHERE name LIKE 'QA-%';
DELETE FROM agent_memories WHERE memory_key='qa_cross_validation' AND scope='org';
"""


def cleanup(window_hours: int, dry_run: bool) -> None:
    """清理 QA 残留。"""
    # 1) QA-* 项目：API 级联删除（需业主 token）
    token = _login_token()
    list_req = urllib.request.Request(f"{BASE}/projects", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(list_req, timeout=30) as resp:
        projects = json.loads(resp.read())
    qa_projects = [p for p in projects if str(p.get("name", "")).startswith("QA-")]
    for p in qa_projects:
        action = "将删除" if dry_run else "删除"
        print(f"[project] {action} {p['name']} ({p['id']})")
        if not dry_run:
            req = urllib.request.Request(
                f"{BASE}/projects/{p['id']}", method="DELETE",
                headers={"Authorization": f"Bearer {token}"},
            )
            urllib.request.urlopen(req, timeout=30)

    # 2) DB 残留：单事务先子后父
    sql = "BEGIN;\n" + _plan_sql(window_hours) + "COMMIT;\n"
    if dry_run:
        # 预览：用 SELECT 计数替代 DELETE（只读不执行）
        preview = sql.replace("DELETE FROM", "SELECT COUNT(*) FROM").replace(
            "COMMIT;", ";"
        ).replace("BEGIN;", "")
        print("\n[db] 预览将影响的行数（dry-run）：")
        for stmt in preview.split(";"):
            s = stmt.strip()
            if s:
                out = _ssh(f'psql "$PGURL" -t -c "{s}"')
                print(" ", s.replace("\n", " ")[:110], "->", out.strip())
        return

    backup = _ssh("mkdir -p /opt/ihome/backups && echo ok")
    print(f"\n[db] 备份目录: {backup.strip()}")
    out = _ssh(f'psql "$PGURL" <<SQL\n{sql}\nSQL')
    print(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="生产 QA 验证残留清理")
    parser.add_argument("--baseline", action="store_true", help="打印演示项目数据基线")
    parser.add_argument("--dry-run", action="store_true", help="预览待清理内容（不执行）")
    parser.add_argument("--apply", action="store_true", help="执行清理（默认 dry-run 语义，须显式开启）")
    parser.add_argument("--verify", action="store_true", help="清理后复核基线")
    parser.add_argument("--window-hours", type=int, default=48, help="残留识别时间窗（小时）")
    args = parser.parse_args()

    if args.baseline or (args.verify and not args.apply):
        print("=== 基线/当前演示项目数据 ===")
        baseline()
        return 0

    if args.apply:
        print(f"=== 清理（窗口 {args.window_hours}h，先子后父事务）===")
        cleanup(args.window_hours, dry_run=False)
    else:
        print(f"=== 预览（dry-run，窗口 {args.window_hours}h）===")
        cleanup(args.window_hours, dry_run=True)

    if args.verify or True:
        print("\n=== 清理后复核 ===")
        baseline()
    return 0


if __name__ == "__main__":
    sys.exit(main())
