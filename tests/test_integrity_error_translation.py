"""IntegrityError 语义化转译（v1.17.4）

背景：v1.17.4 生产库补齐 166 条 CHECK 约束后，受限枚举越界值由 DB 拒绝（此前无约束
可写库）。但 API 层未转译 IntegrityError，客户端只看到「服务器内部错误」（500）——
约束虽已生效，提示却不可操作。

本层只转译**可归因于请求数据**的约束违反（CHECK/NOT NULL/FK → 422，UNIQUE → 409）；
未识别者保持 500 兜底，避免把内部缺陷伪装成用户输入错误。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.main import classify_integrity_error, integrity_error_handler

# ── 消息解析（PG asyncpg 与 SQLite 文案不同，均须识别）──

_PG_CHECK = (
    'new row for relation "smart_home_schemes" violates check constraint '
    '"chk_smart_home_scheme_room_type"'
)
_SQLITE_CHECK = "CHECK constraint failed: chk_smart_home_scheme_room_type"
_PG_UNIQUE = 'duplicate key value violates unique constraint "ix_users_phone"'
_SQLITE_UNIQUE = "UNIQUE constraint failed: users.phone"
_PG_FK = 'insert or update on table "bom_items" violates foreign key constraint "bom_items_material_id_fkey"'
_SQLITE_FK = "FOREIGN KEY constraint failed"
_PG_NOT_NULL = 'null value in column "room_name" of relation "smart_home_schemes" violates not-null constraint'
_SQLITE_NOT_NULL = "NOT NULL constraint failed: smart_home_schemes.room_name"


def _make_error(message: str) -> IntegrityError:
    """构造带指定底层消息的 IntegrityError（orig 决定 str(exc) 的内容）。"""
    return IntegrityError("INSERT INTO t VALUES (1)", {}, Exception(message))


@pytest.mark.parametrize(
    "message,expected",
    [
        (_PG_CHECK, ("check", "chk_smart_home_scheme_room_type")),
        (_SQLITE_CHECK, ("check", "chk_smart_home_scheme_room_type")),
        (_PG_UNIQUE, ("unique", "ix_users_phone")),
        (_SQLITE_UNIQUE, ("unique", "users.phone")),
        (_PG_FK, ("foreign_key", "bom_items_material_id_fkey")),
        (_SQLITE_FK, ("foreign_key", "")),
        (_PG_NOT_NULL, ("not_null", "room_name")),
        (_SQLITE_NOT_NULL, ("not_null", "smart_home_schemes.room_name")),
    ],
)
def test_classify_recognizes_both_dialects(message: str, expected: tuple):
    """PG 与 SQLite 的约束违反文案均能归因（不依赖方言专属异常类）。"""
    assert classify_integrity_error(_make_error(message)) == expected


def test_classify_returns_none_for_unknown_message():
    """无法归因的消息返回 None → 交由 500 兜底，不伪装成用户输入错误。"""
    assert classify_integrity_error(_make_error("connection reset by peer")) is None


@pytest.mark.parametrize(
    "message,expected_status,expected_fragment",
    [
        (_PG_CHECK, 422, "字段取值不在允许范围内"),
        (_SQLITE_CHECK, 422, "chk_smart_home_scheme_room_type"),
        (_PG_UNIQUE, 409, "记录已存在"),
        (_PG_FK, 422, "引用的关联记录不存在"),
        (_PG_NOT_NULL, 422, "缺少必填字段"),
    ],
)
async def test_handler_maps_status_and_detail(
    message: str, expected_status: int, expected_fragment: str,
):
    """handler 返回语义化状态码，且 detail 含可定位的约束名/列名。"""
    from starlette.requests import Request

    scope = {"type": "http", "method": "POST", "path": "/api/smart-home/schemes", "headers": []}
    response = await integrity_error_handler(Request(scope), _make_error(message))
    assert response.status_code == expected_status
    body = response.body.decode()
    assert expected_fragment in body
    assert '"error":true' in body.replace(" ", "")


async def test_handler_keeps_500_for_unclassified():
    """未识别的约束违反保持 500（不掩盖真实缺陷）。"""
    from starlette.requests import Request

    scope = {"type": "http", "method": "POST", "path": "/api/x", "headers": []}
    response = await integrity_error_handler(Request(scope), _make_error("disk full"))
    assert response.status_code == 500
    assert "服务器内部错误" in response.body.decode()


# ── 端到端：受限枚举越界写入经真实端点被拒且可读 ──


async def test_out_of_range_room_type_returns_422_not_500(
    client: AsyncClient, auth_headers: dict,
):
    """room_type 越界（模型允许集外）→ 422 语义化提示，而非 500 内部错误。"""
    project = await client.post(
        "/api/projects", json={"name": "约束转译项目", "total_area": 88.0}, headers=auth_headers,
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    resp = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "阳台", "room_type": "balcony"},
        headers=auth_headers,
    )
    assert resp.status_code == 422, f"应返回 422（取值越界），实际: {resp.status_code} {resp.text}"
    detail = resp.json()["detail"]
    assert isinstance(detail, str), "detail 须为字符串（前端 extractErrorMessage 已兼容）"
    assert "字段取值不在允许范围内" in detail

    # 合法值仍可写入（约束未误伤）
    ok = await client.post(
        "/api/smart-home/schemes",
        json={"project_id": project_id, "room_name": "玄关", "room_type": "entrance"},
        headers=auth_headers,
    )
    assert ok.status_code == 201, ok.text
