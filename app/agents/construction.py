"""施工 Agent — 进度管理、AI 质检、施工计划"""

from datetime import datetime, timezone

from app.agents.base import BaseAgent


# 标准施工阶段（8 阶段）
CONSTRUCTION_PHASES = [
    {"code": "preparation", "name": "准备阶段", "duration": (2, 5), "description": "办理装修许可、材料进场、成品保护"},
    {"code": "demolition", "name": "拆改阶段", "duration": (3, 7), "description": "墙体拆改、垃圾清运、结构加固"},
    {"code": "mep", "name": "水电阶段", "duration": (5, 10), "description": "管线敷设、点位定位、打压测试"},
    {"code": "masonry", "name": "泥瓦阶段", "duration": (7, 15), "description": "防水、贴砖、地面找平"},
    {"code": "carpentry", "name": "木工阶段", "duration": (5, 10), "description": "吊顶、柜体安装、造型基层"},
    {"code": "painting", "name": "油漆阶段", "duration": (7, 10), "description": "墙面处理、刷漆、壁纸"},
    {"code": "installation", "name": "安装阶段", "duration": (5, 7), "description": "灯具/开关/卫浴/橱柜安装"},
    {"code": "acceptance", "name": "验收阶段", "duration": (2, 3), "description": "全面验收、问题整改、保洁"},
]


# 质检检查清单（按阶段）
QUALITY_CHECKLISTS = {
    "mep": [
        {"item": "水管打压测试", "standard": "0.8MPa 保压 30 分钟不掉压", "method": "pressure_test"},
        {"item": "电路绝缘测试", "standard": "绝缘电阻 ≥ 0.5MΩ", "method": "insulation_test"},
        {"item": "线管布局", "standard": "横平竖直，无三管交叉", "method": "visual_check"},
        {"item": "强弱电间距", "standard": "≥ 500mm", "method": "distance_check"},
        {"item": "开关插座位置", "standard": "符合图纸偏差 ≤ 5mm", "method": "dimension_check"},
    ],
    "masonry": [
        {"item": "防水闭水试验", "standard": "蓄水 48h 无渗漏", "method": "water_test"},
        {"item": "瓷砖空鼓率", "standard": "单砖空鼓 < 5%，整体 < 3%", "method": "tap_test"},
        {"item": "瓷砖平整度", "standard": "2m 靠尺 ≤ 2mm", "method": "flatness_check"},
        {"item": "阴阳角方正度", "standard": "偏差 ≤ 3mm", "method": "square_check"},
        {"item": "地漏坡度", "standard": "坡度 1%-2%，无积水", "method": "slope_check"},
    ],
    "carpentry": [
        {"item": "吊顶平整度", "standard": "2m 靠尺 ≤ 3mm", "method": "flatness_check"},
        {"item": "柜体对角线偏差", "standard": "≤ 2mm", "method": "diagonal_check"},
        {"item": "柜门缝隙", "standard": "均匀 1.5-2.5mm", "method": "gap_check"},
        {"item": "抽屉滑轨", "standard": "顺滑无异响", "method": "function_test"},
    ],
    "painting": [
        {"item": "墙面平整度", "standard": "2m 靠尺 ≤ 3mm", "method": "flatness_check"},
        {"item": "色差", "standard": "无可见色差", "method": "color_check"},
        {"item": "流坠/漏刷", "standard": "无流坠、无漏刷", "method": "visual_check"},
        {"item": "阴阳角", "standard": "顺直，偏差 ≤ 2mm", "method": "straightness_check"},
    ],
    "installation": [
        {"item": "灯具安装牢固度", "standard": "承重 ≥ 灯具重量 4 倍", "method": "load_test"},
        {"item": "插座接线", "standard": "左零右火上地线", "method": "wiring_check"},
        {"item": "卫浴下水", "standard": "排水通畅无堵塞", "method": "drainage_test"},
        {"item": "橱柜门板", "standard": "开关顺滑，缝隙均匀", "method": "function_test"},
    ],
}


