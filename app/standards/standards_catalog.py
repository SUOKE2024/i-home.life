"""装修行业标准目录（P0 标准目录扩展）

结构化标准目录，供 Model Spec HC 硬约束、验收清单、定额库、环保等级校验统一引用，
实现「标准 → 规则 → 代码」可追溯。只读、确定性、零外部依赖。

数据来源：本仓库既有引用（acceptance_checklists / quota_library / ihome_model_spec /
config feature flags）+ 公开标准编号。领域与 applies_to 对齐现有 Agent 分工，
name 为描述性标注（非官方标准全称）。
"""

# 每条标准：code(编号) / name(描述) / domain(领域) / status(状态)
#   key_constraints(关键约束) / applies_to(适用 Agent) / source(来源)
STANDARDS_CATALOG: list[dict] = [
    {
        "code": "IFC (ISO 16739)",
        "name": "Industry Foundation Classes 建筑数据交换标准",
        "domain": "BIM 数据交换",
        "status": "现行",
        "key_constraints": ["IFC2X3/IFC4/IFC4.3 语义数据交换", "构件/空间/属性结构化表达"],
        "applies_to": ["ifc_export"],
        "source": "buildingSMART",
    },
    {
        "code": "COBie",
        "name": "Construction Operations Building Information Exchange 运维信息交付",
        "domain": "BIM 数据交换",
        "status": "现行",
        "key_constraints": ["资产/设备/空间信息结构化交付"],
        "applies_to": ["ifc_export", "settlement"],
        "source": "buildingSMART",
    },
    {
        "code": "bSDD / IDS / BCF",
        "name": "buildingSMART 数据字典 / 交付规范 / 协作格式",
        "domain": "BIM 数据交换",
        "status": "现行",
        "key_constraints": ["构件语义字典", "交付物校验规则", "协作议题交换"],
        "applies_to": ["ifc_export", "qa_inspector"],
        "source": "buildingSMART",
    },
    {
        "code": "GB 55000 系列",
        "name": "建筑与市政工程通用规范（全文强制）",
        "domain": "建筑结构安全",
        "status": "现行强制",
        "key_constraints": ["承重结构不可破坏", "消防/逃生合规"],
        "applies_to": ["designer", "structural", "construction"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB/T 50353",
        "name": "建筑工程建筑面积计算规范",
        "domain": "面积计算",
        "status": "现行",
        "key_constraints": ["建筑面积/使用面积计算口径"],
        "applies_to": ["takeoff", "budget", "designer"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB/T 50327",
        "name": "住宅装饰装修工程施工规范",
        "domain": "施工工艺",
        "status": "现行",
        "key_constraints": ["住宅装饰装修施工工序与工艺"],
        "applies_to": ["construction"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB 50210",
        "name": "建筑装饰装修工程质量验收标准",
        "domain": "验收",
        "status": "现行",
        "key_constraints": ["墙面/吊顶/贴砖平整度", "阴阳角方正"],
        "applies_to": ["qa_inspector", "construction"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB 50242",
        "name": "建筑给排水及采暖工程施工质量验收规范",
        "domain": "给排水",
        "status": "现行",
        "key_constraints": ["水管打压 0.8MPa 保压 30 分钟", "排水通畅"],
        "applies_to": ["mep", "construction", "qa_inspector"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB 50303",
        "name": "建筑电气工程施工质量验收规范",
        "domain": "电气",
        "status": "现行",
        "key_constraints": ["绝缘电阻 ≥0.5MΩ", "强弱电间距", "左零右火上地线"],
        "applies_to": ["mep", "construction", "qa_inspector"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB 50209",
        "name": "建筑地面工程施工质量验收规范",
        "domain": "地面",
        "status": "现行",
        "key_constraints": ["地面找平平整度", "地漏坡度 1%-2%"],
        "applies_to": ["construction", "qa_inspector"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB 50693",
        "name": "防水工程施工质量验收规范",
        "domain": "防水",
        "status": "现行",
        "key_constraints": ["防水层厚度 ≥1.5mm", "闭水试验 48h 无渗漏"],
        "applies_to": ["bathroom", "construction", "door_window"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "JGJ 298",
        "name": "住宅室内防水工程技术规范",
        "domain": "防水",
        "status": "现行",
        "key_constraints": ["淋浴区防水 ≥1.8m", "其他墙面 ≥0.3m", "闭水试验"],
        "applies_to": ["bathroom", "construction", "door_window"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "JGJ/T 304",
        "name": "住宅室内装饰装修工程质量验收规范",
        "domain": "验收",
        "status": "现行",
        "key_constraints": ["瓷砖空鼓率 <5%", "贴砖平整度"],
        "applies_to": ["qa_inspector", "construction"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB/T 3324",
        "name": "木家具通用技术条件",
        "domain": "家具",
        "status": "现行",
        "key_constraints": ["柜体对角线/门缝", "抽屉滑轨"],
        "applies_to": ["furniture", "qa_inspector"],
        "source": "国家标准",
    },
    {
        "code": "GB 18580",
        "name": "室内装饰装修材料 人造板及其制品中甲醛释放限量",
        "domain": "环保等级",
        "status": "现行",
        "key_constraints": ["ENF/E0/E1 环保等级", "禁止 E2 用于室内"],
        "applies_to": ["procurement", "designer", "budget"],
        "source": "国家标准",
    },
    {
        "code": "GB 18583",
        "name": "室内装饰装修材料 胶粘剂中有害物质限量",
        "domain": "环保等级",
        "status": "现行",
        "key_constraints": ["胶粘剂有害物质限量"],
        "applies_to": ["procurement", "designer"],
        "source": "国家标准",
    },
    {
        "code": "GB 18585",
        "name": "室内装饰装修材料 壁纸中有害物质限量",
        "domain": "环保等级",
        "status": "现行",
        "key_constraints": ["壁纸有害物质限量"],
        "applies_to": ["procurement", "designer"],
        "source": "国家标准",
    },
    {
        "code": "GB 6566",
        "name": "建筑材料放射性核素限量",
        "domain": "环保等级",
        "status": "现行",
        "key_constraints": ["A/B/C 类放射性分级", "室内用 A 类"],
        "applies_to": ["procurement", "designer"],
        "source": "国家标准",
    },
    {
        "code": "GB/T 50500",
        "name": "建设工程工程量清单计价标准",
        "domain": "计价",
        "status": "现行",
        "key_constraints": ["清单计量、市场询价、自主报价、竞争定价"],
        "applies_to": ["budget", "settlement"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB/T 50854",
        "name": "房屋建筑与装饰工程工程量计算标准",
        "domain": "计价",
        "status": "现行",
        "key_constraints": ["装饰工程计量口径"],
        "applies_to": ["takeoff", "budget"],
        "source": "住房和城乡建设部",
    },
    {
        "code": "GB/T 46456",
        "name": "智能家居互联互通标准",
        "domain": "智能家居",
        "status": "2026 实施",
        "key_constraints": ["设备互联互通", "协议兼容矩阵"],
        "applies_to": ["appliance", "notifications"],
        "source": "国家标准（仓库口径）",
    },
    {
        "code": "GB/Z 185-2026",
        "name": "人工智能 智能体互联互通（含 ACDL 能力描述）",
        "domain": "Agent 互联",
        "status": "2026 发布",
        "key_constraints": ["28 位 AID 身份码", "ACDL 能力描述", "工具调用五重安全机制"],
        "applies_to": ["orchestrator"],
        "source": "国家标准（仓库口径）",
    },
    {
        "code": "Matter (CSA)",
        "name": "Matter 智能家居连接协议",
        "domain": "智能家居",
        "status": "现行",
        "key_constraints": ["设备配网", "跨生态共享"],
        "applies_to": ["appliance"],
        "source": "CSA（Connectivity Standards Alliance）",
    },
]


def get_standards(domain: str | None = None) -> list[dict]:
    """按领域筛选标准目录；domain=None 返回全部。"""
    if not domain:
        return list(STANDARDS_CATALOG)
    return [s for s in STANDARDS_CATALOG if s["domain"] == domain]


def standard_codes() -> list[str]:
    """返回全部标准编号（供交叉引用校验）。"""
    return [s["code"] for s in STANDARDS_CATALOG]


def list_domains() -> list[str]:
    """返回标准目录覆盖的领域（去重，保持目录顺序）。"""
    seen: list[str] = []
    for s in STANDARDS_CATALOG:
        if s["domain"] not in seen:
            seen.append(s["domain"])
    return seen
