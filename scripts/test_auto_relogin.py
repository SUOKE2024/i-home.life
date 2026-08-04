#!/usr/bin/env python3
"""测试辅助：PASETO token 自动重登录工具

用途：在 UI/E2E 测试过程中，token 周期性过期导致 401。本模块封装
"检测 token 有效性 → 过期则重新登录 → 持久化新 token"逻辑，避免手动干预。

复用方式：
  1. 作为模块 import：
       from scripts.test_auto_relogin import get_valid_token, AutoReloginClient
       token = get_valid_token()  # 自动用种子用户重登录
       client = AutoReloginClient()
       client.get("/api/appliances/categories")  # 401 时自动重试

  2. 作为 CLI（打印有效 token 供外部脚本使用）：
       python scripts/test_auto_relogin.py
       python scripts/test_auto_relogin.py --phone 13800138000 --password 123456
       python scripts/test_auto_relogin.py --verify /api/ecosystem/status

约束对齐：
  - PASETO v4.local（非 JWT），登录端点 POST /api/auth/login 需 {phone, password}
  - token 缓存到 /tmp/suoke_test_token.txt（不污染仓库）
  - 用 urllib 标准库，不引入 requests 依赖（对齐 e2e_test.py 风格）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 默认种子用户（对齐 scripts/seed.py:157）
DEFAULT_PHONE = os.environ.get("SUOKE_TEST_PHONE", "13800138000")
DEFAULT_PASSWORD = os.environ.get("SUOKE_TEST_PASSWORD", "123456")
DEFAULT_BASE_URL = os.environ.get("SUOKE_TEST_BASE_URL", "http://localhost:8000")

# token 持久化路径（/tmp 不入库，多进程共享）
TOKEN_CACHE_PATH = Path(os.environ.get("SUOKE_TEST_TOKEN_FILE", "/tmp/suoke_test_token.txt"))

# token 提前刷新阈值（秒）：距离过期不足此时长即主动重登录
TOKEN_REFRESH_MARGIN = 60


def _api(
    method: str,
    base_url: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    timeout: float = 30,
) -> tuple[int, dict]:
    """调用 API 端点，返回 (status_code, parsed_body)。

    对齐 e2e_test.py:api 的风格，但 base_url 可配置。
    """
    url = base_url + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.status == 204 or not raw.strip():
                return r.status, {}
            return r.status, json.loads(raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read()
        if e.code == 204 or not raw.strip():
            return e.code, {}
        try:
            return e.code, json.loads(raw.decode())
        except json.JSONDecodeError:
            return e.code, {"raw": raw.decode()[:500]}
    except Exception as ex:
        return 0, {"error": str(ex)}


def login(base_url: str = DEFAULT_BASE_URL, phone: str = DEFAULT_PHONE, password: str = DEFAULT_PASSWORD) -> str:
    """登录并返回 access_token。

    POST /api/auth/login {phone, password} → {access_token, token_type}
    """
    status, body = _api("POST", base_url, "/api/auth/login", body={"phone": phone, "password": password})
    if status != 200:
        raise RuntimeError(f"登录失败: HTTP {status} {body}")
    token = body.get("access_token", "")
    if not token or not token.startswith("v4.local."):
        raise RuntimeError(f"登录返回 token 异常: {token[:40]}...")
    return token


def is_token_valid(base_url: str, token: str) -> bool:
    """检查 token 是否有效：GET /api/auth/me 返回 200 即有效。"""
    if not token:
        return False
    status, _ = _api("GET", base_url, "/api/auth/me", token=token, timeout=10)
    return status == 200


def get_valid_token(
    base_url: str = DEFAULT_BASE_URL,
    phone: str = DEFAULT_PHONE,
    password: str = DEFAULT_PASSWORD,
    cache_path: Path = TOKEN_CACHE_PATH,
    force_relogin: bool = False,
) -> str:
    """获取有效 token：优先读缓存，无效则重新登录。

    force_relogin=True 时强制重新登录（用于 token 即将过期或怀疑失效场景）。
    """
    # 1. 读缓存
    if not force_relogin and cache_path.exists():
        cached = cache_path.read_text(encoding="utf-8").strip()
        if cached.startswith("v4.local.") and is_token_valid(base_url, cached):
            return cached
        # 缓存失效，删除
        try:
            cache_path.unlink()
        except OSError:
            pass

    # 2. 重新登录
    token = login(base_url, phone, password)

    # 3. 持久化
    try:
        cache_path.write_text(token, encoding="utf-8")
        cache_path.chmod(0o600)  # 仅当前用户可读写
    except OSError:
        pass  # /tmp 不可写时不影响主流程

    return token


class AutoReloginClient:
    """带 401 自动重登录的 API 客户端。

    用法：
        client = AutoReloginClient()
        status, body = client.get("/api/appliances/categories")
        # 若遇 401，自动重新登录并重试一次

    特性：
        - token 缓存到文件，多进程/多脚本共享
        - 401 自动重试（仅重试一次，避免死循环）
        - 提供 get/post/put/delete 便捷方法
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        phone: str = DEFAULT_PHONE,
        password: str = DEFAULT_PASSWORD,
        cache_path: Path = TOKEN_CACHE_PATH,
    ):
        self.base_url = base_url
        self.phone = phone
        self.password = password
        self.cache_path = cache_path
        self._token: str | None = None

    @property
    def token(self) -> str:
        """惰性获取有效 token。"""
        if self._token is None:
            self._token = get_valid_token(self.base_url, self.phone, self.password, self.cache_path)
        return self._token

    def _request(self, method: str, path: str, body: dict | None = None, timeout: float = 30) -> tuple[int, dict]:
        """发起请求，401 时自动重登录并重试一次。"""
        status, resp = _api(method, self.base_url, path, body=body, token=self.token, timeout=timeout)

        if status == 401:
            # token 过期，强制重登录
            self._token = get_valid_token(
                self.base_url, self.phone, self.password, self.cache_path, force_relogin=True
            )
            # 重试一次
            status, resp = _api(method, self.base_url, path, body=body, token=self.token, timeout=timeout)

        return status, resp

    def get(self, path: str, timeout: float = 30) -> tuple[int, dict]:
        return self._request("GET", path, timeout=timeout)

    def post(self, path: str, body: dict | None = None, timeout: float = 30) -> tuple[int, dict]:
        return self._request("POST", path, body=body, timeout=timeout)

    def put(self, path: str, body: dict | None = None, timeout: float = 30) -> tuple[int, dict]:
        return self._request("PUT", path, body=body, timeout=timeout)

    def delete(self, path: str, timeout: float = 30) -> tuple[int, dict]:
        return self._request("DELETE", path, timeout=timeout)

    def upload_file(
        self, path: str, file_path: str, field_name: str = "file", extra_fields: dict | None = None, timeout: float = 60
    ) -> tuple[int, dict]:
        """multipart 文件上传，同样支持 401 自动重登录。"""
        boundary = f"----SuokeBoundary{int(time.time() * 1000)}"

        def _build_multipart(fp: str, fields: dict | None) -> bytes:
            lines = []
            if fields:
                for k, v in fields.items():
                    lines.append(f"--{boundary}".encode())
                    lines.append(f'Content-Disposition: form-data; name="{k}"'.encode())
                    lines.append(b"")
                    lines.append(str(v).encode())
            with open(fp, "rb") as f:
                file_bytes = f.read()
            filename = os.path.basename(fp)
            lines.append(f"--{boundary}".encode())
            lines.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode())
            lines.append(b"Content-Type: application/octet-stream")
            lines.append(b"")
            lines.append(file_bytes)
            lines.append(f"--{boundary}--".encode())
            lines.append(b"")
            return b"\r\n".join(lines)

        def _do_upload(token: str) -> tuple[int, dict]:
            data = _build_multipart(file_path, extra_fields)
            req = urllib.request.Request(self.base_url + path, data=data, method="POST")
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            if token:
                req.add_header("Authorization", f"Bearer {token}")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()
                    return r.status, json.loads(raw.decode()) if raw.strip() else {}
            except urllib.error.HTTPError as e:
                raw = e.read()
                try:
                    return e.code, json.loads(raw.decode()) if raw.strip() else {}
                except json.JSONDecodeError:
                    return e.code, {"raw": raw.decode()[:500]}
            except Exception as ex:
                return 0, {"error": str(ex)}

        status, resp = _do_upload(self.token)
        if status == 401:
            self._token = get_valid_token(
                self.base_url, self.phone, self.password, self.cache_path, force_relogin=True
            )
            status, resp = _do_upload(self.token)
        return status, resp


