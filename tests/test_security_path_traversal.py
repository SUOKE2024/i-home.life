"""路径遍历专项安全测试

验证 FastAPI + StaticFiles + 文件下载端点对路径遍历（../）攻击的防护：
- GET /api/files/download/<traversal> — 文件下载端点（DB 主键查找，非文件系统）
- POST /api/files/upload — 文件名包含 ../../malicious.txt（文件名仅存 DB，非文件系统）
- GET /<traversal>/etc/passwd — 静态文件挂载点路径遍历

防护机制说明：
- 项目使用 SQLAlchemy 存储 FileAttachment.file_data（BLOB），不读写文件系统。
  下载端点通过 attachment_id 主键查询，traversal 字符串不会匹配任何记录 → 404。
- StaticFiles（Starlette）会规范化 URL 路径并拒绝 `..` 跨目录访问 → 404 或 400。
- 文件名仅作为 metadata 存储于 DB，不参与文件系统路径拼接。

每项测试验证：
1. 响应状态码为 404 或 400（非 200、非 500）
2. 响应体不包含 /etc/passwd 内容特征（root:x:0:0 等）
"""

import uuid

import pytest
from httpx import AsyncClient


# ── 系统文件特征（用于验证未泄露文件内容）──────────────────────
_SYSTEM_FILE_MARKERS = (
    "root:x:0:0",          # /etc/passwd
    "daemon:x:1:1",         # /etc/passwd
    "[boot loader]",        # boot.ini (Windows)
    "[fonts]",              # win.ini
    "127.0.0.1\tlocalhost",  # /etc/hosts
    "sshd_config",          # /etc/ssh/sshd_config
)


def _assert_no_system_file_leak(response_body: bytes | str, context: str) -> None:
    """断言响应体不包含系统文件内容特征。"""
    if isinstance(response_body, bytes):
        try:
            body_str = response_body.decode("utf-8", errors="replace")
        except Exception:
            body_str = repr(response_body)
    else:
        body_str = response_body
    body_lower = body_str.lower()
    for marker in _SYSTEM_FILE_MARKERS:
        assert marker.lower() not in body_lower, (
            f"[{context}] 响应体疑似泄露系统文件内容（包含 {marker!r}）"
        )


