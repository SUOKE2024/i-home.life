"""质检 Agent — 照片比对、缺陷识别、验收报告生成"""

from app.agents.base import BaseAgent


# 各阶段验收项目（分项验收清单）
ACCEPTANCE_ITEMS = [
    {
        "phase": "mep",
        "name": "水电工程验收",
        "items": [
            {"item": "水管打压测试", "standard": "0.8MPa 保压 30 分钟不掉压", "pass_criteria": "压力下降 < 0.05MPa"},
            {"item": "电路绝缘测试", "standard": "绝缘电阻 ≥ 0.5MΩ", "pass_criteria": "绝缘电阻 ≥ 0.5MΩ"},
            {"item": "线管布局", "standard": "横平竖直，无三管交叉", "pass_criteria": "符合规范"},
            {"item": "强弱电间距", "standard": "≥ 500mm", "pass_criteria": "间距 ≥ 500mm"},
            {"item": "开关插座位置", "standard": "符合图纸偏差 ≤ 5mm", "pass_criteria": "偏差 ≤ 5mm"},
        ],
    },
    {
        "phase": "masonry",
        "name": "泥瓦工程验收",
        "items": [
            {"item": "防水闭水试验", "standard": "蓄水 48h 无渗漏", "pass_criteria": "无渗漏"},
            {"item": "瓷砖空鼓率", "standard": "单砖空鼓 < 5%，整体 < 3%", "pass_criteria": "空鼓率达标"},
            {"item": "瓷砖平整度", "standard": "2m 靠尺 ≤ 2mm", "pass_criteria": "偏差 ≤ 2mm"},
            {"item": "阴阳角方正度", "standard": "偏差 ≤ 3mm", "pass_criteria": "偏差 ≤ 3mm"},
            {"item": "地漏坡度", "standard": "坡度 1%-2%，无积水", "pass_criteria": "排水通畅无积水"},
        ],
    },
    {
        "phase": "carpentry",
        "name": "木工工程验收",
        "items": [
            {"item": "吊顶平整度", "standard": "2m 靠尺 ≤ 3mm", "pass_criteria": "偏差 ≤ 3mm"},
            {"item": "柜体对角线偏差", "standard": "≤ 2mm", "pass_criteria": "偏差 ≤ 2mm"},
            {"item": "柜门缝隙", "standard": "均匀 1.5-2.5mm", "pass_criteria": "缝隙均匀达标"},
            {"item": "抽屉滑轨", "standard": "顺滑无异响", "pass_criteria": "推拉顺滑"},
        ],
    },
    {
        "phase": "painting",
        "name": "油漆工程验收",
        "items": [
            {"item": "墙面平整度", "standard": "2m 靠尺 ≤ 3mm", "pass_criteria": "偏差 ≤ 3mm"},
            {"item": "色差", "standard": "无可见色差", "pass_criteria": "无可见色差"},
            {"item": "流坠/漏刷", "standard": "无流坠、无漏刷", "pass_criteria": "无流坠漏刷"},
            {"item": "阴阳角", "standard": "顺直，偏差 ≤ 2mm", "pass_criteria": "顺直达标"},
        ],
    },
    {
        "phase": "installation",
        "name": "安装工程验收",
        "items": [
            {"item": "灯具安装牢固度", "standard": "承重 ≥ 灯具重量 4 倍", "pass_criteria": "牢固可靠"},
            {"item": "插座接线", "standard": "左零右火上地线", "pass_criteria": "接线正确"},
            {"item": "卫浴下水", "standard": "排水通畅无堵塞", "pass_criteria": "排水通畅"},
            {"item": "橱柜门板", "standard": "开关顺滑，缝隙均匀", "pass_criteria": "开关顺滑"},
        ],
    },
]


