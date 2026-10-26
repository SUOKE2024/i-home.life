"""运营侧「新改造需求」提醒（fire-and-forget）。

为什么需要这个模块：
小程序 `pages/demand` 提交后，后端只落一条 project（phase=initiation），
平台上没有任何人被告知 —— 而页面写着「顾问会联系你确认上门时间」。
线索沉底，承诺就变成空话。本模块负责把新需求推到运营侧。

通道与降级：
  - 配置 `OPS_ALERT_WEBHOOK`（企业微信群机器人）：POST markdown 消息；
  - 未配置：写 WARNING 日志（含脱敏手机号），至少能在日志巡检里被发现；
  - 通道失败：只记日志。**绝不向上抛异常** —— 业主提交成功与否不能被通知渠道绑架。

隐私边界：
手机号在日志中脱敏（138****8000），仅在发往运营群的正文中完整给出 ——
不脱敏运营无法回访，脱敏了日志泄露风险可控。
"""
import logging
import re

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_PHONE_PATTERN = re.compile(r"^(\d{3})\d{4}(\d{4})$")

_PROJECT_TYPE_LABEL = {
    "full_renovation": "全屋改造",
    "hard_decoration": "硬装施工",
    "soft_furnishing": "软装搭配",
    "curtain": "窗帘定制",
    "kitchen": "厨房改造",
    "bathroom": "卫生间改造",
    "electrical": "水电改造",
    "carpentry": "木工定制",
    "painting": "油漆涂装",
    "plumbing": "管道改造",
    "masonry": "泥瓦工程",
    "installation": "安装服务",
}


def mask_phone(phone: str | None) -> str:
    """日志用脱敏：138****8000；非标准号码只标记「已填写」，不打印原值。"""
    if not phone:
        return "未填写"
    matched = _PHONE_PATTERN.match(phone.strip())
    if matched:
        return f"{matched.group(1)}****{matched.group(2)}"
    return "已填写"


def _build_markdown(
    *,
    project_id: str,
    name: str,
    project_type: str | None,
    contact_name: str | None,
    contact_phone: str | None,
    address: str | None,
    total_area: float | None,
    description: str | None,
) -> str:
    type_label = _PROJECT_TYPE_LABEL.get(project_type or "", project_type or "未指定")
    lines = [
        "**新改造需求待跟进**",
        f"> 项目：{name}",
        f"> 类型：{type_label}",
        f"> 面积：{f'{total_area:g} ㎡' if total_area else '未填写'}",
        f"> 地址：{address or '未填写'}",
        f"> 联系人：{contact_name or '未填写'}",
        f"> 手机号：{contact_phone or '未填写'}",
        f"> 需求说明：{(description or '无')[:120]}",
        f"> project_id：`{project_id}`",
        "",
        "请安排顾问确认上门勘测时间（需求落库即 phase=initiation，尚未派单）。",
    ]
    return "\n".join(lines)


async def notify_new_demand(
    *,
    project_id: str,
    name: str,
    project_type: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    address: str | None = None,
    total_area: float | None = None,
    description: str | None = None,
) -> bool:
    """推送新需求。返回是否真的送达运营通道（未配置/失败均返回 False，不抛异常）。"""
    settings = get_settings()
    if not settings.ops_alert_enabled:
        logger.info("ops_alert_disabled project_id=%s", project_id)
        return False

    if not settings.ops_alert_webhook:
        # 无通道时也不能静默：日志是最后一道可被巡检发现的防线
        logger.warning(
            "new_demand_pending_ops project_id=%s type=%s phone=%s "
            "reason=ops_alert_webhook_not_configured",
            project_id,
            project_type or "unknown",
            mask_phone(contact_phone),
        )
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": _build_markdown(
                project_id=project_id,
                name=name,
                project_type=project_type,
                contact_name=contact_name,
                contact_phone=contact_phone,
                address=address,
                total_area=total_area,
                description=description,
            )
        },
    }

    try:
        async with httpx.AsyncClient(timeout=settings.ops_alert_timeout_seconds) as client:
            resp = await client.post(settings.ops_alert_webhook, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning(
            "new_demand_alert_failed project_id=%s error=%s", project_id, type(e).__name__
        )
        return False

    # 企业微信机器人业务错误在 200 里返回 errcode
    errcode = body.get("errcode") if isinstance(body, dict) else None
    if errcode not in (0, None):
        logger.warning(
            "new_demand_alert_rejected project_id=%s errcode=%s errmsg=%s",
            project_id,
            errcode,
            (body.get("errmsg") or "")[:80],
        )
        return False

    logger.info("new_demand_alert_sent project_id=%s", project_id)
    return True
