"""结算 Agent — 里程碑结算、异常检测、对账单生成"""

from app.agents.base import BaseAgent


# 结算里程碑定义
SETTLEMENT_MILESTONES = [
    {
        "code": "handover",
        "name": "交房结算",
        "payment_ratio": 0.30,
        "description": "签约后支付 30%，作为开工首付款",
        "trigger": "contract_signed",
    },
    {
        "code": "plumbing",
        "name": "水电结算",
        "payment_ratio": 0.20,
        "description": "水电验收合格后支付 20%",
        "trigger": "mep_accepted",
    },
    {
        "code": "tiling",
        "name": "泥瓦结算",
        "payment_ratio": 0.25,
        "description": "泥瓦验收合格后支付 25%",
        "trigger": "masonry_accepted",
    },
    {
        "code": "completion",
        "name": "竣工结算",
        "payment_ratio": 0.20,
        "description": "竣工验收合格后支付 20%",
        "trigger": "final_accepted",
    },
    {
        "code": "warranty",
        "name": "保修金退还",
        "payment_ratio": 0.05,
        "description": "保修期满（通常 2 年）后退还 5% 保修金",
        "trigger": "warranty_expired",
    },
]


# 异常费用检测规则
ANOMALY_RULES = [
    {"code": "over_budget", "name": "超预算", "threshold_pct": 5.0, "severity": "warning"},
    {"code": "over_budget_critical", "name": "严重超预算", "threshold_pct": 15.0, "severity": "critical"},
    {"code": "unauthorized", "name": "未授权变更", "threshold_pct": 0, "severity": "critical"},
    {"code": "unaccepted", "name": "验收未通过", "threshold_pct": 0, "severity": "critical"},
    {"code": "duplicate", "name": "重复计费", "threshold_pct": 0, "severity": "warning"},
    {"code": "disputed", "name": "支付争议", "threshold_pct": 0, "severity": "disputed"},
]