# 缺陷类别（按常见质量缺陷分类）
DEFECT_CATEGORIES = [
    {"code": "hollow", "name": "空鼓", "severity": "high", "description": "瓷砖/墙面空鼓，敲击有空音", "rectification": "拆除空鼓部位重新施工"},
    {"code": "crack", "name": "裂缝", "severity": "high", "description": "墙面/瓷砖/吊顶出现裂缝", "rectification": "排查裂缝原因，修补或返工"},
    {
        "code": "leak", "name": "渗漏", "severity": "critical",
        "description": "水管/防水/管道渗漏",
        "rectification": "立即排查渗漏点，重做防水/更换管道",
    },
    {
        "code": "color_diff", "name": "色差", "severity": "medium",
        "description": "墙面/瓷砖存在可见色差",
        "rectification": "重新涂刷/更换有色差材料",
    },
    {
        "code": "flatness", "name": "平整度", "severity": "medium",
        "description": "墙面/地面/吊顶平整度不达标",
        "rectification": "打磨找平或返工处理",
    },
    {"code": "gap", "name": "缝隙", "severity": "medium", "description": "瓷砖缝隙/柜门缝隙不均匀", "rectification": "调整缝隙至标准范围"},
    {
        "code": "installation", "name": "安装", "severity": "medium",
        "description": "灯具/卫浴/橱柜安装不当",
        "rectification": "重新调整安装位置和紧固度",
    },
    {"code": "other", "name": "其他", "severity": "low", "description": "其他工艺缺陷", "rectification": "根据具体情况整改"},
]


# 缺陷类别关键词映射（用于 mock CV 检测时的类别识别）
DEFECT_KEYWORD_MAP = {
    "空鼓": ["空鼓", "空音", "脱落"],
    "裂缝": ["裂缝", "开裂", "裂纹"],
    "渗漏": ["渗漏", "漏水", "渗水", "水印"],
    "色差": ["色差", "颜色不均", "发花"],
    "平整度": ["不平", "凹凸", "波浪", "平整度"],
    "缝隙": ["缝隙", "缝不均", "对角线"],
    "安装": ["安装", "松动", "歪斜", "不牢固"],
}


