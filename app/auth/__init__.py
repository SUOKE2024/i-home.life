import time
from collections import OrderedDict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.auth.paseto_handler import verify_token, TokenExpiredError, TokenInvalidError
from app.database import get_db
from app.models.user import User

security = HTTPBearer()

# ── 用户对象短 TTL 内存缓存（v1.1.12 性能优化） ──
# 避免每个认证请求都查 User 表；TTL 30s 平衡一致性与性能。
# 写操作（更新用户/禁用账户）应调用 invalidate_user_cache 清除缓存。
_USER_CACHE_TTL = 30  # 秒
_USER_CACHE_MAX = 512  # 最大缓存条目数
_user_cache: OrderedDict[str, tuple[float, User]] = OrderedDict()


def invalidate_user_cache(user_id: str | None = None) -> None:
    """清除用户缓存。不传 user_id 则清空整个缓存。
    在用户信息更新/禁用/登出时调用。
    """
    if user_id is None:
        _user_cache.clear()
    else:
        _user_cache.pop(user_id, None)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    # 性能优化（v1.1.12）：复用中间件已解析的 payload，避免 verify_token 重复调用
    payload = getattr(request.state, "paseto_payload", None)
    if payload is None:
        token = credentials.credentials
        try:
            payload = verify_token(token)
        except TokenExpiredError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="令牌已过期，请重新登录",
            )
        except TokenInvalidError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌",
            )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌格式无效",
        )

    # 命中缓存且未过期
    now = time.monotonic()
    cached = _user_cache.get(user_id)
    if cached is not None:
        exp_at, cached_user = cached
        if now < exp_at:
            # LRU：移动到末尾
            _user_cache.move_to_end(user_id)
            # 重新检查账户状态（缓存内对象可能被禁用）
            if not cached_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="账户已禁用",
                )
            return cached_user
        else:
            _user_cache.pop(user_id, None)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已禁用",
        )

    # 写入缓存（detached 防止 session 关闭后失效）
    db.expunge(user)
    _user_cache[user_id] = (now + _USER_CACHE_TTL, user)
    _user_cache.move_to_end(user_id)
    # LRU 淘汰
    while len(_user_cache) > _USER_CACHE_MAX:
        _user_cache.popitem(last=False)

    return user
