"""推送发送服务 — 多通道推送（FCM/APNs/WebPush/短信）

为施工健康 OS 及其他业务场景提供统一的推送发送接口。
当前实现为 mock 模式（开发环境），生产环境需接入真实推送通道。

支持的推送通道：
1. FCM (Firebase Cloud Messaging) — Android
2. APNs (Apple Push Notification Service) — iOS
3. WebPush (Web Push API) — 浏览器
4. SMS — 紧急通知短信通道

受 settings.health_os_enabled + settings.push_enabled feature flag 控制。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class PushChannel(str):
    """推送通道常量"""
    FCM = "fcm"
    APNS = "apns"
    WEB = "web"
    SMS = "sms"
    MOCK = "mock"


async def send_push_to_user(
    db,
    user_id: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """向指定用户的所有已激活设备发送推送通知。

    Args:
        db: 异步数据库会话
        user_id: 目标用户 ID
        title: 通知标题
        body: 通知正文
        data: 附加数据（JSON payload）
        channel: 指定通道（None 则全通道发送）

    Returns:
        {"sent": int, "failed": int, "tokens": [...]}
    """
    if not settings.push_enabled:
        logger.debug("push_sender: push_enabled=False，跳过推送")
        return {"sent": 0, "failed": 0, "reason": "disabled"}

    try:
        from app.services.notification_service import get_user_tokens
        tokens = await get_user_tokens(db, user_id)
    except Exception as e:
        logger.warning("push_sender: 获取设备令牌失败: %s", e)
        return {"sent": 0, "failed": 0, "error": str(e)}

    if not tokens:
        return {"sent": 0, "failed": 0, "reason": "no_devices"}

    sent = 0
    failed = 0
    results = []

    for token_obj in tokens:
        platform = token_obj.platform
        device_token = token_obj.device_token

        # 通道过滤
        target_channel = _platform_to_channel(platform)
        if channel and target_channel != channel:
            continue

        try:
            result = await _send_to_device(
                device_token=device_token,
                platform=platform,
                title=title,
                body=body,
                data=data,
            )
            results.append(result)
            if result.get("success"):
                sent += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            logger.debug("push_send_failed: token=%s platform=%s error=%s",
                         device_token[:8], platform, e)

    return {"sent": sent, "failed": failed, "results": results}


async def send_project_push(
    db,
    project_id: str,
    title: str,
    body: str,
    alert_type: str = "info",
    exclude_user_id: str | None = None,
) -> dict[str, Any]:
    """向项目相关方全员推送通知。

    推送对象：项目业主 + 施工负责人 + 监理（如有）。

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        title: 通知标题
        body: 通知正文
        alert_type: 预警类型（info/warning/error/critical）
        exclude_user_id: 排除的用户 ID（如操作者本人）

    Returns:
        {"total_users": int, "sent": int, "failed": int}
    """
    if not settings.push_enabled:
        return {"total_users": 0, "sent": 0, "failed": 0, "reason": "disabled"}

    try:
        from sqlalchemy import select
        from app.models.project import Project

        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()

        if not project:
            return {"total_users": 0, "sent": 0, "failed": 0, "reason": "project_not_found"}

        # 收集相关用户
        recipients = {project.owner_id}
        if hasattr(project, "contractor_id") and project.contractor_id:
            recipients.add(project.contractor_id)
        if hasattr(project, "supervisor_id") and project.supervisor_id:
            recipients.add(project.supervisor_id)
        if exclude_user_id:
            recipients.discard(exclude_user_id)

        total_sent = 0
        total_failed = 0

        push_data = {
            "project_id": project_id,
            "alert_type": alert_type,
            "click_action": "OPEN_PROJECT",
        }

        for uid in recipients:
            result = await send_push_to_user(
                db=db, user_id=uid, title=title, body=body, data=push_data,
            )
            total_sent += result.get("sent", 0)
            total_failed += result.get("failed", 0)

        return {
            "total_users": len(recipients),
            "sent": total_sent,
            "failed": total_failed,
        }

    except Exception as e:
        logger.error("send_project_push_error: project=%s error=%s", project_id, e)
        return {"total_users": 0, "sent": 0, "failed": 0, "error": str(e)}


async def _send_to_device(
    device_token: str,
    platform: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """向单个设备发送推送通知。

    当前为 mock 实现。生产环境接入 FCM/APNs 时替换此函数：
    - FCM: POST https://fcm.googleapis.com/v1/projects/{project}/messages:send
    - APNs: POST https://api.push.apple.com/3/device/{token}
    - WebPush: 使用 Web Push API（需 VAPID keys）
    """
    channel = _platform_to_channel(platform)

    # Mock 模式：记录日志并返回成功
    logger.info(
        "push_send_mock: channel=%s token=%s title=%s",
        channel, device_token[:12], title,
    )
    return {
        "success": True,
        "channel": f"{channel}_mock",
        "token": device_token[:12] + "...",
        "title": title,
    }


def _platform_to_channel(platform: str) -> str:
    """平台 → 推送通道映射"""
    mapping = {
        "ios": PushChannel.APNS,
        "android": PushChannel.FCM,
        "web": PushChannel.WEB,
        "harmonyos": PushChannel.FCM,  # 鸿蒙使用 HMS Push Kit
    }
    return mapping.get(platform.lower(), PushChannel.MOCK)
