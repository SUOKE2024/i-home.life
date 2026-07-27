"""回复模板系统 — 集中管理硬编码中文回复文本

将 voice.py / voice_realtime.py / agents.py 中分散的硬编码回复
统一收拢到 ReplyTemplates，方便：
- 国际化（i18n）迁移
- 统一语气调优
- 避免跨文件重复
"""


class ReplyTemplates:
    """索克家居 AI 助手回复模板"""

    # ── 意图分类回复 ──

    @staticmethod
    def design(text: str) -> str:
        return f"收到设计需求：「{text}」。正在为您生成布局方案..."

    @staticmethod
    def design_room_created(name: str, w: float, h: float) -> str:
        return f"已创建 {name} ({w}×{h}m)"

    @staticmethod
    def budget(text: str) -> str:
        return f"预算分析：「{text}」。建议按舒适型标准（1200-2000/㎡）估算。"

    @staticmethod
    def procurement(text: str) -> str:
        return f"采购分析：「{text}」。已为您匹配优质供应商，请查看推荐列表。"

    @staticmethod
    def construction(text: str) -> str:
        return f"施工计划：「{text}」。建议按 8 阶段推进，预计工期 45 天。"

    @staticmethod
    def general(text: str) -> str:
        return f"收到您的消息：「{text}」。我是索克家居 AI 助手，可以帮您进行设计、预算、采购、施工管理。"

    # ── 增强版回复（voice_realtime.py _get_enhanced_reply）──

    @staticmethod
    def enhanced_reply(intent: str) -> str:
        """无 LLM 时的降级回复模板"""
        return {
            "design":        "收到设计需求，正在为您分析户型并生成布局方案...",
            "budget":        "正在为您进行预算分析，请稍候...",
            "procurement":   "正在搜索匹配的物料和供应商...",
            "construction":  "正在查询施工进度和质检状态...",
            "qa_inspector":  "正在执行质量检测，请稍候...",
            "concierge":     "您好，我是索克家居 AI 客服，请问有什么可以帮您？",
            "general":       "收到您的消息，我是索克家居 AI 助手，可以帮您进行设计、预算、采购、施工管理。",
        }.get(intent, "收到您的消息，我是索克家居 AI 助手，可以帮您进行设计、预算、采购、施工管理。")

    @staticmethod
    def emotion_prefix(emotion_label: str) -> str:
        """情绪感知前缀"""
        if emotion_label in ("anxious", "angry", "sad", "tired"):
            return "理解您的心情，我马上帮您处理。"
        return ""

    # ── 新增业务模块引导回复（voice_realtime.py / agents.py 共用）──

    _MODULE_REPLIES: dict[str, str] = {
        "ar_measurement": (
            "AR 空间测量功能需要在移动端 App 上使用。请打开索克家居 App，"
            "进入项目后点击「AR 扫描」即可开始测量。支持 RoomPlan 全屋扫描、"
            "激光测距仪辅助校准和墙面特征自动识别。"
        ),
        "floorplans": "户型管理功能可以帮助您查看、保存和修改户型方案。您可以在项目中查看已保存的户型平面图。",
        "structural": "土建结构模块支持梁、柱、墙、板等结构元素的设计与分析。请告诉我具体的结构设计需求。",
        "lighting": "灯光设计模块支持照明方案规划、照度计算和色温推荐。请告诉我您想为哪个房间设计灯光方案。",
        "smart_home": "智能家居模块支持设备配置、场景联动和 Matter/Zigbee 协议。请告诉我您想配置哪种智能设备。",
        "scene_automation": "场景自动化支持创建和编辑智能场景联动规则，如离家模式、回家模式、睡眠模式等。",
        "custom_furniture": "定制家具模块支持参数化设计柜体（衣柜、橱柜、书柜等），自动计算板材用量和价格。",
        "tasks": "任务协调模块支持施工任务的分派、跟踪和管理。请告诉我您想创建或查看什么任务。",
        "change_orders": "变更管理模块支持工程变更的申请、审批和跟踪。请告诉我您想做什么样的变更。",
        "crews": "工程队管理模块支持班组匹配和施工队调度。请告诉我您的项目需求，我来帮您匹配合适的施工队。",
        "vr_panorama": "VR 全景查看器支持 360° 沉浸式漫游和场景切换。请打开 VR 全景页面开始体验。",
        "ai_render": "AI 渲染模块支持 2D/3D 效果图生成和风格迁移。请告诉我您想渲染什么内容。",
        "sketch_to_3d": "草图转3D 功能可以将手绘草图智能转换为 3D 模型。请上传您的草图，我来帮您转换。",
        "soft_furnishing": "软装设计模块支持窗帘、布艺、地毯、饰品等软装配饰的选择与搭配。",
        "hard_decoration": "硬装设计模块支持吊顶、墙面装饰、地面铺装等硬装方案设计。",
        "takeoff": "工程量计算模块支持材料清单生成和用量估算。请告诉我您需要计算哪些项目的工程量。",
        "points": "积分系统支持积分累计、等级提升和积分兑换。您可以通过完成装修任务获取积分。",
        "cad_import": "CAD 导入模块支持 DXF/DWG 格式的户型图纸导入和墙体解析。",
    }

    @staticmethod
    def module_guide(intent: str) -> str:
        """获取新增业务模块的引导回复"""
        return ReplyTemplates._MODULE_REPLIES.get(
            intent,
            f"「{intent}」模块正在建设中，请联系管理员了解详情。",
        )
