"""装修验收清单标准库（S4 — 验收清单贯通）

v1.1.31 FP-5 修复：提取自 ``app/agents/construction.py`` 的 QUALITY_CHECKLISTS，
扩展为 6 阶段（水电/防水/泥瓦/木工/油漆/竣工），每项含：
- item: 检查项名称
- standard: 判定标准（量化阈值）
- method: 检测方法
- regulation: 依据规范（GB/JGJ）
- phase: 阶段码（与 ConstructionTask.phase 对齐）

供：
- ``ConstructionAgent.get_quality_checklist`` 引用（避免重复定义）
- ``quality_service.generate_acceptance_report`` 自动比对 checklist 与实际 issue

受 ``settings.acceptance_checklist_enabled`` feature flag 控制。
"""

# 验收清单按阶段分组
# phase 字段对齐 ConstructionTask.phase 枚举值
ACCEPTANCE_CHECKLISTS: dict[str, list[dict]] = {
    "mep": [
        {
            "item": "水管打压测试",
            "standard": "0.8MPa 保压 30 分钟不掉压",
            "method": "pressure_test",
            "regulation": "GB 50242-2002",
            "category": "给排水",
        },
        {
            "item": "电路绝缘测试",
            "standard": "绝缘电阻 ≥ 0.5MΩ",
            "method": "insulation_test",
            "regulation": "GB 50303-2016",
            "category": "电气",
        },
        {
            "item": "线管布局",
            "standard": "横平竖直，无三管交叉",
            "method": "visual_check",
            "regulation": "GB 50303-2016",
            "category": "电气",
        },
        {
            "item": "强弱电间距",
            "standard": "≥ 500mm",
            "method": "distance_check",
            "regulation": "GB 50303-2016",
            "category": "电气",
        },
        {
            "item": "开关插座位置",
            "standard": "符合图纸偏差 ≤ 5mm",
            "method": "dimension_check",
            "regulation": "GB 50303-2016",
            "category": "电气",
        },
    ],
    "waterproof": [
        {
            "item": "防水层厚度",
            "standard": "≥ 1.5mm（聚氨酯防水涂料）",
            "method": "thickness_test",
            "regulation": "GB 50693-2011",
            "category": "防水",
        },
        {
            "item": "淋浴区墙面防水高度",
            "standard": "≥ 1800mm",
            "method": "dimension_check",
            "regulation": "JGJ 298-2013",
            "category": "防水",
        },
        {
            "item": "其他墙面防水翻边高度",
            "standard": "≥ 300mm",
            "method": "dimension_check",
            "regulation": "JGJ 298-2013",
            "category": "防水",
        },
        {
            "item": "闭水试验",
            "standard": "蓄水 48h 无渗漏",
            "method": "water_test",
            "regulation": "JGJ 298-2013 / HC-005",
            "category": "防水",
        },
        {
            "item": "地漏坡度",
            "standard": "坡度 1%-2%，无积水",
            "method": "slope_check",
            "regulation": "GB 50209-2010",
            "category": "防水",
        },
    ],
    "masonry": [
        {
            "item": "瓷砖空鼓率",
            "standard": "单砖空鼓 < 5%，整体 < 3%",
            "method": "tap_test",
            "regulation": "JGJ/T 304-2013",
            "category": "贴砖",
        },
        {
            "item": "瓷砖平整度",
            "standard": "2m 靠尺 ≤ 2mm",
            "method": "flatness_check",
            "regulation": "JGJ/T 304-2013",
            "category": "贴砖",
        },
        {
            "item": "阴阳角方正度",
            "standard": "偏差 ≤ 3mm",
            "method": "square_check",
            "regulation": "GB 50210-2018",
            "category": "贴砖",
        },
        {
            "item": "地面找平平整度",
            "standard": "2m 靠尺 ≤ 3mm",
            "method": "flatness_check",
            "regulation": "GB 50210-2018",
            "category": "地面",
        },
    ],
    "carpentry": [
        {
            "item": "吊顶平整度",
            "standard": "2m 靠尺 ≤ 3mm",
            "method": "flatness_check",
            "regulation": "GB 50210-2018",
            "category": "吊顶",
        },
        {
            "item": "柜体对角线偏差",
            "standard": "≤ 2mm",
            "method": "diagonal_check",
            "regulation": "GB 50210-2018",
            "category": "定制柜",
        },
        {
            "item": "柜门缝隙",
            "standard": "均匀 1.5-2.5mm",
            "method": "gap_check",
            "regulation": "GB 50210-2018",
            "category": "定制柜",
        },
        {
            "item": "抽屉滑轨",
            "standard": "顺滑无异响",
            "method": "function_test",
            "regulation": "GB/T 3324-2017",
            "category": "定制柜",
        },
    ],
    "painting": [
        {
            "item": "墙面平整度",
            "standard": "2m 靠尺 ≤ 3mm",
            "method": "flatness_check",
            "regulation": "GB 50210-2018",
            "category": "墙面",
        },
        {
            "item": "色差",
            "standard": "无可见色差",
            "method": "color_check",
            "regulation": "GB 50210-2018",
            "category": "墙面",
        },
        {
            "item": "流坠/漏刷",
            "standard": "无流坠、无漏刷",
            "method": "visual_check",
            "regulation": "GB 50210-2018",
            "category": "墙面",
        },
        {
            "item": "阴阳角顺直度",
            "standard": "偏差 ≤ 2mm",
            "method": "straightness_check",
            "regulation": "GB 50210-2018",
            "category": "墙面",
        },
    ],
    "installation": [
        {
            "item": "灯具安装牢固度",
            "standard": "承重 ≥ 灯具重量 4 倍",
            "method": "load_test",
            "regulation": "GB 50303-2016",
            "category": "安装",
        },
        {
            "item": "插座接线",
            "standard": "左零右火上地线",
            "method": "wiring_check",
            "regulation": "GB 50303-2016",
            "category": "安装",
        },
        {
            "item": "卫浴下水",
            "standard": "排水通畅无堵塞",
            "method": "drainage_test",
            "regulation": "GB 50242-2002",
            "category": "安装",
        },
        {
            "item": "橱柜门板",
            "standard": "开关顺滑，缝隙均匀",
            "method": "function_test",
            "regulation": "GB/T 3324-2017",
            "category": "安装",
        },
    ],
    "completion": [
        {
            "item": "整体清洁度",
            "standard": "无施工残留、无灰尘堆积",
            "method": "visual_check",
            "regulation": "—",
            "category": "竣工",
        },
        {
            "item": "成品保护",
            "standard": "门窗/五金/柜体无划痕损伤",
            "method": "visual_check",
            "regulation": "—",
            "category": "竣工",
        },
        {
            "item": "功能验收",
            "standard": "水电/门窗/卫浴全部功能正常",
            "method": "function_test",
            "regulation": "GB 50210-2018",
            "category": "竣工",
        },
        {
            "item": "资料移交",
            "standard": "竣工图/保修卡/材料清单齐全",
            "method": "document_check",
            "regulation": "—",
            "category": "竣工",
        },
    ],
}