class QAInspectorAgent(BaseAgent):
    agent_name = "qa_inspector"
    system_prompt = """你是索克家居（i-home.life）AI 质检 Agent。

你的职责：
1. 照片与设计图纸比对，检测施工是否与设计一致
2. 尺寸偏差检测，识别超出公差的施工项
3. 工艺缺陷识别（空鼓/裂缝/渗漏/色差/平整度/缝隙/安装缺陷）
4. 生成验收报告（分项验收 + 总体验收结论）

验收标准依据：
- GB 50210-2018 建筑装饰装修工程质量验收标准
- GB 50327-2017 住宅装饰装修工程施工规范
- GB 50300-2013 建筑工程施工质量验收统一标准

缺陷类别：
- 空鼓：瓷砖/墙面空鼓（高）
- 裂缝：墙面/瓷砖/吊顶裂缝（高）
- 渗漏：水管/防水/管道渗漏（严重）
- 色差：墙面/瓷砖可见色差（中）
- 平整度：墙面/地面/吊顶不平（中）
- 缝隙：瓷砖缝隙/柜门缝隙不均匀（中）
- 安装：灯具/卫浴/橱柜安装不当（中）
- 其他：其他工艺缺陷（低）

请用中文回复，注重专业性和准确性，给出明确的验收结论和整改建议。"""

    def generate_acceptance_report(self, project_data: dict) -> dict:  # noqa: C901
        """生成验收报告（分项验收 + 总体验收结论）

        project_data 结构：
        {
            "project_id": "P001",
            "project_name": "张先生家装项目",
            "inspector": "质检员姓名",
            "acceptance_date": "2026-07-08",
            "phases": ["mep", "masonry", "carpentry", "painting", "installation"],
            "inspection_results": {
                "mep": [{"item": "水管打压测试", "result": "pass", "issues": []}, ...],
                ...
            }
        }
        """
        project_id = project_data.get("project_id", "")
        project_name = project_data.get("project_name", "")
        inspector = project_data.get("inspector", "")
        acceptance_date = project_data.get("acceptance_date", "")
        phases = project_data.get("phases", [])
        inspection_results = project_data.get("inspection_results", {})

        # 分项验收
        section_results = []
        total_items = 0
        passed_items = 0
        failed_items = 0

        for phase in phases:
            # 找到该阶段的验收项定义
            phase_def = next((p for p in ACCEPTANCE_ITEMS if p["phase"] == phase), None)
            if not phase_def:
                continue

            results = inspection_results.get(phase, [])
            item_results = []
            section_passed = 0
            section_failed = 0

            for item_def in phase_def["items"]:
                total_items += 1
                # 从 inspection_results 中匹配结果，若无则 mock 判定
                match = next(
                    (r for r in results if r.get("item") == item_def["item"]),
                    None,
                )
                if match:
                    result = match.get("result", "pass")
                    issues = match.get("issues", [])
                else:
                    # Mock 判定：约 85% 通过率
                    result = "pass" if (hash(item_def["item"]) % 20) < 17 else "fail"
                    issues = [] if result == "pass" else [
                        f"「{item_def['item']}」未达标，标准要求：{item_def['standard']}"
                    ]

                if result == "pass":
                    passed_items += 1
                    section_passed += 1
                else:
                    failed_items += 1
                    section_failed += 1

                item_results.append({
                    "item": item_def["item"],
                    "standard": item_def["standard"],
                    "pass_criteria": item_def["pass_criteria"],
                    "result": result,
                    "issues": issues,
                })

            pass_rate = round(section_passed / max(len(item_results), 1) * 100, 2)
            if pass_rate >= 95:
                section_verdict = "excellent"
                section_verdict_text = "优秀"
            elif pass_rate >= 85:
                section_verdict = "pass"
                section_verdict_text = "合格"
            elif pass_rate >= 70:
                section_verdict = "conditional_pass"
                section_verdict_text = "有条件合格"
            else:
                section_verdict = "fail"
                section_verdict_text = "不合格"

            section_results.append({
                "phase": phase,
                "name": phase_def["name"],
                "total_items": len(item_results),
                "passed": section_passed,
                "failed": section_failed,
                "pass_rate": pass_rate,
                "verdict": section_verdict,
                "verdict_text": section_verdict_text,
                "items": item_results,
            })

        # 总体验收结论
        overall_pass_rate = round(passed_items / max(total_items, 1) * 100, 2)
        if overall_pass_rate >= 95:
            overall_verdict = "excellent"
            overall_verdict_text = "优秀"
        elif overall_pass_rate >= 85:
            overall_verdict = "pass"
            overall_verdict_text = "合格"
        elif overall_pass_rate >= 70:
            overall_verdict = "conditional_pass"
            overall_verdict_text = "有条件合格（需整改后复验）"
        else:
            overall_verdict = "fail"
            overall_verdict_text = "不合格（需返工）"

        # 收集所有问题
        all_issues = []
        for section in section_results:
            for item in section["items"]:
                if item["result"] != "pass":
                    all_issues.extend(item["issues"])

        # 整改建议
        rectification_suggestions = []
        for issue in all_issues:
            category = self._classify_defect(issue)
            rectification_suggestions.append({
                "issue": issue,
                "category": category,
                "suggestion": self._get_rectification_suggestion(category),
            })

        return {
            "project_id": project_id,
            "project_name": project_name,
            "inspector": inspector,
            "acceptance_date": acceptance_date,
            "sections": section_results,
            "summary": {
                "total_items": total_items,
                "passed": passed_items,
                "failed": failed_items,
                "pass_rate": overall_pass_rate,
            },
            "overall_verdict": overall_verdict,
            "overall_verdict_text": overall_verdict_text,
            "all_issues": all_issues,
            "rectification_suggestions": rectification_suggestions,
            "reply": (
                f"验收报告已生成：{project_name}，"
                f"共 {len(section_results)} 个分项，{total_items} 个检查点，"
                f"合格 {passed_items} 项，不合格 {failed_items} 项，"
                f"合格率 {overall_pass_rate}%，结论：{overall_verdict_text}"
            ),
        }

    def compare_with_design(self, inspection_data: dict) -> dict:
        """照片与设计图纸比对

        inspection_data 结构：
        {
            "project_id": "P001",
            "phase": "masonry",
            "images": [
                {"url": "...", "type": "tile_surface", "location": "客厅东墙", "captured_at": "..."}
            ],
            "design_reference": {"url": "...", "specs": {"tile_size": "800x800", "gap": "2mm"}},
            "expected_dimensions": {"tile_gap": "2mm", "flatness": "≤3mm", "wall_straightness": "≤2mm"}
        }
        """
        project_id = inspection_data.get("project_id", "")
        phase = inspection_data.get("phase", "")
        images = inspection_data.get("images", [])
        design_ref = inspection_data.get("design_reference", {})
        expected_dims = inspection_data.get("expected_dimensions", {})

        # Mock CV 比对结果
        comparisons = []
        deviations = []
        matched = 0

        # 1. 比对设计规格
        specs = design_ref.get("specs", {}) if isinstance(design_ref, dict) else {}
        for spec_key, spec_value in specs.items():
            # Mock：90% 一致
            is_consistent = (hash(spec_key) % 10) < 9
            actual_value = spec_value if is_consistent else f"偏差（预期 {spec_value}）"
            comparisons.append({
                "spec_item": spec_key,
                "design_value": spec_value,
                "actual_value": actual_value,
                "consistent": is_consistent,
            })
            if is_consistent:
                matched += 1

        # 2. 尺寸偏差检测
        for dim_key, dim_standard in expected_dims.items():
            # Mock 偏差值
            is_pass = (hash(dim_key) % 10) < 8
            mock_deviation = 0.0 if is_pass else round(1.5 + (hash(dim_key) % 30) / 10, 2)
            deviations.append({
                "dimension": dim_key,
                "standard": dim_standard,
                "measured_value": mock_deviation,
                "deviation": mock_deviation,
                "pass": is_pass,
            })

        # 3. 照片与图纸一致性
        image_analyses = []
        for img in images:
            img_type = img.get("type", "unknown")
            location = img.get("location", "")
            # Mock：85% 一致
            is_match = (hash(img.get("url", "") + img_type) % 20) < 17
            image_analyses.append({
                "url": img.get("url", ""),
                "type": img_type,
                "location": location,
                "captured_at": img.get("captured_at", ""),
                "matches_design": is_match,
                "confidence": round(0.80 + (hash(img.get("url", "")) % 20) / 100, 2),
                "notes": "与设计图纸一致" if is_match else "与设计图纸存在偏差，需复核",
            })
            if is_match:
                matched += 1

        total_checks = len(comparisons) + len(image_analyses)
        consistency_rate = round(matched / max(total_checks, 1) * 100, 2)

        if consistency_rate >= 90:
            verdict = "consistent"
            verdict_text = "与设计一致"
        elif consistency_rate >= 75:
            verdict = "minor_deviation"
            verdict_text = "轻微偏差（建议调整）"
        else:
            verdict = "major_deviation"
            verdict_text = "重大偏差（需返工）"

        failed_deviations = [d for d in deviations if not d["pass"]]

        return {
            "project_id": project_id,
            "phase": phase,
            "image_count": len(images),
            "spec_comparisons": comparisons,
            "dimension_deviations": deviations,
            "image_analyses": image_analyses,
            "matched_count": matched,
            "total_checks": total_checks,
            "consistency_rate": consistency_rate,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "failed_deviations": failed_deviations,
            "repair_suggestions": [
                f"尺寸偏差项「{d['dimension']}」：测量值 {d['measured_value']}，标准 {d['standard']}"
                for d in failed_deviations
            ],
            "reply": (
                f"设计图纸比对完成：{phase} 阶段，"
                f"共 {total_checks} 项检查，一致 {matched} 项，"
                f"一致率 {consistency_rate}%，结论：{verdict_text}"
            ),
        }

    def detect_defects(self, image_data: dict) -> dict:
        """工艺缺陷识别（mock CV 检测）

        image_data 结构：
        {
            "project_id": "P001",
            "phase": "masonry",
            "images": [
                {"url": "...", "type": "tile_surface", "location": "卫生间墙面", "captured_at": "..."}
            ],
            "check_categories": ["hollow", "crack", "flatness"]
        }
        """
        project_id = image_data.get("project_id", "")
        phase = image_data.get("phase", "")
        images = image_data.get("images", [])
        check_categories = image_data.get("check_categories", [c["code"] for c in DEFECT_CATEGORIES])

        # Mock CV 检测结果
        detected_defects = []
        checked_items = 0

        for img in images:
            url = img.get("url", "")
            location = img.get("location", "")
            img_type = img.get("type", "")

            for cat_code in check_categories:
                cat_def = next((c for c in DEFECT_CATEGORIES if c["code"] == cat_code), None)
                if not cat_def:
                    continue
                checked_items += 1
                # Mock：约 15% 检出缺陷
                has_defect = (hash(url + cat_code) % 20) >= 17
                if has_defect:
                    confidence = round(0.75 + (hash(url + cat_code) % 25) / 100, 2)
                    detected_defects.append({
                        "image_url": url,
                        "image_type": img_type,
                        "location": location,
                        "category": cat_code,
                        "category_name": cat_def["name"],
                        "severity": cat_def["severity"],
                        "description": cat_def["description"],
                        "confidence": confidence,
                        "bbox": {
                            "x": hash(url + cat_code) % 80 + 10,
                            "y": hash(url + "y" + cat_code) % 80 + 10,
                            "w": 15 + (hash(url + "w" + cat_code) % 20),
                            "h": 15 + (hash(url + "h" + cat_code) % 20),
                        },
                        "rectification": cat_def["rectification"],
                    })

        # 缺陷统计
        severity_count = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for defect in detected_defects:
            severity_count[defect["severity"]] = severity_count.get(defect["severity"], 0) + 1

        # 缺陷类别统计
        category_count = {}
        for defect in detected_defects:
            cat = defect["category_name"]
            category_count[cat] = category_count.get(cat, 0) + 1

        # 总体评价
        if not detected_defects:
            verdict = "pass"
            verdict_text = "未检出缺陷，工艺合格"
        elif severity_count["critical"] > 0:
            verdict = "fail"
            verdict_text = "检出严重缺陷，必须返工"
        elif severity_count["high"] > 0:
            verdict = "conditional_pass"
            verdict_text = "检出高危缺陷，需整改后复检"
        else:
            verdict = "minor_issues"
            verdict_text = "检出轻微缺陷，建议整改"

        return {
            "project_id": project_id,
            "phase": phase,
            "image_count": len(images),
            "checked_items": checked_items,
            "detected_defects": detected_defects,
            "defect_count": len(detected_defects),
            "severity_count": severity_count,
            "category_count": category_count,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "repair_suggestions": [
                f"「{d['category_name']}」缺陷（{d['location']}）：{d['rectification']}"
                for d in detected_defects
            ],
            "reply": (
                f"工艺缺陷识别完成：{phase} 阶段，"
                f"共检测 {checked_items} 项，检出缺陷 {len(detected_defects)} 项"
                f"（严重 {severity_count['critical']}，高 {severity_count['high']}，"
                f"中 {severity_count['medium']}，低 {severity_count['low']}），"
                f"结论：{verdict_text}"
            ),
        }

    @staticmethod
    def detect_qa_intent(message: str) -> str:
        """识别质检相关子意图"""
        if any(kw in message for kw in ["验收", "验收报告", "分项验收", "竣工验收"]):
            return "acceptance"
        if any(kw in message for kw in ["比对", "图纸比对", "设计对比", "一致性"]):
            return "compare"
        if any(kw in message for kw in ["缺陷", "空鼓", "裂缝", "渗漏", "色差", "平整度", "工艺"]):
            return "defect"
        if any(kw in message for kw in ["质检", "质量检测", "检查", "巡检"]):
            return "inspection"
        if any(kw in message for kw in ["整改", "返工", "修补", "修复"]):
            return "rectification"
        return "general"

    def _classify_defect(self, text: str) -> str:
        """根据文本内容识别缺陷类别"""
        for category, keywords in DEFECT_KEYWORD_MAP.items():
            if any(kw in text for kw in keywords):
                return category
        return "other"

    def _get_rectification_suggestion(self, category: str) -> str:
        """根据缺陷类别获取整改建议"""
        cat_def = next((c for c in DEFECT_CATEGORIES if c["name"] == category), None)
        if cat_def:
            return cat_def["rectification"]
        return "根据具体情况整改至符合标准要求"