class ConstructionAgent(BaseAgent):
    agent_name = "construction"
    system_prompt = """你是索克家居（i-home.life）AI 施工 Agent。

你的职责：
1. 根据设计方案生成施工计划（Gantt 排期）
2. 分解施工任务、设定里程碑节点
3. 每日推送任务、检查施工日志
4. AI 照片审核，比对设计图纸
5. 生成施工日报/周报

标准施工流程：
- 准备阶段（2-5天）：办理装修许可、材料进场
- 拆改阶段（3-7天）：墙体拆改、垃圾清运
- 水电阶段（5-10天）：管线敷设、点位定位、打压测试
- 泥瓦阶段（7-15天）：防水、贴砖、地面找平
- 木工阶段（5-10天）：吊顶、柜体安装
- 油漆阶段（7-10天）：墙面处理、刷漆
- 安装阶段（5-7天）：灯具/开关/卫浴安装
- 验收阶段（2-3天）：全面验收、问题整改

请用中文回复，注重工期安排和质量管理。"""

    def generate_construction_plan(self, total_area: float = 100.0, tier: str = "comfort") -> dict:
        """生成施工计划（Gantt 排期）"""
        # 面积调整系数：小户型加急，大户型延长
        area_factor = 1.0
        if total_area > 150:
            area_factor = 1.3
        elif total_area > 120:
            area_factor = 1.15
        elif total_area < 80:
            area_factor = 0.85

        # 档次调整：豪华型延长工期
        tier_factor = {"economy": 0.9, "comfort": 1.0, "premium": 1.15, "luxury": 1.3}.get(tier, 1.0)
        factor = area_factor * tier_factor

        tasks = []
        current_day = 1
        for phase in CONSTRUCTION_PHASES:
            low, high = phase["duration"]
            duration = round((low + high) / 2 * factor)
            end_day = current_day + duration - 1
            tasks.append({
                "phase": phase["code"],
                "name": phase["name"],
                "start_day": current_day,
                "end_day": end_day,
                "duration_days": duration,
                "description": phase["description"],
            })
            current_day = end_day + 1

        total_days = current_day - 1
        return {
            "total_area": total_area,
            "tier": tier,
            "area_factor": area_factor,
            "tier_factor": tier_factor,
            "total_duration_days": total_days,
            "tasks": tasks,
            "milestones": [
                {"day": tasks[0]["end_day"], "name": "材料进场完成", "phase": "preparation"},
                {"day": tasks[2]["end_day"], "name": "水电验收", "phase": "mep"},
                {"day": tasks[3]["end_day"], "name": "泥瓦验收（闭水试验）", "phase": "masonry"},
                {"day": tasks[5]["end_day"], "name": "油漆完成", "phase": "painting"},
                {"day": total_days, "name": "竣工验收", "phase": "acceptance"},
            ],
            "reply": f"已生成施工计划：共 {len(tasks)} 阶段，预计工期 {total_days} 天（面积系数 {area_factor:.2f}，档次系数 {tier_factor:.2f}）",
        }

    def get_quality_checklist(self, phase: str) -> dict:
        """获取指定阶段的质检清单"""
        checklist = QUALITY_CHECKLISTS.get(phase, [])
        return {
            "phase": phase,
            "total_items": len(checklist),
            "checklist": checklist,
            "reply": f"「{phase}」阶段质检清单：共 {len(checklist)} 项检查点" if checklist else f"「{phase}」阶段暂无预设质检清单",
        }

    def analyze_inspection_images(self, inspection_data: dict) -> dict:
        """AI 图像比对质检框架（F38）

        inspection_data 结构：
        {
            "phase": "masonry",
            "images": [{"url": "...", "type": "tile_surface", "captured_at": "..."}],
            "design_reference": "url_to_design_drawing",
            "expected_dimensions": {"tile_gap": "2mm", "flatness": "≤3mm"}
        }
        """
        phase = inspection_data.get("phase", "")
        images = inspection_data.get("images", [])
        checklist = QUALITY_CHECKLISTS.get(phase, [])

        # Mock AI 检测结果（实际场景需对接 CV 模型）
        ai_results = []
        passed = 0
        for item in checklist:
            # 模拟：80% 通过率
            is_pass = (hash(item["item"]) % 10) < 8
            if is_pass:
                passed += 1
            ai_results.append({
                "check_item": item["item"],
                "standard": item["standard"],
                "method": item["method"],
                "ai_result": "pass" if is_pass else "fail",
                "confidence": round(0.85 + (hash(item["item"]) % 15) / 100, 2),
                "issues": [] if is_pass else [f"检测到「{item['item']}」未达标，建议整改"],
            })

        total = len(ai_results)
        pass_rate = round(passed / total * 100, 2) if total > 0 else 0
        score = round(pass_rate)  # 0-100

        if pass_rate >= 95:
            verdict = "excellent"
            verdict_text = "优秀"
        elif pass_rate >= 85:
            verdict = "pass"
            verdict_text = "合格"
        elif pass_rate >= 70:
            verdict = "conditional_pass"
            verdict_text = "有条件合格（需整改）"
        else:
            verdict = "fail"
            verdict_text = "不合格（需返工）"

        failed_items = [r for r in ai_results if r["ai_result"] == "fail"]

        return {
            "phase": phase,
            "image_count": len(images),
            "total_checks": total,
            "passed": passed,
            "failed": len(failed_items),
            "pass_rate": pass_rate,
            "score": score,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "ai_results": ai_results,
            "failed_items": failed_items,
            "repair_suggestions": [
                f"整改「{item['check_item']}」：当前不满足 {item['standard']}"
                for item in failed_items
            ],
            "reply": f"AI 质检完成：{phase} 阶段，{passed}/{total} 项合格（{pass_rate}%），结论：{verdict_text}",
        }

    def generate_daily_report(self, task_data: dict) -> dict:
        """生成施工日报"""
        return {
            "report_date": task_data.get("date", ""),
            "project_id": task_data.get("project_id", ""),
            "weather": task_data.get("weather", "晴"),
            "workers_count": task_data.get("workers_count", 0),
            "completed_tasks": task_data.get("completed_tasks", []),
            "ongoing_tasks": task_data.get("ongoing_tasks", []),
            "issues": task_data.get("issues", []),
            "materials_used": task_data.get("materials_used", []),
            "tomorrow_plan": task_data.get("tomorrow_plan", []),
            "reply": (
                f"施工日报已生成：完成 {len(task_data.get('completed_tasks', []))} 项，"
                f"进行中 {len(task_data.get('ongoing_tasks', []))} 项，"
                f"问题 {len(task_data.get('issues', []))} 项"
            ),
        }

    @staticmethod
    def detect_construction_intent(message: str) -> str:
        """识别施工相关子意图"""
        if any(kw in message for kw in ["进度", "排期", "计划", "工期", "gantt", "甘特"]):
            return "plan"
        if any(kw in message for kw in ["质检", "验收", "检查", "审核", "巡检"]):
            return "inspection"
        if any(kw in message for kw in ["日报", "周报", "日志", "汇报"]):
            return "report"
        if any(kw in message for kw in ["问题", "整改", "返工", "延期"]):
            return "issue"
        if any(kw in message for kw in ["发布任务", "招工", "找人", "安排", "派工", "需要工人", "要一个"]):
            return "publish_task"
        return "general"

    # ── 按工种发布任务到任务池 ──

    # 子角色 ↔ 施工阶段/任务类型映射
    SUB_ROLE_TASK_MAP = {
        "electrician": {
            "task_type": "construction",
            "phase": "mep",
            "title_template": "电路改造施工",
            "description_template": "承担 {project_name} 项目的电路敷设、开关插座安装、配电箱接线等工作",
            "claim_role": "contractor",
        },
        "plumber": {
            "task_type": "construction",
            "phase": "mep",
            "title_template": "水暖管道安装",
            "description_template": "承担 {project_name} 项目的给排水管敷设、暖气管道安装、打压测试等工作",
            "claim_role": "contractor",
        },
        "carpenter": {
            "task_type": "construction",
            "phase": "carpentry",
            "title_template": "木工制作安装",
            "description_template": "承担 {project_name} 项目的吊顶制作、柜体安装、门窗套线安装等工作",
            "claim_role": "contractor",
        },
        "mason": {
            "task_type": "construction",
            "phase": "masonry",
            "title_template": "泥瓦铺贴施工",
            "description_template": "承担 {project_name} 项目的防水处理、瓷砖铺贴、地面找平等工作",
            "claim_role": "contractor",
        },
        "painter": {
            "task_type": "construction",
            "phase": "painting",
            "title_template": "油漆涂刷施工",
            "description_template": "承担 {project_name} 项目的墙面批灰、油漆涂刷、壁纸铺贴等工作",
            "claim_role": "contractor",
        },
        "installer": {
            "task_type": "construction",
            "phase": "installation",
            "title_template": "设备安装施工",
            "description_template": "承担 {project_name} 项目的灯具/开关/卫浴/橱柜等设备安装工作",
            "claim_role": "contractor",
        },
        "curtain_installer": {
            "task_type": "construction",
            "phase": "installation",
            "title_template": "窗帘安装施工",
            "description_template": "承担 {project_name} 项目的窗帘轨道安装、窗帘挂装等工作",
            "claim_role": "contractor",
        },
        "supervisor": {
            "task_type": "qa_inspector",
            "phase": "acceptance",
            "title_template": "工程质量监理",
            "description_template": "承担 {project_name} 项目的全过程质量监理、进度把控、安全检查等工作",
            "claim_role": "contractor",
        },
    }

    def generate_sub_task_cards(
        self,
        project_info: dict,
        sub_roles: list[str] | None = None,
        location: str | None = None,
    ) -> dict:
        """根据位置、项目类型和所需工种生成任务发布卡片列表

        Args:
            project_info: {"project_id": str, "project_name": str, "address": str,
                           "project_type": str, "total_area": float}
            sub_roles: 需要发布的工种列表，为空则按项目类型自动推断
            location: 位置信息（用于匹配附近工人）

        Returns:
            {"tasks": [...], "reply": str}
        """
        if not sub_roles:
            sub_roles = self._infer_sub_roles(project_info.get("project_type", ""))

        tasks = []
        for sub_role in sub_roles:
            template = self.SUB_ROLE_TASK_MAP.get(sub_role)
            if not template:
                continue

            title = template["title_template"].format(project_name=project_info.get("project_name", ""))
            description = template["description_template"].format(project_name=project_info.get("project_name", ""))
            if location:
                description += f"（施工地点：{location}）"

            tasks.append({
                "sub_role": sub_role,
                "sub_role_label": self._sub_role_label(sub_role),
                "task_type": template["task_type"],
                "phase": template["phase"],
                "title": title,
                "description": description,
                "claim_role": template["claim_role"],
                "project_id": project_info.get("project_id"),
                "project_name": project_info.get("project_name"),
                "location": location or project_info.get("address"),
                "total_area": project_info.get("total_area"),
            })

        role_labels = "、".join([self._sub_role_label(r) for r in sub_roles])
        reply = (
            f"🔨 **施工任务发布**\n\n"
            f"根据项目「{project_info.get('project_name', '')}」的需求，"
            f"建议招募以下工种：{role_labels}\n\n"
            f"共 {len(tasks)} 个工种子任务已生成，将推送到任务池供相应工种申领。"
        )

        return {"tasks": tasks, "reply": reply, "sub_roles": sub_roles}

    @staticmethod
    def _infer_sub_roles(project_type: str) -> list[str]:
        """根据项目类型推断所需工种"""
        project_role_map = {
            "full_renovation": ["electrician", "plumber", "mason", "carpenter", "painter", "installer"],
            "hard_decoration": ["electrician", "plumber", "mason", "carpenter", "painter", "installer"],
            "soft_furnishing": ["installer", "carpenter"],
            "curtain": ["curtain_installer"],
            "curtain_designer": ["curtain_installer"],
            "kitchen": ["electrician", "plumber", "mason", "installer"],
            "bathroom": ["plumber", "mason", "installer"],
            "electrical": ["electrician"],
            "carpentry": ["carpenter"],
            "painting": ["painter"],
            "plumbing": ["plumber"],
            "masonry": ["mason"],
            "installation": ["installer"],
        }
        return project_role_map.get(project_type, ["installer"])

    @staticmethod
    def _sub_role_label(sub_role: str) -> str:
        """工种中文标签"""
        labels = {
            "electrician": "电工",
            "carpenter": "木工",
            "plumber": "水电安装工",
            "painter": "油漆工",
            "mason": "泥瓦工",
            "installer": "安装工",
            "curtain_installer": "窗帘安装工",
            "supervisor": "监理",
            "curtain_designer": "窗帘设计师",
        }
        return labels.get(sub_role, sub_role)


