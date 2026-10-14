"""阿里云 FC 定时器函数：按环境变量 TARGET_URLS 依次 GET i-home 管理端点。

IaC 描述见同目录 `s.yaml`。触发器为 FC 定时触发器（cron ``0 0 8 * * *`` Asia/Shanghai），
与被驱动的三个平台管理端点：
- ``/api/admin/daily-briefing``
- ``/api/admin/skill-evolution``
- ``/api/admin/supplier-daily-briefing``

用途：把此前**仅存在于阿里云控制台**的定时器配置（见 CLAUDE.md「FC 运维须知」）
收敛为仓库内可复现的 IaC。本函数与线上既有函数行为等价；**首次采用前请与既有控制台
函数核对**（region/access/runtime/handler/base URL）。

鉴权：环境变量 ``API_TOKEN`` 为手工签发的静态 PASETO v4.public admin 令牌，
由 ``scripts/mint_paseto_token.py`` 以生产 ``PASETO_PRIVATE_KEY`` 签发；
到期当天三个定时任务会静默 401，届时须重签并更新本函数环境变量。
"""

from __future__ import annotations

import os
import urllib.request


def handler(event, context):  # noqa: ARG001 - FC 约定签名
    base = os.getenv("IHOME_BASE_URL", "https://api.ihome.life").rstrip("/")
    token = os.getenv("API_TOKEN", "")
    targets = [u.strip() for u in os.getenv("TARGET_URLS", "").split(",") if u.strip()]

    results = []
    for target in targets:
        url = target if target.startswith("http") else base + "/" + target.lstrip("/")
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                results.append({"url": url, "status": resp.status})
        except Exception as e:  # noqa: BLE001 - 定时任务须如实回报每个目标失败
            results.append({"url": url, "error": str(e)})

    ok = all("error" not in r for r in results)
    return {"ok": ok, "results": results}
