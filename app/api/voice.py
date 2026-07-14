from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.models.user import User
from app.auth import get_current_user

router = APIRouter(prefix="/voice", tags=["语音"])


class VoiceMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    project_id: str | None = None


class VoiceResponse(BaseModel):
    transcript: str
    intent: str = "general"
    reply: str
    actions: list[dict] = []


@router.post("/process", response_model=VoiceResponse)
async def process_voice(
    data: VoiceMessage,
    current_user: User = Depends(get_current_user),
):
    text = data.text
    intent = "general"

    if any(kw in text for kw in ["设计", "布局", "方案", "户型", "画", "墙", "房间", "添加", "加一个", "新建", "建造"]):
        intent = "design"
    elif any(kw in text for kw in ["测量", "丈量", "扫描", "激光", "LiDAR", "摄像头", "拍照测量", "量房", "测距", "面积"]):
        intent = "measurement"
    elif any(kw in text for kw in ["预算", "价格", "费用", "成本", "多少钱"]):
        intent = "budget"
    elif any(kw in text for kw in ["采购", "买", "材料", "建材", "供应商"]):
        intent = "procurement"
    elif any(kw in text for kw in ["施工", "进度", "验收", "质检"]):
        intent = "construction"

    from app.agents.orchestrator import OrchestratorAgent
    classification = OrchestratorAgent.fallback_classify(text)
    fallback_intent = classification.get("intent", "general")
    # 仅当 fallback 给出更具体的意图时才覆盖(避免 general 覆盖已识别的具体意图)
    if fallback_intent != "general":
        intent = fallback_intent

    reply, actions = _handle_intent(text, intent)
    return VoiceResponse(transcript=text, intent=intent, reply=reply, actions=actions)


def _handle_intent(text: str, intent: str) -> tuple[str, list[dict]]:
    actions = []
    if intent == "measurement":
        reply = _build_measurement_guide(text)
        actions = _extract_room_from_text(text)
    elif intent == "design":
        reply = f"收到设计需求：「{text}」。正在为您生成布局方案..."
        if "加" in text or "添加" in text or "建" in text:
            import re
            name_match = re.search(r"(客厅|卧室|厨房|卫生间|书房|阳台|餐厅|走廊)", text)
            size_match = re.search(r"(\d+(\.\d+)?)[×xX](\d+(\.\d+)?)", text)
            w = float(size_match.group(1)) if size_match else 4
            h = float(size_match.group(3)) if size_match else 3
            name = name_match.group(1) if name_match else "房间"
            type_map = {"客厅": "living_room", "卧室": "bedroom", "厨房": "kitchen", "卫生间": "bathroom", "书房": "study", "阳台": "balcony", "餐厅": "dining_room", "走廊": "hallway"}
            actions = [{"action": "add_room", "x": 0, "y": 0, "w": w, "h": h, "name": name, "roomType": type_map.get(name, "living_room")}]
            reply = f"已创建 {name} ({w}×{h}m)"
    elif intent == "budget":
        reply = f"预算分析：「{text}」。建议按舒适型标准（1200-2000/㎡）估算。"
    elif intent == "procurement":
        reply = f"采购分析：「{text}」。已为您匹配优质供应商，请查看推荐列表。"
    elif intent == "construction":
        reply = f"施工计划：「{text}」。建议按 8 阶段推进，预计工期 45 天。"
    else:
        reply = f"收到您的消息：「{text}」。我是索克家居 AI 助手，可以帮您进行设计、预算、采购、施工管理。"
    return reply, actions


def _build_measurement_guide(text: str) -> str:
    """构建测量语音引导回复"""
    guide_parts = ["📐 测量模式已激活。"]
    # 检测场景类型
    scene_hints = {"室内": "indoor", "阳台": "balcony", "室外": "outdoor", "露台": "outdoor"}
    for kw, scene in scene_hints.items():
        if kw in text:
            guide_parts.append(f"检测到{kw}场景，推荐使用{'激光测距仪' if scene == 'indoor' else '户外激光+视觉辅助'}测量。")
            break
    else:
        guide_parts.append("请手持设备沿墙壁扫描，或用激光测距仪逐个测量房间。")

    guide_parts.append("语音引导步骤：1) 站到房间一角 → 2) 说出房间名称和用途 → 3) 沿墙移动设备 → 4) 系统自动计算面积。")
    guide_parts.append("💡 您可以说：「客厅 6米×7米」来直接录入尺寸。")
    return "\n".join(guide_parts)


def _extract_room_from_text(text: str) -> list[dict]:
    """从语音文本中提取房间测量信息"""
    import re
    actions = []
    # 匹配模式: "客厅 6×7" 或 "主卧 4米×5米"
    pattern = re.compile(r"(客厅|主卧|次卧|卧室|厨房|卫生间|书房|阳台|餐厅|走廊|玄关).*?(\d+(?:\.\d+)?)[×xX米]*\s*[×xX]*\s*(\d+(?:\.\d+)?)")
    for m in pattern.finditer(text):
        name = m.group(1)
        w = float(m.group(2))
        h = float(m.group(3))
        type_map = {"客厅": "living_room", "卧室": "living_room", "主卧": "bedroom", "次卧": "bedroom", "厨房": "kitchen", "卫生间": "bathroom", "书房": "study", "阳台": "balcony", "餐厅": "dining_room", "走廊": "hallway", "玄关": "hallway"}
        actions.append({"action": "measure_room", "name": name, "room_type": type_map.get(name, "living_room"), "width": w, "length": h, "area": round(w * h, 2)})
    return actions