async def _register_and_login(
    client: AsyncClient, phone: str, name: str = "路径遍历测试用户"
) -> tuple[str, dict]:
    """注册一个用户并返回 (token, headers)。"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code == 201, f"注册失败: {resp.text}"
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "路径遍历项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, f"创建项目失败: {resp.text}"
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════════
# 路径遍历防护测试
# ════════════════════════════════════════════════════════════════


class TestPathTraversalProtection:
    """路径遍历防护专项测试 — 验证 ../ 序列无法读取任意文件。"""

    # ── a. 文件下载端点路径遍历 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_file_download_path_traversal(self, client: AsyncClient):
        """GET /api/files/download/<traversal> — 文件下载端点路径遍历。

        /api/files/download/{attachment_id} 通过 DB 主键查找，
        traversal 字符串不会匹配任何 attachment 记录，应返回 404。
        """
        _, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        # 多种 traversal 向量：原始 + URL 编码（绕过客户端规范化）
        traversal_vectors = [
            "../../etc/passwd",
            "..%2F..%2Fetc%2Fpasswd",          # URL-encoded /
            "..%2F..%2F..%2Fetc%2Fpasswd",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # 全编码
            "..\\..\\windows\\win.ini",         # Windows 路径
            "%2e%2e%5c%2e%2e%5cwindows%5cwin.ini",
            "....//....//etc/passwd",           # 双点绕过尝试
            "..%252f..%252fetc%252fpasswd",     # 双重编码
        ]

        for vector in traversal_vectors:
            # 直接作为 attachment_id（httpx 会保留 URL 编码字符串作为路径段）
            resp = await client.get(
                f"/api/files/download/{vector}",
                headers=headers,
            )
            # 关键断言：不应返回 200（成功下载系统文件）或 500（服务异常）
            assert resp.status_code != 200, (
                f"路径遍历成功下载文件（严重）: vector={vector!r}, "
                f"status={resp.status_code}"
            )
            assert resp.status_code != 500, (
                f"路径遍历导致 500: vector={vector!r}, resp={resp.text[:300]!r}"
            )
            # 应为 401（未认证）、404（未找到）或 422（参数校验失败）—— 均合法
            assert resp.status_code in (401, 404, 422), (
                f"路径遍历响应码异常: vector={vector!r}, status={resp.status_code}, "
                f"resp={resp.text[:300]!r}"
            )
            _assert_no_system_file_leak(resp.content, f"file download {vector!r}")

    # ── b. 文件上传文件名路径遍历 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_file_upload_path_traversal(self, client: AsyncClient):
        """POST /api/files/upload — 文件名包含 ../../../malicious.txt。

        项目将文件内容存入 DB（BLOB），文件名仅作为 metadata 存储，
        不参与文件系统路径拼接，因此 traversal 文件名不会造成任意文件写入。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")
        project_id = await _create_project(client, headers, "上传遍历测试")

        # 多种恶意文件名
        malicious_filenames = [
            "../../../malicious.txt",
            "..\\..\\..\\malicious.txt",
            "../../../../etc/passwd",
            "..%2F..%2F..%2Fmalicious.txt",
            "....//....//malicious.txt",
            "../../etc/cron.d/exploit",
        ]

        for filename in malicious_filenames:
            resp = await client.post(
                "/api/files/upload",
                data={
                    "project_id": project_id,
                    "category": "other",
                },
                files={
                    "file": (filename, b"malicious content", "text/plain"),
                },
                headers=headers,
            )
            # 关键：不应返回 500（服务异常）
            assert resp.status_code != 500, (
                f"恶意文件名导致 500: filename={filename!r}, resp={resp.text[:300]!r}"
            )
            # 文件名仅存 DB，端点应正常返回 201（或 400 如有文件名校验）
            assert resp.status_code in (201, 400), (
                f"上传响应码异常: filename={filename!r}, status={resp.status_code}, "
                f"resp={resp.text[:300]!r}"
            )
            _assert_no_system_file_leak(resp.text, f"file upload {filename!r}")

            # 如果上传成功（201），验证下载返回的是上传内容（非系统文件）
            if resp.status_code == 201:
                attachment_id = resp.json()["id"]
                dl_resp = await client.get(
                    f"/api/files/download/{attachment_id}",
                    headers=headers,
                )
                assert dl_resp.status_code == 200, (
                    f"下载刚上传的文件失败: id={attachment_id}, "
                    f"status={dl_resp.status_code}"
                )
                # 下载内容应是上传的恶意字符串，不是系统文件
                assert dl_resp.content == b"malicious content", (
                    f"下载内容与上传内容不一致（疑似路径遍历）: "
                    f"got={dl_resp.content[:100]!r}"
                )
                _assert_no_system_file_leak(
                    dl_resp.content, f"file download after upload {filename!r}"
                )

    # ── c. 静态文件挂载点路径遍历 ──────────────────────────────

    @pytest.mark.asyncio
    async def test_static_file_path_traversal(self, client: AsyncClient):
        """GET /<traversal>/etc/passwd — 静态文件挂载点路径遍历。

        Starlette StaticFiles 会规范化 URL 路径并拒绝 `..` 跨目录访问。
        """
        traversal_vectors = [
            "/../../etc/passwd",
            "/../../../etc/passwd",
            "/..%2F..%2Fetc%2Fpasswd",
            "/%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "/..%5C..%5Cetc%5Cpasswd",                # Windows 反斜杠编码
            "/....//....//etc/passwd",
            "/..%252f..%252fetc%252fpasswd",            # 双重编码
            "/static/../../etc/passwd",
        ]

        for vector in traversal_vectors:
            resp = await client.get(vector, follow_redirects=False)
            # 关键：不应返回 200（成功读取系统文件）或 500（服务异常）
            assert resp.status_code != 200, (
                f"静态文件路径遍历成功（严重）: vector={vector!r}, "
                f"status={resp.status_code}"
            )
            assert resp.status_code != 500, (
                f"静态文件路径遍历导致 500: vector={vector!r}"
            )
            # 应为 404（未找到）或 400（拒绝路径）—— 均合法
            assert resp.status_code in (400, 404), (
                f"静态文件路径遍历响应码异常: vector={vector!r}, "
                f"status={resp.status_code}, resp={resp.text[:300]!r}"
            )
            _assert_no_system_file_leak(resp.content, f"static file {vector!r}")