# 向后兼容：construction.py 原 QUALITY_CHECKLISTS 别名
# （原数据合并防水项进 masonry；新标准库将防水独立为 waterproof 阶段，
#  保留 masonry 子集以兼容 ConstructionAgent.analyze_inspection_images 的旧调用）
_LEGACY_MASONRY_WITH_WATERPROOF = (
    ACCEPTANCE_CHECKLISTS["masonry"]
    + [
        {
            "item": "防水闭水试验",
            "standard": "蓄水 48h 无渗漏",
            "method": "water_test",
            "regulation": "JGJ 298-2013 / HC-005",
            "category": "防水",
        }
    ]
)

QUALITY_CHECKLISTS: dict[str, list[dict]] = {
    "mep": ACCEPTANCE_CHECKLISTS["mep"],
    "masonry": _LEGACY_MASONRY_WITH_WATERPROOF,
    "carpentry": ACCEPTANCE_CHECKLISTS["carpentry"],
    "painting": ACCEPTANCE_CHECKLISTS["painting"],
    "installation": ACCEPTANCE_CHECKLISTS["installation"],
}


def get_checklist(phase: str) -> list[dict]:
    """获取指定阶段的验收清单（从标准库）

    优先匹配 ACCEPTANCE_CHECKLISTS（6 阶段），回退到 legacy QUALITY_CHECKLISTS。
    """
    if phase in ACCEPTANCE_CHECKLISTS:
        return ACCEPTANCE_CHECKLISTS[phase]
    return QUALITY_CHECKLISTS.get(phase, [])


def all_phases() -> list[str]:
    """返回所有定义了验收清单的阶段码"""
    return list(ACCEPTANCE_CHECKLISTS.keys())