# ── F37 里程碑定义（与结算里程碑对齐：交房30% / 水电20% / 泥瓦25% / 竣工20% / 保修5%） ──
PROJECT_MILESTONES = [
    {"code": "delivery", "name": "交房验收", "phase": "preparation", "planned_percent": 5.0, "payment_ratio": 30.0},
    {"code": "mep", "name": "水电验收", "phase": "mep", "planned_percent": 30.0, "payment_ratio": 20.0},
    {"code": "masonry", "name": "泥瓦验收（闭水试验）", "phase": "masonry", "planned_percent": 55.0, "payment_ratio": 25.0},
    {"code": "completion", "name": "竣工验收", "phase": "acceptance", "planned_percent": 95.0, "payment_ratio": 20.0},
    {"code": "warranty", "name": "保修期满", "phase": "acceptance", "planned_percent": 100.0, "payment_ratio": 5.0},
]

# 阶段对应总进度百分比区间
PHASE_PROGRESS_RANGE = {
    "preparation": (0, 5),
    "demolition": (5, 15),
    "mep": (15, 30),
    "masonry": (30, 55),
    "carpentry": (55, 70),
    "painting": (70, 85),
    "installation": (85, 95),
    "acceptance": (95, 100),
}

# 状态 → 完成度映射
TASK_STATUS_PROGRESS = {
    "pending": 0.0,
    "in_progress": 50.0,
    "completed": 100.0,
    "delayed": 50.0,
    "paused": 30.0,
}


