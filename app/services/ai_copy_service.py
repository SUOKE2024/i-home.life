"""AI 文案批量生成服务 — 后台异步处理"""

import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import select

from app.models.product import Product
from app.agents.procurement import ProcurementAgent

logger = logging.getLogger("ihome")

# 内存中的任务状态追踪（生产环境应迁移到 Redis/数据库）
_job_status: dict[str, dict] = {}


def get_job_status(batch_id: str) -> dict | None:
    """获取批量 AI 文案生成任务状态"""
    return _job_status.get(batch_id)


async def start_batch_ai_copy(
    batch_id: str,
    product_ids: list[str],
    db_session_factory,
):
    """启动后台批量 AI 文案生成任务（fire-and-forget）"""
    job = {
        "batch_id": batch_id,
        "total": len(product_ids),
        "completed": 0,
        "failed": 0,
        "in_progress": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    _job_status[batch_id] = job

    # 在后台执行
    asyncio.create_task(
        _run_batch_ai_copy(batch_id, product_ids, db_session_factory)
    )


async def _run_batch_ai_copy(
    batch_id: str,
    product_ids: list[str],
    db_session_factory,
):
    """后台执行批量 AI 文案生成"""
    agent = ProcurementAgent()
    try:
        for pid in product_ids:
            try:
                async with db_session_factory() as db:
                    result = await db.execute(select(Product).where(Product.id == pid))
                    product = result.scalar_one_or_none()
                    if not product:
                        _job_status[batch_id]["failed"] += 1
                        continue

                    # 构建 prompt
                    prompt = _build_marketing_prompt(product)

                    try:
                        reply = await agent.think(prompt)
                        desc, tags = _parse_ai_response(reply)
                    except Exception:
                        # LLM 不可用时生成默认文案
                        desc = _generate_fallback_description(product)
                        tags = []

                    if desc:
                        product.ai_description = desc
                        if not product.description:
                            product.description = desc
                    if tags:
                        existing_tags = json.loads(product.tags) if product.tags else []
                        merged = list(dict.fromkeys(existing_tags + tags))
                        product.tags = json.dumps(merged, ensure_ascii=False)
                    product.ai_generated = True

                    await db.commit()
                    _job_status[batch_id]["completed"] += 1

            except Exception as e:
                logger.warning(f"AI 文案生成失败 product={pid}: {e}")
                _job_status[batch_id]["failed"] += 1

            _job_status[batch_id]["updated_at"] = datetime.utcnow()

            # 避免 LLM API 限流
            await asyncio.sleep(0.5)

    finally:
        await agent.close()
        _job_status[batch_id]["in_progress"] = False
        _job_status[batch_id]["updated_at"] = datetime.utcnow()


def _build_marketing_prompt(product: Product) -> str:
    """构建营销文案生成 prompt"""
    cat_labels = {
        "tile": "瓷砖", "flooring": "地板", "cabinet": "橱柜",
        "paint": "涂料", "lighting": "灯具", "appliance": "家电",
        "curtain": "窗帘", "custom_furniture": "定制家具",
        "service": "家居服务", "other": "家居产品",
    }
    cat_label = cat_labels.get(product.category, "家居产品")
    price_info = ""
    if product.price_min:
        price_info = f"¥{product.price_min:.0f}"
        if product.price_max and product.price_max != product.price_min:
            price_info += f"-{product.price_max:.0f}"
        price_info += f"/{product.unit}"

    existing_tags = []
    if product.tags:
        try:
            existing_tags = json.loads(product.tags) or []
        except Exception:
            pass

    return (
        f"你是家居产品营销文案专家。请为以下产品撰写一段吸引人的营销文案（80-150字），"
        f"并推荐3-5个标签。\n\n"
        f"产品名称：{product.name}\n"
        f"产品类别：{cat_label}\n"
        f"价格：{price_info}\n"
        f"现有标签：{', '.join(existing_tags)}\n"
        f"产品描述：{product.description or '暂无'}\n\n"
        f"要求：\n"
        f"1. 突出产品核心卖点和优势\n"
        f"2. 适合手机端阅读，段落简短\n"
        f"3. 包含场景化描述\n"
        f"4. 用 JSON 格式回复：{{'description': '...', 'tags': ['标签1', '标签2']}}"
    )


def _parse_ai_response(reply: str) -> tuple[str, list[str]]:
    """解析 AI 返回的 JSON 文案"""
    text = reply.strip()
    # 提取 JSON
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
        return data.get("description", ""), data.get("tags", [])
    except Exception:
        pass

    # 尝试从文本中提取
    try:
        # 找 { 开头 } 结尾的部分
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            return data.get("description", ""), data.get("tags", [])
    except Exception:
        pass

    return "", []


def _generate_fallback_description(product: Product) -> str:
    """生成默认产品描述（LLM 不可用时）"""
    cat_labels = {
        "tile": "瓷砖", "flooring": "地板", "cabinet": "橱柜",
        "paint": "涂料", "lighting": "灯具", "appliance": "家电",
        "curtain": "窗帘", "custom_furniture": "定制家具",
        "service": "家居服务", "other": "家居产品",
    }
    cat_label = cat_labels.get(product.category, "家居产品")
    parts = [product.name]
    if product.description:
        parts.append(product.description[:80])
    if product.price_min:
        price = f"¥{product.price_min:.0f}"
        if product.price_max and product.price_max != product.price_min:
            price += f"-{product.price_max:.0f}"
        price += f"/{product.unit}"
        parts.append(price)
    parts.append(f"品质{cat_label}，索克家居认证供应商直供。")
    return "。".join(parts) + "。"
