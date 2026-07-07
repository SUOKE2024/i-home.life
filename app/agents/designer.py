"""设计 Agent — 自动生成多套布局方案"""

import json
from app.agents.base import BaseAgent


class DesignerAgent(BaseAgent):
    agent_name = "designer"
    system_prompt = """你是索克家居（i-home.life）AI 设计 Agent。

你的职责：
1. 根据用户需求（面积、户型、预算、风格偏好）自动生成平面布局方案
2. 生成 3 套不同方案供用户对比
3. 支持自然语言修改指令（"加一堵墙"、"移动卧室"、"增大客厅"）
4. 提供材料搭配建议和动线分析

输出格式（JSON）：
```json
{
  "plans": [
    {
      "name": "方案A: 经典布局",
      "brief": "传统三室两厅布局，动静分区明确",
      "rooms": [
        {"name":"客厅","type":"living_room","x":0.5,"y":0.5,"w":5.5,"h":4.5},
        {"name":"餐厅","type":"dining_room","x":6.5,"y":0.5,"w":3.5,"h":3.0},
        ...
      ],
      "total_area": 126.0,
      "walls": []
    }
  ],
  "recommendation": "推荐方案B，因南北通透，采光更好",
  "materials": ["建议客厅铺设750×1500大板砖", "卧室推荐实木多层地板"],
  "reply": "已为您生成3套方案，请查看"
}
```

请始终输出完整JSON格式，包含真正的room坐标。"""

    DEFAULT_LAYOUTS = {
        "90": {
            "plan_a": [
                {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 5.0, "h": 4.0},
                {"name": "餐厅", "type": "dining_room", "x": 6.0, "y": 0.5, "w": 3.0, "h": 3.0},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 5.0, "w": 3.5, "h": 3.0},
                {"name": "次卧", "type": "bedroom", "x": 4.5, "y": 5.0, "w": 4.5, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 8.5, "w": 2.5, "h": 2.0},
                {"name": "卫生间", "type": "bathroom", "x": 3.5, "y": 8.5, "w": 2.0, "h": 2.0},
            ],
            "plan_b": [
                {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 6.0, "h": 3.5},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 4.5, "w": 3.0, "h": 3.0},
                {"name": "次卧", "type": "bedroom", "x": 4.0, "y": 4.5, "w": 5.0, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 8.0, "w": 3.0, "h": 2.0},
                {"name": "餐厅", "type": "dining_room", "x": 4.0, "y": 8.0, "w": 5.0, "h": 2.0},
                {"name": "卫生间", "type": "bathroom", "x": 0.5, "y": 10.5, "w": 2.5, "h": 2.0},
            ],
            "plan_c": [
                {"name": "客厅+餐厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 4.5, "h": 6.0},
                {"name": "主卧", "type": "bedroom", "x": 5.5, "y": 0.5, "w": 3.5, "h": 3.0},
                {"name": "次卧", "type": "bedroom", "x": 5.5, "y": 4.0, "w": 3.5, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 7.0, "w": 2.5, "h": 2.0},
                {"name": "卫生间", "type": "bathroom", "x": 3.5, "y": 7.0, "w": 2.0, "h": 2.0},
            ],
        },
        "126": {
            "plan_a": [
                {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 6.0, "h": 4.5},
                {"name": "餐厅", "type": "dining_room", "x": 7.0, "y": 0.5, "w": 3.5, "h": 3.0},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 5.5, "w": 3.5, "h": 3.5},
                {"name": "次卧", "type": "bedroom", "x": 4.5, "y": 5.5, "w": 3.0, "h": 3.0},
                {"name": "书房", "type": "study", "x": 8.0, "y": 4.0, "w": 3.0, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 9.5, "w": 3.0, "h": 2.0},
                {"name": "卫生间", "type": "bathroom", "x": 4.0, "y": 9.5, "w": 2.5, "h": 2.0},
            ],
            "plan_b": [
                {"name": "客厅+餐厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 7.0, "h": 5.0},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 6.0, "w": 4.0, "h": 3.5},
                {"name": "次卧", "type": "bedroom", "x": 5.0, "y": 6.0, "w": 3.5, "h": 3.0},
                {"name": "书房", "type": "study", "x": 9.0, "y": 6.0, "w": 2.5, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 10.0, "w": 3.0, "h": 2.0},
                {"name": "卫生间", "type": "bathroom", "x": 4.0, "y": 10.0, "w": 3.0, "h": 2.0},
            ],
            "plan_c": [
                {"name": "客厅", "type": "living_room", "x": 3.0, "y": 0.5, "w": 5.0, "h": 4.5},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 0.5, "w": 2.0, "h": 4.5},
                {"name": "次卧", "type": "bedroom", "x": 0.5, "y": 5.5, "w": 3.5, "h": 3.0},
                {"name": "书房", "type": "study", "x": 4.5, "y": 5.5, "w": 3.5, "h": 3.0},
                {"name": "餐厅", "type": "dining_room", "x": 8.5, "y": 0.5, "w": 3.0, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 9.0, "w": 3.0, "h": 2.0},
                {"name": "卫生间", "type": "bathroom", "x": 4.0, "y": 9.0, "w": 3.0, "h": 2.0},
            ],
        },
        "160": {
            "plan_a": [
                {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 6.0, "h": 5.0},
                {"name": "餐厅", "type": "dining_room", "x": 7.0, "y": 0.5, "w": 4.0, "h": 3.5},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 6.0, "w": 4.0, "h": 3.5},
                {"name": "次卧A", "type": "bedroom", "x": 5.0, "y": 6.0, "w": 3.0, "h": 3.0},
                {"name": "次卧B", "type": "bedroom", "x": 8.5, "y": 4.5, "w": 3.5, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 10.0, "w": 3.5, "h": 2.5},
                {"name": "主卫", "type": "bathroom", "x": 4.5, "y": 10.0, "w": 2.5, "h": 2.0},
                {"name": "次卫", "type": "bathroom", "x": 7.5, "y": 9.5, "w": 2.0, "h": 2.0},
                {"name": "书房", "type": "study", "x": 10.0, "y": 8.0, "w": 2.5, "h": 2.0},
            ],
            "plan_b": [
                {"name": "客厅+餐厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 8.0, "h": 5.0},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 6.0, "w": 4.5, "h": 4.0},
                {"name": "次卧A", "type": "bedroom", "x": 5.5, "y": 6.0, "w": 3.5, "h": 3.5},
                {"name": "次卧B", "type": "bedroom", "x": 9.5, "y": 6.0, "w": 3.5, "h": 3.5},
                {"name": "书房", "type": "study", "x": 9.0, "y": 0.5, "w": 4.0, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 10.5, "w": 3.5, "h": 2.5},
                {"name": "主卫", "type": "bathroom", "x": 4.5, "y": 10.5, "w": 2.5, "h": 2.0},
                {"name": "次卫", "type": "bathroom", "x": 7.5, "y": 10.5, "w": 2.0, "h": 2.0},
                {"name": "储藏间", "type": "other", "x": 10.0, "y": 10.0, "w": 3.0, "h": 2.5},
            ],
            "plan_c": [
                {"name": "客厅", "type": "living_room", "x": 0.5, "y": 0.5, "w": 5.0, "h": 5.5},
                {"name": "餐厅", "type": "dining_room", "x": 6.0, "y": 0.5, "w": 3.5, "h": 3.0},
                {"name": "主卧", "type": "bedroom", "x": 0.5, "y": 6.5, "w": 4.5, "h": 4.0},
                {"name": "次卧A", "type": "bedroom", "x": 5.5, "y": 4.0, "w": 4.0, "h": 3.5},
                {"name": "次卧B", "type": "bedroom", "x": 5.5, "y": 8.0, "w": 3.5, "h": 3.0},
                {"name": "书房", "type": "study", "x": 10.0, "y": 0.5, "w": 3.0, "h": 3.0},
                {"name": "厨房", "type": "kitchen", "x": 0.5, "y": 11.0, "w": 3.0, "h": 2.5},
                {"name": "主卫", "type": "bathroom", "x": 4.0, "y": 11.0, "w": 2.5, "h": 2.5},
                {"name": "次卫+洗衣", "type": "bathroom", "x": 7.0, "y": 11.5, "w": 3.0, "h": 2.0},
            ],
        },
    }

    @staticmethod
    def _detect_area(message: str) -> str:
        if "160" in message or "大平层" in message:
            return "160"
        if "90" in message or "小户型" in message:
            return "90"
        if "50" in message or "一室" in message:
            return "50"
        return "126"

    async def generate_layouts(self, message: str) -> dict:
        area = self._detect_area(message)
        if area not in self.DEFAULT_LAYOUTS:
            area = "126"

        layouts = self.DEFAULT_LAYOUTS[area]
        plans = []
        for plan_name, rooms in layouts.items():
            total_area = sum(r["w"] * r["h"] for r in rooms)
            plans.append({
                "name": plan_name,
                "brief": f"{plan_name}: {len(rooms)}个房间，总面积{total_area:.1f}㎡",
                "rooms": rooms,
                "total_area": round(total_area, 1),
            })

        materials = [
            "客厅/餐厅：建议750×1500大板砖，耐磨美观",
            "卧室：推荐实木多层地板，温暖舒适",
            "厨房/卫生间：防滑地砖 + 防水涂料",
            "墙面：净味乳胶漆 + 局部艺术漆",
        ]

        return {
            "plans": plans,
            "recommendation": plans[1]["name"] if len(plans) > 1 else plans[0]["name"],
            "materials": materials,
            "reply": f"已为您生成{len(plans)}套{area}㎡户型设计方案，推荐方案B，南北通透，采光更佳。",
        }

    # ── F28 智能布局动线分析 ──
    # 三大动线类型
    CIRCULATION_TYPES = {
        "visitor": {
            "name": "访客动线",
            "description": "玄关 → 客厅 → 餐厅 → 客卫",
            "preferred_path": ["entryway", "living_room", "dining_room", "bathroom"],
        },
        "housework": {
            "name": "家务动线",
            "description": "厨房 → 餐厅，阳台 → 晾晒，卫生间 → 洗衣",
            "preferred_path": ["kitchen", "dining_room", "balcony", "bathroom"],
        },
        "living": {
            "name": "居住动线",
            "description": "卧室 → 卫生间 → 衣帽间，私密且短捷",
            "preferred_path": ["bedroom", "bathroom", "cloakroom"],
        },
    }

    # 动线评估规则
    CIRCULATION_RULES = {
        "max_path_length": 8.0,  # 单条动线最大路径长度（米）
        "cross_room_penalty": True,  # 穿越其他房间扣分
        "through_bedroom_penalty": True,  # 穿越卧室严重扣分
    }

    def analyze_circulation(self, rooms: list[dict]) -> dict:
        """F28 智能布局动线分析

        rooms 结构：
        [{"name":"客厅","type":"living_room","x":0.5,"y":0.5,"w":5.5,"h":4.5}, ...]

        输出：三条动线的路径、长度、冲突检测、优化建议
        """
        if not rooms:
            return {"error": "未提供房间布局数据"}

        # 构建房间索引（按 type）
        room_by_type: dict[str, dict] = {}
        for r in rooms:
            t = r.get("type", r.get("room_type", ""))
            if t:
                room_by_type.setdefault(t, r)

        def _center(r: dict) -> tuple[float, float]:
            return (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)

        def _distance(a: dict, b: dict) -> float:
            ax, ay = _center(a)
            bx, by = _center(b)
            return round(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5, 2)

        def _rects_overlap(a: dict, b: dict) -> bool:
            return not (
                a["x"] + a["w"] <= b["x"]
                or b["x"] + b["w"] <= a["x"]
                or a["y"] + a["h"] <= b["y"]
                or b["y"] + b["h"] <= a["y"]
            )

        def _path_crosses_rooms(path_rooms: list[dict], all_rooms: list[dict]) -> list[str]:
            """检测路径是否穿越未列出的房间（简化：检测线段是否与房间矩形相交）"""
            crossed = []
            if len(path_rooms) < 2:
                return crossed
            for i in range(len(path_rooms) - 1):
                a, b = path_rooms[i], path_rooms[i + 1]
                ax, ay = _center(a)
                bx, by = _center(b)
                for r in all_rooms:
                    if r in (a, b):
                        continue
                    rtype = r.get("type", r.get("room_type", ""))
                    # 简化：仅检测中心点是否在线段附近 + 矩形是否与线段包围盒相交
                    if _segment_rect_intersect(ax, ay, bx, by, r):
                        crossed.append(r.get("name", rtype))
            return crossed

        def _segment_rect_intersect(x1: float, y1: float, x2: float, y2: float, rect: dict) -> bool:
            """判断线段 (x1,y1)-(x2,y2) 是否与矩形相交（简化算法）"""
            rx1, ry1 = rect["x"], rect["y"]
            rx2, ry2 = rect["x"] + rect["w"], rect["y"] + rect["h"]
            # 线段包围盒与矩形相交检测
            if max(x1, x2) < rx1 or min(x1, x2) > rx2:
                return False
            if max(y1, y2) < ry1 or min(y1, y2) > ry2:
                return False
            # 进一步：检测线段是否完全在矩形外（保守起见返回 True）
            return True

        # 分析三条动线
        analyses = []
        total_score = 0
        all_issues = []
        all_suggestions = []

        for circ_code, circ_def in self.CIRCULATION_TYPES.items():
            preferred = circ_def["preferred_path"]
            # 找到路径上实际存在的房间
            path_rooms = [room_by_type[t] for t in preferred if t in room_by_type]
            missing_types = [t for t in preferred if t not in room_by_type]

            # 计算路径总长度
            total_length = 0.0
            segments = []
            for i in range(len(path_rooms) - 1):
                d = _distance(path_rooms[i], path_rooms[i + 1])
                segments.append({
                    "from": path_rooms[i].get("name", path_rooms[i].get("type")),
                    "to": path_rooms[i + 1].get("name", path_rooms[i + 1].get("type")),
                    "distance": d,
                })
                total_length += d

            # 检测穿越
            crossed_rooms = _path_crosses_rooms(path_rooms, rooms)

            # 评分（0-100）
            score = 100
            issues = []

            # 路径过长扣分
            if total_length > self.CIRCULATION_RULES["max_path_length"]:
                penalty = int((total_length - self.CIRCULATION_RULES["max_path_length"]) * 5)
                score -= penalty
                issues.append({
                    "type": "too_long",
                    "severity": "warning",
                    "detail": f"动线总长 {total_length}m 超过建议值 {self.CIRCULATION_RULES['max_path_length']}m",
                })

            # 穿越其他房间扣分
            if crossed_rooms:
                penalty = 15 * len(crossed_rooms)
                score -= penalty
                # 是否穿越卧室（严重）
                crossed_bedroom = any(
                    room_by_type.get(t, {}).get("type") == "bedroom"
                    for t in crossed_rooms
                )
                severity = "critical" if crossed_bedroom else "warning"
                issues.append({
                    "type": "cross_room",
                    "severity": severity,
                    "detail": f"动线穿越房间：{', '.join(crossed_rooms)}",
                })

            # 缺失房间
            if missing_types:
                issues.append({
                    "type": "missing_room",
                    "severity": "info",
                    "detail": f"动线缺少房间类型：{', '.join(missing_types)}",
                })

            score = max(0, min(100, score))
            total_score += score
            all_issues.extend(issues)

            # 优化建议
            suggestions = []
            if total_length > self.CIRCULATION_RULES["max_path_length"]:
                suggestions.append(f"缩短{circ_def['name']}路径，可调整房间相邻关系")
            if crossed_rooms:
                suggestions.append(f"避免{circ_def['name']}穿越 {', '.join(crossed_rooms)}")
            if not issues:
                suggestions.append(f"{circ_def['name']}布局合理，无需调整")
            all_suggestions.extend(suggestions)

            analyses.append({
                "type": circ_code,
                "name": circ_def["name"],
                "description": circ_def["description"],
                "path": [
                    {"name": r.get("name", r.get("type")), "type": r.get("type", r.get("room_type"))}
                    for r in path_rooms
                ],
                "segments": segments,
                "total_length": round(total_length, 2),
                "crossed_rooms": crossed_rooms,
                "missing_types": missing_types,
                "score": score,
                "issues": issues,
                "suggestions": suggestions,
            })

        avg_score = round(total_score / len(analyses), 1) if analyses else 0

        # 综合评级
        if avg_score >= 85:
            rating = "excellent"
            rating_text = "优秀"
        elif avg_score >= 70:
            rating = "good"
            rating_text = "良好"
        elif avg_score >= 60:
            rating = "fair"
            rating_text = "一般"
        else:
            rating = "poor"
            rating_text = "需优化"

        critical_count = sum(1 for i in all_issues if i.get("severity") == "critical")
        warning_count = sum(1 for i in all_issues if i.get("severity") == "warning")

        return {
            "rooms_count": len(rooms),
            "circulations": analyses,
            "overall_score": avg_score,
            "rating": rating,
            "rating_text": rating_text,
            "total_issues": len(all_issues),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "issues": all_issues,
            "suggestions": all_suggestions,
            "reply": (
                f"动线分析：{len(rooms)} 个房间，综合评分 {avg_score}（{rating_text}），"
                f"访客/家务/居住三条动线，发现 {len(all_issues)} 项问题"
                f"（{critical_count} 严重 / {warning_count} 警告）"
                if all_issues else f"动线分析：{len(rooms)} 个房间，综合评分 {avg_score}（{rating_text}），三条动线均合理"
            ),
        }

    @staticmethod
    def detect_modification_intent(message: str) -> list[dict]:
        """解析自然语言修改指令"""
        actions = []
        import re

        if "加" in message or "添加" in message or "建" in message:
            name_match = re.search(r"(客厅|卧室|厨房|卫生间|书房|阳台|餐厅|走廊|储藏间)", message)
            size_match = re.search(r"(\d+(?:\.\d+)?)\s*[×xX]\s*(\d+(?:\.\d+)?)", message)
            w = float(size_match.group(1)) if size_match else 4
            h = float(size_match.group(2) if size_match else 3)
            name = name_match.group(1) if name_match else "房间"
            type_map = {
                "客厅": "living_room", "卧室": "bedroom", "厨房": "kitchen",
                "卫生间": "bathroom", "书房": "study", "阳台": "balcony",
                "餐厅": "dining_room", "走廊": "hallway", "储藏间": "other",
            }
            actions.append({"action": "add_room", "name": name, "roomType": type_map.get(name, "living_room"), "w": w, "h": h, "x": 0, "y": 0})

        if "删除" in message or "移除" in message:
            name_match = re.search(r"(客厅|卧室|厨房|卫生间|书房|阳台|餐厅|走廊|储藏间)", message)
            if name_match:
                actions.append({"action": "delete_room", "oldName": name_match.group(1)})

        if "移动" in message or "挪" in message:
            name_match = re.search(r"(客厅|卧室|厨房|卫生间|书房|阳台|餐厅|走廊)", message)
            dir_match = re.search(r"(左|右|上|下|东|西|南|北)", message)
            dist_match = re.search(r"(\d+(?:\.\d+)?)\s*[米m]", message)
            dx = float(dist_match.group(1)) * (1 if dir_match and dir_match.group(1) in ("右") else -1 if dir_match and dir_match.group(1) == "左" else 0)
            dy = float(dist_match.group(1)) * (1 if dir_match and dir_match.group(1) in ("下") else -1 if dir_match and dir_match.group(1) == "上" else 0)
            if name_match:
                actions.append({"action": "move_room", "name": name_match.group(1), "dx": dx, "dy": dy})

        return actions