def _cli() -> int:
    parser = argparse.ArgumentParser(description="索克家居 PASETO token 自动重登录工具")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"后端地址（默认 {DEFAULT_BASE_URL}）")
    parser.add_argument("--phone", default=DEFAULT_PHONE, help=f"手机号（默认 {DEFAULT_PHONE}）")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="密码（默认 123456）")
    parser.add_argument("--force", action="store_true", help="强制重新登录，忽略缓存")
    parser.add_argument("--verify", metavar="PATH", help="验证指定端点（如 /api/ecosystem/status），打印响应摘要")
    args = parser.parse_args()

    try:
        token = get_valid_token(args.base_url, args.phone, args.password, force_relogin=args.force)
    except Exception as e:
        print(f"[FAIL] 获取 token 失败: {e}", file=sys.stderr)
        return 1

    # 验证 token
    status, body = _api("GET", args.base_url, "/api/auth/me", token=token)
    if status != 200:
        print(f"[FAIL] token 无效（/api/auth/me 返回 {status}）: {body}", file=sys.stderr)
        return 1

    print(f"[OK] token 有效（长度 {len(token)}）")
    print(f"token: {token}")

    if args.verify:
        path = args.verify if args.verify.startswith("/api") else f"/api/{args.verify}"
        status, body = _api("GET", args.base_url, path, token=token)
        if status == 200:
            preview = json.dumps(body, ensure_ascii=False)
            if len(preview) > 400:
                preview = preview[:400] + "..."
            print(f"\n[OK] GET {path} → 200")
            print(f"响应: {preview}")
        else:
            print(f"\n[FAIL] GET {path} → {status}: {body}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(_cli())