def _severity_from_delay(delay_days: int) -> str:
    """根据延期天数判定严重级别"""
    if delay_days >= 14:
        return "critical"
    if delay_days >= 7:
        return "high"
    if delay_days >= 3:
        return "medium"
    return "low"


def _compute_expected_progress(start_date: datetime, current_date: datetime, total_days: int) -> float:
    """基于起始日期 + 当前日期 + 总工期计算期望进度"""
    if total_days <= 0:
        return 0.0
    elapsed = (current_date - start_date).total_seconds() / 86400
    if elapsed <= 0:
        return 0.0
    expected = elapsed / total_days * 100
    return round(min(expected, 100.0), 2)


def manage_progress(  # noqa: C901
    project_id: str,
    tasks: list[dict],
    current_date: datetime | None = None,
    milestones: list[dict] | None = None,
) -> dict:
    """F37 AI 进度管理 — 预警 + 里程碑跟踪

    输入：施工任务列表（含 phase, status, start_date, end_date 等）
    输出：整体进度、阶段状态、预警、里程碑跟踪、风险等级、建议
    """
    now = current_date or datetime.now(timezone.utc)

    if not tasks:
        return {
            "project_id": project_id,
            "current_date": now,
            "overall_progress": 0.0,
            "expected_progress": 0.0,
            "progress_deviation": 0.0,
            "phase_status": [],
            "alerts": [],
            "milestones": [],
            "risk_level": "low",
            "summary": "暂无施工任务，无法分析进度",
            "suggestions": ["请先创建施工任务并设定计划日期"],
        }

    # 1. 计算各阶段进度
    phase_status = []
    phase_groups: dict[str, list[dict]] = {}
    for task in tasks:
        phase = task.get("phase", "preparation")
        phase_groups.setdefault(phase, []).append(task)

    for phase_info in CONSTRUCTION_PHASES:
        phase_code = phase_info["code"]
        group = phase_groups.get(phase_code, [])
        if not group:
            continue
        total = len(group)
        completed = sum(1 for t in group if t.get("status") == "completed")
        in_progress = sum(1 for t in group if t.get("status") in ("in_progress", "delayed"))
        phase_progress = round((completed * 100 + in_progress * 50) / total, 2)
        low, high = PHASE_PROGRESS_RANGE.get(phase_code, (0, 0))
        phase_status.append({
            "phase": phase_code,
            "name": next((p["name"] for p in CONSTRUCTION_PHASES if p["code"] == phase_code), phase_code),
            "total_tasks": total,
            "completed_tasks": completed,
            "in_progress_tasks": in_progress,
            "progress": phase_progress,
            "progress_range": [low, high],
        })

    # 2. 整体进度 = 各阶段进度按区间跨度加权平均
    overall_progress = 0.0
    total_span = 0
    for ps in phase_status:
        low, high = ps["progress_range"]
        span = max(high - low, 1)
        overall_progress += (ps["progress"] / 100) * span
        total_span += span
    overall_progress = round(overall_progress / max(total_span, 1) * 100, 2)

    # 3. 期望进度（基于首任务起始 + 总工期）
    dates_with_start = [t for t in tasks if t.get("start_date")]
    if dates_with_start:
        start_dates = []
        for t in dates_with_start:
            sd = t["start_date"]
            if isinstance(sd, str):
                try:
                    sd = datetime.fromisoformat(sd.replace("Z", "+00:00"))
                except Exception:
                    continue
            start_dates.append(sd)
        if start_dates:
            project_start = min(start_dates)
            end_dates = []
            for t in tasks:
                ed = t.get("end_date")
                if isinstance(ed, str):
                    try:
                        ed = datetime.fromisoformat(ed.replace("Z", "+00:00"))
                        end_dates.append(ed)
                    except Exception:
                        pass
                elif isinstance(ed, datetime):
                    end_dates.append(ed)
            total_days = (max(end_dates) - project_start).days if end_dates else 60
            expected_progress = _compute_expected_progress(project_start, now, total_days)
        else:
            expected_progress = 0.0
    else:
        expected_progress = 0.0

    progress_deviation = round(overall_progress - expected_progress, 2)

    # 4. 生成预警（延期 + 风险 + 里程碑）
    alerts = []
    for task in tasks:
        status = task.get("status", "pending")
        end_date = task.get("end_date")
        if not end_date:
            continue
        if isinstance(end_date, str):
            try:
                end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except Exception:
                continue
        phase = task.get("phase", "preparation")
        task_name = task.get("name", "未命名任务")

        # 延期预警：未完成且超过计划结束日期
        if status != "completed" and end_date < now:
            delay_days = (now - end_date).days
            if delay_days > 0:
                severity = _severity_from_delay(delay_days)
                alerts.append({
                    "task_id": task.get("id"),
                    "phase": phase,
                    "alert_type": "delay",
                    "severity": severity,
                    "message": f"「{task_name}」已延期 {delay_days} 天（计划完成：{end_date.date()}）",
                    "planned_date": end_date.isoformat(),
                    "actual_date": None,
                    "delay_days": delay_days,
                    "progress_percent": TASK_STATUS_PROGRESS.get(status, 0),
                    "suggestion": _build_delay_suggestion(phase, delay_days, severity),
                })
        # 风险预警：进行中且接近结束日期 3 天内
        elif status == "in_progress" and 0 <= (end_date - now).days <= 3:
            alerts.append({
                "task_id": task.get("id"),
                "phase": phase,
                "alert_type": "risk",
                "severity": "medium",
                "message": f"「{task_name}」即将到期（剩余 {(end_date - now).days} 天）",
                "planned_date": end_date.isoformat(),
                "actual_date": None,
                "delay_days": 0,
                "progress_percent": 50.0,
                "suggestion": f"建议加快「{task_name}」进度，必要时增派人手",
            })

    # 5. 里程碑跟踪
    milestone_list = milestones or PROJECT_MILESTONES
    milestone_status = []
    for ms in milestone_list:
        ms_code = ms.get("code") or ms.get("milestone_code")
        ms_phase = ms.get("phase", "preparation")
        ms_name = ms.get("name", ms_code)
        planned_percent = ms.get("planned_percent", 0.0)
        payment_ratio = ms.get("payment_ratio", 0.0)
        # 判定状态：依据整体进度
        if overall_progress >= planned_percent:
            ms_status = "completed"
            actual_percent = planned_percent
        elif overall_progress >= planned_percent - 10:
            ms_status = "in_progress"
            actual_percent = overall_progress
        else:
            ms_status = "pending"
            actual_percent = 0.0
        # 若整体进度 ≥ planned_percent - 5 但未达到，且 expected_progress < overall_progress，标记 delayed
        if ms_status != "completed" and expected_progress >= planned_percent and overall_progress < planned_percent:
            ms_status = "delayed"
        milestone_status.append({
            "milestone_code": ms_code,
            "name": ms_name,
            "phase": ms_phase,
            "planned_percent": planned_percent,
            "actual_percent": actual_percent,
            "status": ms_status,
            "payment_ratio": payment_ratio,
        })
        # 里程碑预警
        if ms_status == "delayed":
            alerts.append({
                "task_id": None,
                "phase": ms_phase,
                "alert_type": "milestone",
                "severity": "high",
                "message": f"里程碑「{ms_name}」应已完成但实际进度不足（期望 {planned_percent}%，实际 {overall_progress}%）",
                "planned_date": None,
                "actual_date": None,
                "delay_days": 0,
                "progress_percent": overall_progress,
                "suggestion": f"建议立即评估「{ms_name}」延期影响，调整后续工序排期",
            })

    # 6. 风险等级
    if any(a["severity"] == "critical" for a in alerts):
        risk_level = "critical"
    elif any(a["severity"] == "high" for a in alerts):
        risk_level = "high"
    elif any(a["severity"] == "medium" for a in alerts):
        risk_level = "medium"
    else:
        risk_level = "low"

    # 7. 汇总建议
    suggestions = []
    if progress_deviation < -10:
        suggestions.append(f"整体进度落后 {abs(progress_deviation)}%，建议立即排查瓶颈工序并采取赶工措施")
    elif progress_deviation < -5:
        suggestions.append(f"整体进度略落后 {abs(progress_deviation)}%，建议关注关键路径任务")
    elif progress_deviation > 10:
        suggestions.append(f"整体进度超前 {progress_deviation}%，可考虑提前安排后续工序")
    if any(a["alert_type"] == "delay" and a["severity"] in ("high", "critical") for a in alerts):
        suggestions.append("存在高危延期任务，建议召开进度协调会并调整资源分配")
    if not suggestions:
        suggestions.append("进度正常，建议继续保持")

    summary = (
        f"项目进度分析完成：整体完成 {overall_progress}%（期望 {expected_progress}%，偏差 {progress_deviation}%），"
        f"共 {len(alerts)} 条预警，风险等级：{risk_level}"
    )

    return {
        "project_id": project_id,
        "current_date": now,
        "overall_progress": overall_progress,
        "expected_progress": expected_progress,
        "progress_deviation": progress_deviation,
        "phase_status": phase_status,
        "alerts": alerts,
        "milestones": milestone_status,
        "risk_level": risk_level,
        "summary": summary,
        "suggestions": suggestions,
    }