# ── 模块级函数 ──


def get_acceptance_items(phase: str | None = None) -> dict:
    """获取验收项目清单（可按阶段过滤）

    Args:
        phase: 施工阶段代码（如 mep/masonry/carpentry/painting/installation），为空则返回全部

    Returns:
        验收项目清单
    """
    if phase:
        phase_def = next((p for p in ACCEPTANCE_ITEMS if p["phase"] == phase), None)
        if not phase_def:
            return {
                "phase": phase,
                "items": [],
                "reply": f"阶段「{phase}」暂无预设验收项目",
            }
        return {
            "phase": phase,
            "name": phase_def["name"],
            "items": phase_def["items"],
            "total": len(phase_def["items"]),
            "reply": f"「{phase_def['name']}」验收项目：共 {len(phase_def['items'])} 项",
        }

    return {
        "phases": [
            {"phase": p["phase"], "name": p["name"], "item_count": len(p["items"])}
            for p in ACCEPTANCE_ITEMS
        ],
        "total_phases": len(ACCEPTANCE_ITEMS),
        "total_items": sum(len(p["items"]) for p in ACCEPTANCE_ITEMS),
        "reply": f"共 {len(ACCEPTANCE_ITEMS)} 个验收阶段，{sum(len(p['items']) for p in ACCEPTANCE_ITEMS)} 个验收项目",
    }