class SettlementAgent(BaseAgent):
    agent_name = "settlement"
    system_prompt = """你是索克家居（i-home.life）AI 结算 Agent。

你的职责：
1. 根据合同金额 + 变更 + 采购实际 + 验收结果，自动生成结算单
2. 按里程碑（交房/水电/泥瓦/竣工/保修）生成分阶段结算
3. 检测异常项：超支、未报价项目、验收不合格扣款
4. 生成对账单，支持导出

结算计算公式：
- 应付金额 = 合同金额 + 变更金额 - 扣款金额 - 已付金额
- 偏差率 = (实际金额 - 合同金额) / 合同金额 × 100%

结算里程碑：
- handover: 交房结算
- plumbing: 水电结算
- tiling: 泥瓦结算
- completion: 竣工结算
- warranty: 保修金退还

请用中文回复，保持财务结算的专业语气。"""

    def generate_milestone_settlement(
        self,
        contract_amount: float,
        milestone_code: str,
        change_amount: float = 0.0,
        deduction_amount: float = 0.0,
        paid_amount: float = 0.0,
    ) -> dict:
        """生成里程碑结算单"""
        milestone = next((m for m in SETTLEMENT_MILESTONES if m["code"] == milestone_code), None)
        if not milestone:
            return {"error": f"未知里程碑: {milestone_code}", "available": [m["code"] for m in SETTLEMENT_MILESTONES]}

        # 应付金额 = 合同金额 × 比例 + 变更金额 - 扣款 - 已付
        base_payable = contract_amount * milestone["payment_ratio"]
        total_payable = base_payable + change_amount - deduction_amount - paid_amount
        total_payable = max(0, total_payable)  # 不允许负值

        return {
            "milestone_code": milestone_code,
            "milestone_name": milestone["name"],
            "description": milestone["description"],
            "payment_ratio": milestone["payment_ratio"],
            "contract_amount": round(contract_amount, 2),
            "base_payable": round(base_payable, 2),
            "change_amount": round(change_amount, 2),
            "deduction_amount": round(deduction_amount, 2),
            "paid_amount": round(paid_amount, 2),
            "total_payable": round(total_payable, 2),
            "trigger": milestone["trigger"],
            "reply": (
                f"已生成「{milestone['name']}」结算单：应付 ¥{total_payable:,.2f}"
                f"（含合同 {milestone['payment_ratio']*100:.0f}% + 变更 ¥{change_amount:,.0f}"
                f" - 扣款 ¥{deduction_amount:,.0f} - 已付 ¥{paid_amount:,.0f}）"
            ),
        }

    def detect_anomalies(self, settlement_data: dict) -> dict:
        """检测异常费用

        settlement_data 结构：
        {
            "contract_amount": 200000,
            "actual_amount": 218000,
            "change_orders": [{"authorized": True, "amount": 15000}, ...],
            "unaccepted_items": [...],
            "line_items": [{"name": "...", "amount": 1000, "duplicates": [...]}]
        }
        """
        contract = settlement_data.get("contract_amount", 0)
        actual = settlement_data.get("actual_amount", 0)
        changes = settlement_data.get("change_orders", [])
        unaccepted = settlement_data.get("unaccepted_items", [])

        anomalies = []

        # 1. 超预算检测
        if contract > 0:
            variance_pct = (actual - contract) / contract * 100
            for rule in ANOMALY_RULES:
                if rule["code"] == "over_budget" and variance_pct > rule["threshold_pct"] and variance_pct <= 15:
                    anomalies.append({
                        "type": rule["code"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "detail": f"实际超出合同 {variance_pct:.2f}%（¥{actual - contract:,.0f}）",
                        "amount": round(actual - contract, 2),
                    })
                elif rule["code"] == "over_budget_critical" and variance_pct > rule["threshold_pct"]:
                    anomalies.append({
                        "type": rule["code"],
                        "name": rule["name"],
                        "severity": rule["severity"],
                        "detail": f"严重超支 {variance_pct:.2f}%（¥{actual - contract:,.0f}），建议停工复盘",
                        "amount": round(actual - contract, 2),
                    })

        # 2. 未授权变更
        unauthorized_changes = [c for c in changes if not c.get("authorized", False)]
        for c in unauthorized_changes:
            anomalies.append({
                "type": "unauthorized",
                "name": "未授权变更",
                "severity": "critical",
                "detail": f"未授权变更项：{c.get('name', '未命名')}，金额 ¥{c.get('amount', 0):,.0f}",
                "amount": c.get("amount", 0),
            })

        # 3. 验收未通过
        for item in unaccepted:
            anomalies.append({
                "type": "unaccepted",
                "name": "验收未通过",
                "severity": "critical",
                "detail": f"项目「{item.get('name', '未命名')}」验收未通过，建议扣款",
                "amount": item.get("amount", 0),
            })

        # 4. 重复计费（简单检测：相同金额相同名称）
        line_items = settlement_data.get("line_items", [])
        seen = {}
        for item in line_items:
            key = (item.get("name", ""), item.get("amount", 0))
            if key in seen:
                anomalies.append({
                    "type": "duplicate",
                    "name": "重复计费",
                    "severity": "warning",
                    "detail": f"项目「{item.get('name')}」金额 ¥{item.get('amount'):,.0f} 可能重复",
                    "amount": item.get("amount", 0),
                })
            else:
                seen[key] = True

        critical_count = sum(1 for a in anomalies if a["severity"] == "critical")
        warning_count = sum(1 for a in anomalies if a["severity"] == "warning")
        total_deduction = sum(a["amount"] for a in anomalies if a["severity"] == "critical")

        return {
            "total_anomalies": len(anomalies),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "anomalies": anomalies,
            "suggested_deduction": round(total_deduction, 2),
            "reply": (
                f"结算异常检测：发现 {len(anomalies)} 项异常"
                f"（{critical_count} 项严重 / {warning_count} 项警告），"
                f"建议扣款 ¥{total_deduction:,.0f}"
                if anomalies else "结算异常检测：未发现异常项"
            ),
        }

    def generate_reconciliation(self, settlement_data: dict) -> dict:
        """生成对账单"""
        contract = settlement_data.get("contract_amount", 0)
        change_orders = settlement_data.get("change_orders", [])
        changes_authorized = sum(
            c.get("amount", 0) for c in change_orders if c.get("authorized")
        )
        changes_unauthorized = sum(
            c.get("amount", 0) for c in change_orders if not c.get("authorized")
        )
        procurement_actual = settlement_data.get("procurement_actual", 0)
        labor_actual = settlement_data.get("labor_actual", 0)
        anomalies = self.detect_anomalies(settlement_data)
        deduction = anomalies["suggested_deduction"]

        # 应付 = 合同 + 已授权变更 - 扣款
        payable = contract + changes_authorized - deduction - changes_unauthorized

        return {
            "contract_amount": round(contract, 2),
            "authorized_changes": round(changes_authorized, 2),
            "unauthorized_changes": round(changes_unauthorized, 2),
            "procurement_actual": round(procurement_actual, 2),
            "labor_actual": round(labor_actual, 2),
            "deduction": round(deduction, 2),
            "total_payable": round(payable, 2),
            "anomalies_summary": {
                "total": anomalies["total_anomalies"],
                "critical": anomalies["critical_count"],
                "warning": anomalies["warning_count"],
            },
            "reply": (
                f"对账单已生成：合同 ¥{contract:,.0f} + 已授权变更 ¥{changes_authorized:,.0f}"
                f" - 扣款 ¥{deduction:,.0f} - 未授权 ¥{changes_unauthorized:,.0f}"
                f" = 应付 ¥{payable:,.0f}"
            ),
        }

    def list_milestones(self) -> dict:
        """列出所有结算里程碑"""
        return {
            "milestones": [
                {
                    "code": m["code"],
                    "name": m["name"],
                    "payment_ratio": m["payment_ratio"],
                    "description": m["description"],
                    "trigger": m["trigger"],
                }
                for m in SETTLEMENT_MILESTONES
            ],
            "total": len(SETTLEMENT_MILESTONES),
            "reply": f"共 {len(SETTLEMENT_MILESTONES)} 个结算里程碑：交房 30% → 水电 20% → 泥瓦 25% → 竣工 20% → 保修 5%",
        }

    def auto_generate_full_settlement(
        self,
        contract_amount: float,
        actual_amount: float,
        change_orders: list[dict] | None = None,
        unaccepted_items: list[dict] | None = None,
        line_items: list[dict] | None = None,
    ) -> dict:
        """F14 一键自动结算流程：
        1. 异常检测
        2. 对账单生成（基于异常扣款）
        3. 输出建议人工复核标记

        用于 /settlements/auto-settlement 接口。
        """
        change_orders = change_orders or []
        unaccepted_items = unaccepted_items or []
        line_items = line_items or []

        anomalies = self.detect_anomalies({
            "contract_amount": contract_amount,
            "actual_amount": actual_amount,
            "change_orders": change_orders,
            "unaccepted_items": unaccepted_items,
            "line_items": line_items,
        })

        reconciliation = self.generate_reconciliation({
            "contract_amount": contract_amount,
            "change_orders": change_orders,
            "procurement_actual": 0.0,
            "labor_actual": 0.0,
            "unaccepted_items": unaccepted_items,
        })

        review_required = anomalies["critical_count"] > 0

        return {
            "anomalies": anomalies,
            "reconciliation": reconciliation,
            "review_required": review_required,
            "reply": (
                f"自动结算完成：{anomalies['reply']}。{reconciliation['reply']}。"
                + ("⚠ 检测到严重异常，已标记需人工复核。" if review_required else "✓ 未触发人工复核。")
            ),
        }