def _build_delay_suggestion(phase: str, delay_days: int, severity: str) -> str:
    """根据阶段 + 延期天数生成整改建议"""
    phase_name = next((p["name"] for p in CONSTRUCTION_PHASES if p["code"] == phase), phase)
    if severity == "critical":
        return f"「{phase_name}」阶段严重延期 {delay_days} 天，建议立即增派人手或调整工序，必要时启用备用方案"
    if severity == "high":
        return f"「{phase_name}」阶段延期 {delay_days} 天，建议加快施工节奏并排查原因"
    if severity == "medium":
        return f"「{phase_name}」阶段轻度延期 {delay_days} 天，建议关注并适度加班赶工"
    return f"「{phase_name}」阶段略有延期 {delay_days} 天，建议留意"


# ── F38 AI 质量问题检测 ──

# 质量问题严重程度映射规则
SEVERITY_RULES = {
    # category → {fail_pattern → severity}
    "防水": {"fail": "critical", "warn": "high"},
    "电路": {"fail": "critical", "warn": "high"},
    "结构": {"fail": "critical", "warn": "high"},
    "空鼓": {"fail": "high", "warn": "medium"},
    "平整度": {"fail": "medium", "warn": "low"},
    "缝隙": {"fail": "medium", "warn": "low"},
    "油漆": {"fail": "medium", "warn": "low"},
    "安装": {"fail": "medium", "warn": "low"},
}

