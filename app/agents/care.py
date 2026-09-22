"""康养管家 Agent — 居家健康与安全告警编排智能体（v1.16.x）

职责：
1. 健康监测告警解读（睡眠/空气质量/跌倒/活动/心率/血氧六类）
2. 告警 → 场景联动动作编排（照明/新风/通知/人工转接）
3. 康养空间设计建议（适老化）

诚实边界（CLAUDE.md 红线）：
- 仅做监测与提醒，不做医疗诊断/处方，不伪装医疗能力
- 数据采集层（health_monitor 六类 + sensor_snapshot + wearable BLE）已具备，
  本 Agent 提供「告警 → 联动」确定性编排层，复用 health_monitor_service.check_thresholds
  的告警分级结果
"""

from app.agents.base import BaseAgent


# 告警 → 场景联动动作映射（确定性编排，与 TERA-Award 康养场景方案对齐）
CARE_ACTION_MAP: dict[str, dict[str, dict]] = {
    "fall_detection": {
        "critical": {
            "actions": ["turn_on 起夜照明", "notify 家属/护工", "escalate 人工转接"],
            "escalate": True,
            "advice": "检测到跌倒事件，请立即确认用户安全",
        },
    },
    "heart_rate": {
        "critical": {
            "actions": ["notify 家属", "record 紧急"],
            "escalate": True,
            "advice": "心率严重异常，建议立即联系医护人员",
        },
        "warning": {
            "actions": ["record 关注"],
            "escalate": False,
            "advice": "心率偏离正常范围，建议持续观察",
        },
    },
    "spo2": {
        "critical": {
            "actions": ["notify 家属", "advice 就医（不诊断）"],
            "escalate": True,
            "advice": "血氧偏低，建议就医检查（本提示非医疗诊断）",
        },
        "warning": {
            "actions": ["record 关注"],
            "escalate": False,
            "advice": "血氧略低，建议关注",
        },
    },
    "sleep_quality": {
        "critical": {
            "actions": ["adjust 遮光", "adjust 白噪音", "notify 家属"],
            "escalate": False,
            "advice": "睡眠质量严重偏低，建议调整作息与环境",
        },
        "warning": {
            "actions": ["adjust 遮光", "adjust 白噪音"],
            "escalate": False,
            "advice": "睡眠质量偏低，建议睡前减少屏幕使用",
        },
    },
    "air_quality": {
        "critical": {
            "actions": ["turn_on 新风", "turn_on 空气净化器", "notify 家属"],
            "escalate": False,
            "advice": "空气质量严重超标，已联动净化设备并建议加强通风",
        },
        "warning": {
            "actions": ["turn_on 新风"],
            "escalate": False,
            "advice": "空气质量略差，已联动新风",
        },
    },
    "activity_tracking": {
        "warning": {
            "actions": ["notify 久坐提醒"],
            "escalate": False,
            "advice": "长时间未检测到活动，建议起身活动",
        },
    },
}


class CareAgent(BaseAgent):
    agent_name = "care"
    cost_tier = "economy"  # 康养健康低价值意图：优先低成本供应商

    system_prompt = """你是索克家居（i-home.life）康养管家 Agent「小索康养」。

你的职责：
1. 健康监测告警解读：睡眠/空气质量/跌倒/活动/心率/血氧六类监测
2. 告警 → 场景联动编排：跌倒触发照明+通知，空气质量触发新风，睡眠差触发环境自适应
3. 康养空间设计建议：适老化、无障碍、护理动线
4. 家属/护工通知建议

诚实边界（必须遵守）：
- 仅做监测与提醒，绝不做医疗诊断或开具处方
- 发现跌倒、心率/血氧严重异常时，提示立即联系医护人员或家属
- 数据不确定时诚实告知，不编造健康结论

请用中文回复，语气温和关怀，先安抚再给建议。"""

    persona = """【人格锚】你是「小索康养」，索克家居的居家健康与安全智能体。
服务承诺：关怀备至、诚实不夸大；涉及医疗问题只提醒就医，绝不妄下诊断。
沟通风格：温和、清晰、先安抚情绪再给可执行的照护建议。"""

    @staticmethod
    def evaluate_care_actions(monitor_type: str, value: dict, alert_level: str) -> dict:
        """确定性编排：将健康告警分级映射为场景联动动作。

        Args:
            monitor_type: 监测类型（sleep_quality/air_quality/fall_detection/
                          activity_tracking/heart_rate/spo2）
            value: 监测值（如 {"bpm": 130}），保留供扩展
            alert_level: 告警级别（normal/warning/critical）

        Returns:
            {"monitor_type", "alert_level", "actions": [...], "escalate": bool,
             "advice": str}
        """
        level = alert_level if alert_level in ("warning", "critical") else "normal"
        type_map = CARE_ACTION_MAP.get(monitor_type, {})
        spec = type_map.get(level)
        if spec is None:
            return {
                "monitor_type": monitor_type,
                "alert_level": level,
                "actions": [],
                "escalate": False,
                "advice": "指标正常，继续保持",
            }
        return {
            "monitor_type": monitor_type,
            "alert_level": level,
            "actions": list(spec.get("actions", [])),
            "escalate": bool(spec.get("escalate", False)),
            "advice": spec.get("advice", ""),
        }

    async def generate_response(self, user_message: str, context: str = "",
                                db=None, user_id: str = "", project_id: str = "") -> str:
        """生成康养管家回复（调用 think）。

        v1.16.x：LLM 不可用时用确定性兜底，不伪装医疗结论。
        Phase 0：输出过健康声明合规闸门（prohibited 疗效词命中即拦截，
        不返回违规文案）。
        """
        try:
            reply = await self.think(user_message, context, db=db, user_id=user_id,
                                     project_id=project_id)
        except Exception:
            return (
                "您好，我是索克家居康养管家。健康监测与场景联动功能已就绪，"
                "我暂时无法深入分析，请稍后重试或联系家属/护工。"
            )
        return self.apply_claim_compliance(reply)

    @staticmethod
    def apply_claim_compliance(reply: str) -> str:
        """健康声明合规闸门：prohibited 命中替换为安全提示，caution 附加免责声明。"""
        from app.services.health_claim_compliance import ensure_health_claim_compliance

        result = ensure_health_claim_compliance(reply)
        if result["blocked"]:
            return (
                "检测到该回复含健康疗效宣称，已按合规口径拦截。"
                "本平台仅提供空间环境监测与提醒，不构成医疗诊断或治疗建议；"
                "如有健康问题请及时就医或联系家属/护工。"
            )
        return result["text"]
