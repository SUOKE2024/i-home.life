import json
import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    agent_name = "orchestrator"
    system_prompt = (
        """你是索克家居（i-home.life）AI 总控 Agent。

你的职责：
1. 理解用户的装修需求意图（设计、预算、采购、施工、质检、结算、客服）
2. 将复杂需求分解为可执行的子任务
3. 根据任务类型路由到合适的专业 Agent
4. 监控全局项目状态，在关键节点提醒用户

可用 Agent：
- designer: 设计 Agent，负责平面布局、3D 建模、效果图
- budget: 预算 Agent，负责成本估算、预算跟踪
- procurement: 采购 Agent，负责物料匹配、询价比价、内容发布
- construction: 施工 Agent，负责进度管理、任务调度、工人匹配（含木工、水电安装工、窗帘安装工等工种调度）
- qa_inspector: 质检 Agent，负责质量检测、验收报告、缺陷识别、图纸比对
- settlement: 结算 Agent，负责财务结算、付款管理
- concierge: 客服 Agent，负责 7×24 知识问答、咨询接待、问题升级
- content_publisher: 内容发布 Agent，辅助供应商在聊天中发布产品/服务
- ar_measurement: AR 测量引导，帮助用户使用 AR 空间测量、RoomPlan 扫描、激光测距等功能
- floorplans: 户型管理，查看/保存/修改户型方案
- structural: 土建结构，梁柱墙板承重结构设计
- lighting: 灯光设计，照明方案、色温规划、照度计算
- smart_home: 智能家居，设备配置、场景联动、Matter 协议
- scene_automation: 场景自动化，智能场景编辑、触发条件、自动化规则
- custom_furniture: 定制家具，参数化设计、板材计算、价格估算
- tasks: 任务协调，任务分配、进度跟踪、工人匹配
- change_orders: 变更管理，工程变更申请、审批、跟踪
- crews: 工程队管理，班组匹配、工队调度
- vr_panorama: VR 全景，360° 漫游、场景切换、语音讲解
- ai_render: AI 渲染，2D/3D 效果图生成、风格迁移
- sketch_to_3d: 草图转3D，手绘草图智能建模
- kitchen: 厨房设计 Agent，橱柜布局、黄金三角、水电走线
- bathroom: 卫浴设计 Agent，干湿分离、排水坡度、防水方案
- mep: 水电暖通 Agent，强弱电布局、空调新风、给排水
- appliance: 家电 Agent，电器尺寸预留、能效匹配、安装方案
- furniture: 家具 Agent，风格搭配、尺寸建议、材质推荐
- door_window: 门窗防水 Agent，型材选择、五金配置、闭水试验
- files: 文件管理 Agent，合同图纸证件上传下载分类
- products: 产品管理 Agent，供应商产品上架定价管理
- identity: 身份认证 Agent，实名认证审核状态查询
- notifications: 通知 Agent，消息推送提醒设备注册管理
- takeoff: 工程量计算 Agent，墙面面积、地砖用量、材料清单
- ifc_export: BIM导出 Agent，IFC 格式结构模型导出
- soft_furnishing: 软装设计 Agent，窗帘地毯抱枕饰品搭配
- hard_decoration: 硬装设计 Agent，吊顶墙面地面石材涂料
- points: 积分 Agent，积分查询兑换排行榜会员等级
- cad_import: CAD导入 Agent，DXF/DWG 图纸导入解析

最重要：对于用户的消息，你需要判断属于哪种类型，然后用以下JSON格式回复：
```json
{
  "intent": "design|budget|procurement|construction|qa_inspector|settlement|concierge|"
            "content_publish|ar_measurement|floorplans|structural|lighting|smart_home|"
            "scene_automation|custom_furniture|tasks|change_orders|crews|vr_panorama|"
            "ai_render|sketch_to_3d|kitchen|bathroom|mep|appliance|furniture|"
            "door_window|files|products|identity|notifications|takeoff|ifc_export|"
            "soft_furnishing|hard_decoration|points|cad_import|general",
  "reasoning": "简短说明",
  "reply": "给用户的回复"
}
```

如果消息包含设计/布局/方案/户型相关内容 → intent: design
如果消息包含预算/价格/费用/成本/报价相关内容 → intent: budget
如果消息包含采购/材料/物料/建材/供应商相关内容 → intent: procurement
如果消息包含施工/进度/排期/工期/阶段/完工/木工/水电安装工/水电工/窗帘安装工/工人/招工/派工相关内容 → intent: construction
如果消息包含质检/验收/缺陷/整改/返工/空鼓/裂缝/渗漏相关内容 → intent: qa_inspector
如果消息包含结算/付款/尾款/账单相关内容 → intent: settlement
如果消息包含咨询/帮助/投诉/售后/FAQ/常见问题相关内容 → intent: concierge
如果消息包含发布/上架/产品/商品/服务/推广相关内容 → intent: content_publish
如果消息包含AR/测量/扫描/量房/激光/LiDAR/RoomPlan/测距/丈量/AR测量/拍照测量/三维扫描/空间测量/面积测算/户型测绘相关内容 → intent: ar_measurement
如果消息包含户型/平面图/户型方案/户型图/户型管理/我的户型/保存户型相关内容 → intent: floorplans
如果消息包含结构/梁/柱/墙/板/承重/框架/地基相关内容 → intent: structural
如果消息包含灯光/照明/灯/照度/色温/灯具/亮度相关内容 → intent: lighting
如果消息包含智能家居/智能/自动化/传感器/窗帘电机/智能灯/Matter/Zigbee相关内容 → intent: smart_home
如果消息包含场景联动/场景/情景/离家/回家/睡眠/会客/一键相关内容 → intent: scene_automation
如果消息包含定制/定做/柜子/衣柜/橱柜/书柜/板材/板材计算相关内容 → intent: custom_furniture
如果消息包含任务/待办/交办/分派/安排/谁来做/工期相关内容 → intent: tasks
如果消息包含变更/改方案/改设计/变更单/设计变更/工程变更相关内容 → intent: change_orders
如果消息包含工程队/班组/施工队/外包/哪个队/派工相关内容 → intent: crews
如果消息包含VR/全景/虚拟/360/漫游/沉浸相关内容 → intent: vr_panorama
如果消息包含渲染/效果图/出图/风格/配色/色调相关内容 → intent: ai_render
如果消息包含草图/手绘/转3D/画图/涂鸦相关内容 → intent: sketch_to_3d
如果消息包含厨房/橱柜/台面/三件套/油烟机/灶具/水槽/厨房布局/黄金三角相关内容 → intent: kitchen
如果消息包含卫生间/浴室/卫浴/马桶/淋浴/浴缸/干湿分离/花洒相关内容 → intent: bathroom
如果消息包含水电/暖通/空调/新风/地暖/配电/插座/给排水/强弱电相关内容 → intent: mep
如果消息包含家电/电器/冰箱/洗衣机/洗碗机/烘干机/微波炉/烤箱/蒸箱/净水器相关内容 → intent: appliance
如果消息包含家具/沙发/餐桌/床/椅子/茶几/电视柜/书桌/衣柜/鞋柜相关内容 → intent: furniture
如果消息包含门窗/窗户/入户门/推拉门/封阳台/断桥铝/防水/闭水试验/渗水相关内容 → intent: door_window
如果消息包含文件/上传/下载/附件/合同/照片/证件/文档相关内容 → intent: files
如果消息包含产品/商品/上架/定价/改价格/SKU/产品管理相关内容 → intent: products
如果消息包含实名/认证/身份/身份证/实名认证/认证状态/审核相关内容 → intent: identity
如果消息包含通知/消息/推送/提醒/手机通知/消息提醒相关内容 → intent: notifications
如果消息包含工程量/算量/材料清单/用量计算/工程量清单/材料用量相关内容 → intent: takeoff
如果消息包含BIM/IFC/导出BIM/BIM模型/IFC文件/结构模型相关内容 → intent: ifc_export
如果消息包含软装/窗帘/地毯/抱枕/装饰画/挂画/布艺/饰品/摆件相关内容 → intent: soft_furnishing
如果消息包含硬装/吊顶/墙面装饰/背景墙/地面/石材/大理石相关内容 → intent: hard_decoration
如果消息包含积分/会员/等级/兑换/奖励/积分商城/成长值相关内容 → intent: points
如果消息包含CAD导入/导入CAD/DXF/DWG/CAD文件/导入图纸相关内容 → intent: cad_import
其他通用问题 → intent: general

请始终输出JSON格式的回复。"""
    )

    async def classify_intent(self, message: str) -> dict:
        """用 LLM 分类用户意图

        LLM 调用失败时打印 warning 日志（避免静默降级），并回退到 fallback_classify
        规则分类，使意图路由至少与 /voice/process 行为一致。
        """
        try:
            result = await self.think(message)
            result = result.strip()
            if "```json" in result:
                start = result.find("```json") + 7
                end = result.find("```", start)
                result = result[start:end].strip()
            elif "```" in result:
                start = result.find("```") + 3
                end = result.find("```", start)
                result = result[start:end].strip()
            return json.loads(result)
        except Exception as e:
            logger.warning(
                "classify_intent_llm_failed: msg=%r provider=%s error=%s; "
                "fallback to rule-based classify",
                message[:80], self.provider, e,
            )
            fallback = self.fallback_classify(message)
            fallback["reasoning"] = f"LLM分类失败({e})，使用规则分类"
            return fallback

    @staticmethod
    def fallback_classify(message: str) -> dict:
        """无 API Key 时的规则分类"""
        keywords = {
            "design": [
                "设计", "布局", "方案", "户型", "平面", "空间", "风格",
                "装修效果", "图纸", "CAD", "添加", "加一个",
                "新建", "建造", "删除", "移动",
            ],
            "budget": ["预算", "价格", "费用", "成本", "报价", "多少钱", "估算", "花费"],
            "procurement": ["采购", "材料", "物料", "建材", "供应商", "购买", "买", "订单", "询价",
                            "家具品类", "家具目录", "家具库", "家具选购", "家具品牌"],
            "construction": ["施工", "进度", "排期", "工期", "阶段", "完工", "招工", "找人", "派工", "发布任务", "安排工人", "要一个",
                             "木工", "水电工", "窗帘安装", "安装工", "电工", "水工"],
            "qa_inspector": ["质检", "验收", "缺陷", "整改", "返工", "空鼓", "裂缝", "渗漏", "色差", "平整度", "工艺缺陷", "验收报告"],
            "concierge": ["咨询", "帮助", "投诉", "售后", "FAQ", "常见问题", "客服", "转人工", "保修", "报修", "退款"],
            "content_publish": ["发布", "上架", "产品", "商品", "推广", "上新", "介绍产品", "发布产品",
                                "修改产品", "更新产品", "下架产品", "我的产品", "库存", "售罄", "缺货",
                                "改价格", "改描述", "编辑产品", "管理产品", "产品列表", "我的商品"],
            "admin": ["用户管理", "角色管理", "权限管理", "平台统计", "平台数据", "管理员", "禁用用户",
                      "启用用户", "审核认证", "系统管理", "设为管理员", "修改角色", "用户列表",
                      "全部项目", "所有用户"],
            "ar_measurement": ["AR", "AR测量", "测量", "扫描", "量房", "激光", "LiDAR", "RoomPlan",
                               "测距", "丈量", "拍照测量", "三维扫描", "空间测量",
                               "面积测算", "户型测绘", "空间扫描", "距离测量", "3D扫描",
                               "勘测", "量房记录", "测量记录", "拍照识别", "拍照扫描", "相机扫描"],
            "floorplans": ["户型", "平面图", "户型方案", "户型图", "户型管理",
                           "我的户型", "保存户型", "户型信息", "楼层平面"],
            "structural": ["结构", "梁", "柱", "墙", "板", "承重", "框架",
                           "地基", "剪力墙", "楼板", "钢筋", "混凝土"],
            "lighting": ["灯光", "照明", "灯", "照度", "色温", "灯具", "亮度",
                         "射灯", "筒灯", "轨道灯", "氛围灯", "灯带"],
            "smart_home": ["智能家居", "智能", "自动化", "传感器", "窗帘电机",
                           "智能灯", "Matter", "Zigbee", "智能开关", "智能插座",
                           "温控", "门锁", "监控"],
            "scene_automation": ["场景联动", "场景", "情景", "离家", "回家",
                                 "睡眠", "会客", "一键", "触发", "条件"],
            "custom_furniture": ["定制", "定做", "柜子", "衣柜", "橱柜", "书柜",
                                 "板材", "板材计算", "展开面积", "投影面积"],
            "tasks": ["任务", "待办", "交办", "分派", "安排", "谁来做", "工期",
                      "施工任务", "任务列表", "安排任务"],
            "change_orders": ["变更", "改方案", "改设计", "变更单", "设计变更",
                              "工程变更", "修改方案", "方案变更"],
            "crews": ["工程队", "班组", "施工队", "外包", "哪个队", "派工",
                      "工队", "施工班组", "装修队",
                      "harness", "调度", "工程队调度", "工队调配"],
            "vr_panorama": ["VR", "全景", "虚拟", "360", "漫游", "沉浸",
                            "VR全景", "360度", "虚拟现实"],
            "ai_render": ["渲染", "效果图", "出图", "风格", "配色", "色调",
                          "3D渲染", "2D渲染", "渲染图", "风格迁移"],
            "sketch_to_3d": ["草图", "手绘", "转3D", "画图", "涂鸦",
                             "手绘转", "草图转", "随手画"],
            "kitchen": ["厨房", "橱柜", "台面", "三件套", "油烟机", "灶具",
                        "水槽", "厨房布局", "黄金三角", "岛台"],
            "bathroom": ["卫生间", "浴室", "卫浴", "马桶", "淋浴", "浴缸",
                         "干湿分离", "花洒", "台盆", "地漏"],
            "mep": ["水电点位", "暖通", "空调", "新风", "地暖", "配电",
                    "插座", "给排水", "强弱电", "MEP", "厨卫水电", "厨卫MEP"],
            "appliance": ["家电", "电器", "冰箱", "洗衣机", "洗碗机", "烘干机",
                          "微波炉", "烤箱", "蒸箱", "净水器", "热水器", "电视机"],
            "furniture": ["家具", "沙发", "餐桌", "床", "椅子", "茶几",
                          "电视柜", "书桌", "鞋柜", "家具风格", "家具尺寸"],
            "door_window": ["门窗", "窗户", "入户门", "推拉门", "封阳台",
                            "断桥铝", "防水", "闭水试验", "渗水", "门窗防水"],
            "files": ["文件", "上传", "下载", "附件", "合同", "照片", "证件",
                      "文档", "文件管理", "图纸管理"],
            "products": ["产品", "商品", "材料价格", "产品目录", "产品上架",
                         "SKU", "产品信息", "规格参数", "产品列表"],
            "identity": ["实名", "认证", "身份证", "身份认证", "实名认证",
                         "认证状态", "审核"],
            "notifications": ["通知", "消息", "推送", "提醒", "手机通知",
                              "消息提醒", "通知设置", "设备注册"],
            "takeoff": ["工程量", "算量", "材料清单", "用量计算", "工程量清单",
                        "材料用量", "辅料计算", "清单计算"],
            "ifc_export": ["BIM", "IFC", "导出BIM", "BIM模型", "IFC文件",
                           "结构模型", "BIM导出", "模型导出"],
            "soft_furnishing": ["软装", "窗帘", "地毯", "抱枕", "装饰画", "挂画",
                                "软装配饰", "布艺", "饰品", "摆件"],
            "hard_decoration": ["硬装", "吊顶", "墙面装饰", "背景墙", "地面",
                                "涂料", "墙纸", "石材", "大理石"],
            "points": ["积分", "会员", "等级", "兑换", "奖励", "累计", "积分商城",
                       "积分兑换", "成长值", "权益"],
            "cad_import": ["CAD导入", "导入CAD", "DXF", "DWG", "CAD文件",
                           "导入图纸", "上传CAD", "CAD图纸"],
        }

        keywords["settlement"] = ["结算", "付款", "尾款", "账单", "结清", "结账"]

        scores = {}
        for intent, kws in keywords.items():
            scores[intent] = sum(1 for kw in kws if kw in message)

        if max(scores.values()) == 0:
            return {"intent": "general", "reasoning": "无明确匹配", "reply": ""}

        best = max(scores, key=scores.get)
        return {"intent": best, "reasoning": f"匹配关键词: {best}", "reply": ""}