# 整改建议模板
RECTIFICATION_TEMPLATES = {
    "防水": "需重新做防水层，进行 48h 闭水试验合格后方可继续",
    "电路": "需重新布线/接线，进行绝缘测试和通电测试合格后方可继续",
    "结构": "需结构加固方案，由专业结构工程师评估并签字确认",
    "空鼓": "需拆除空鼓瓷砖/墙面重新施工，单砖空鼓率需 < 5%",
    "平整度": "需打磨/找平处理，2m 靠尺偏差需 ≤ {standard}mm",
    "缝隙": "需调整缝隙均匀度，建议返工至标准范围",
    "油漆": "需打磨返工，重新涂刷至无流坠、无色差",
    "安装": "需重新调整安装位置/紧固度，确保功能正常",
}


def detect_quality_issues(
    project_id: str,
    phase: str,
    inspection_results: list[dict],
    task_id: str | None = None,
    inspection_id: str | None = None,
) -> dict:
    """F38 AI 质量问题检测 — 基于质检结果自动识别质量问题

    输入：
    - project_id: 项目 ID
    - phase: 施工阶段
    - inspection_results: 质检结果列表，每项含 check_item, standard, ai_result, confidence, issues 等
    - task_id / inspection_id: 可选关联

    输出：
    - detected_issues: 检测到的质量问题列表
    - summary: 检测汇总
    - suggested_order: 建议生成的整改单
    """
    detected_issues = []
    checklist = QUALITY_CHECKLISTS.get(phase, [])

    # 1. 从 inspection_results 中提取失败项
    for result in inspection_results:
        ai_result = result.get("ai_result", "pass")
        if ai_result == "pass":
            continue
        check_item = result.get("check_item", "")
        standard = result.get("standard", "")
        confidence = result.get("confidence", 0.0)
        issues_list = result.get("issues", [])
        # 识别 category
        category = _classify_category(check_item)
        severity_rule = SEVERITY_RULES.get(category, {"fail": "medium", "warn": "low"})
        # 判定严重级别
        if ai_result == "fail":
            severity = severity_rule["fail"]
        else:
            severity = severity_rule["warn"]
        # 生成问题描述
        description = issues_list[0] if issues_list else f"「{check_item}」未达标，标准：{standard}"
        # 生成整改建议
        suggestion = RECTIFICATION_TEMPLATES.get(category, "建议返工至符合标准要求")
        if "{standard}" in suggestion:
            # 提取数值标准
            std_num = "".join(c for c in standard if c.isdigit() or c == ".")
            suggestion = suggestion.replace("{standard}", std_num or "3")

        detected_issues.append({
            "project_id": project_id,
            "task_id": task_id,
            "inspection_id": inspection_id,
            "phase": phase,
            "category": category,
            "description": description,
            "severity": severity,
            "detected_by": "ai",
            "standard": standard,
            "location": check_item,
            "confidence": confidence,
            "suggestion": suggestion,
        })

    # 2. 若 inspection_results 为空，则基于阶段 checklist 模拟检测
    if not inspection_results and checklist:
        for item in checklist:
            # Mock AI 检测：约 20% 概率不通过
            is_fail = (hash(item["item"]) % 10) >= 8
            if not is_fail:
                continue
            category = _classify_category(item["item"])
            severity_rule = SEVERITY_RULES.get(category, {"fail": "medium", "warn": "low"})
            severity = severity_rule["fail"]
            suggestion = RECTIFICATION_TEMPLATES.get(category, "建议返工至符合标准要求")
            if "{standard}" in suggestion:
                std_num = "".join(c for c in item["standard"] if c.isdigit() or c == ".")
                suggestion = suggestion.replace("{standard}", std_num or "3")
            detected_issues.append({
                "project_id": project_id,
                "task_id": task_id,
                "inspection_id": inspection_id,
                "phase": phase,
                "category": category,
                "description": f"AI 检测到「{item['item']}」未达标，标准：{item['standard']}",
                "severity": severity,
                "detected_by": "ai",
                "standard": item["standard"],
                "location": item["item"],
                "confidence": round(0.85 + (hash(item["item"]) % 15) / 100, 2),
                "suggestion": suggestion,
            })

    # 3. 汇总
    severity_count = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in detected_issues:
        severity_count[issue["severity"]] = severity_count.get(issue["severity"], 0) + 1

    # 4. 建议生成整改单
    suggested_order = None
    if detected_issues:
        # 按严重级别排序，取最高级别作为优先级
        if severity_count["critical"] > 0:
            priority = "urgent"
        elif severity_count["high"] > 0:
            priority = "high"
        elif severity_count["medium"] > 0:
            priority = "medium"
        else:
            priority = "low"
        phase_name = next((p["name"] for p in CONSTRUCTION_PHASES if p["code"] == phase), phase)
        suggested_order = {
            "project_id": project_id,
            "title": f"{phase_name}阶段质量问题整改单",
            "description": (
                f"AI 自动检测到 {len(detected_issues)} 项质量问题"
                f"（严重 {severity_count['critical']}，高 {severity_count['high']}，"
                f"中 {severity_count['medium']}，低 {severity_count['low']}）"
            ),
            "phase": phase,
            "priority": priority,
            "cost": _estimate_rectification_cost(detected_issues),
            "notes": "由 AI 质量检测自动生成",
        }

    summary = (
        f"AI 质量问题检测完成：{phase} 阶段共检测到 {len(detected_issues)} 项质量问题"
        f"（严重 {severity_count['critical']}，高 {severity_count['high']}，"
        f"中 {severity_count['medium']}，低 {severity_count['low']}）"
    )

    return {
        "project_id": project_id,
        "phase": phase,
        "detected_issues": detected_issues,
        "severity_count": severity_count,
        "summary": summary,
        "suggested_order": suggested_order,
    }