def list_defect_categories() -> dict:
    """列出所有缺陷类别"""
    return {
        "categories": DEFECT_CATEGORIES,
        "total": len(DEFECT_CATEGORIES),
        "reply": f"共 {len(DEFECT_CATEGORIES)} 个缺陷类别：{'、'.join(c['name'] for c in DEFECT_CATEGORIES)}",
    }


def assess_defect_severity(category: str, count: int = 1) -> dict:
    """评估缺陷严重程度及建议处理方式

    Args:
        category: 缺陷类别名称（空鼓/裂缝/渗漏/色差/平整度/缝隙/安装/其他）
        count: 缺陷数量

    Returns:
        严重程度评估结果
    """
    cat_def = next((c for c in DEFECT_CATEGORIES if c["name"] == category or c["code"] == category), None)
    if not cat_def:
        return {
            "category": category,
            "error": f"未知缺陷类别: {category}",
            "available": [c["name"] for c in DEFECT_CATEGORIES],
        }

    severity = cat_def["severity"]
    # 根据数量调整优先级
    if count >= 5 and severity == "medium":
        priority = "high"
    elif count >= 3 and severity == "high":
        priority = "critical"
    else:
        priority = severity

    return {
        "category": cat_def["name"],
        "category_code": cat_def["code"],
        "base_severity": severity,
        "count": count,
        "priority": priority,
        "description": cat_def["description"],
        "rectification": cat_def["rectification"],
        "reply": f"缺陷「{cat_def['name']}」×{count}，严重级别：{severity}，处理优先级：{priority}",
    }