def _classify_category(check_item: str) -> str:
    """根据检查项名称识别问题类别"""
    if any(kw in check_item for kw in ["防水", "闭水", "蓄水", "渗漏", "水管", "打压"]):
        return "防水"
    if any(kw in check_item for kw in ["电路", "绝缘", "接线", "强弱电", "插座", "开关"]):
        return "电路"
    if any(kw in check_item for kw in ["结构", "承重", "墙体"]):
        return "结构"
    if any(kw in check_item for kw in ["空鼓"]):
        return "空鼓"
    if any(kw in check_item for kw in ["平整度", "靠尺", "方正度", "顺直"]):
        return "平整度"
    if any(kw in check_item for kw in ["缝隙", "缝隙", "对角线"]):
        return "缝隙"
    if any(kw in check_item for kw in ["油漆", "色差", "流坠", "漏刷", "壁纸"]):
        return "油漆"
    if any(kw in check_item for kw in ["安装", "牢固", "滑轨", "下水", "灯具"]):
        return "安装"
    return "其他"


def _estimate_rectification_cost(issues: list[dict]) -> float:
    """根据问题数量 + 严重级别估算整改成本"""
    cost_map = {"critical": 2000.0, "high": 800.0, "medium": 300.0, "low": 100.0}
    total = 0.0
    for issue in issues:
        total += cost_map.get(issue["severity"], 200.0)
    return round(total, 2)
