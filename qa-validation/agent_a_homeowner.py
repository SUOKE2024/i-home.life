"""智能体 A — 业主张先生（homeowner）

用户画像：昆明 126㎡ 改善型业主，深度参与全链路，习惯逐项核对账单与进度，
对预算/结算金额敏感，会主动使用 AI 设计、AI 客服与智能家居选配。

覆盖链路：登录 → 项目 → 全链路 timeline → AI 设计 → 预算 → 采购(含支付意图)
→ 施工 → 质检 → 结算 → 智能家居 → 变更 → AI 对话 → 资金托管
并穿插边界条件（空名/越权/非法ID/异常载荷）与异常场景验证。
"""

from agent_common import Agent

PHONE = "13800138000"


class AgentAHomeowner(Agent):
    name = "agent_a_homeowner"
    role = "homeowner"
    phone = PHONE
    habits = "深度参与全链路，逐项核对账单，敏感金额一致性"

    # ── 1. 认证与账户 ──────────────────────────────────────
    def check_auth(self) -> None:
        self.api(scenario="normal", step="获取当前用户", method="GET", path="/auth/me",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("role 非 homeowner"))
                 if b.get("role") != "homeowner" else None)
        self.api(scenario="normal", step="获取权限码", method="GET", path="/auth/me/permissions",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("无权限码"))
                 if not isinstance(b, dict) or not b.get("permissions") else None)

    # ── 2. 项目与全链路 timeline ────────────────────────────
    def walk_projects(self) -> None:
        ok, st, body = self.api(scenario="normal", step="项目列表", method="GET", path="/projects",
                                check=lambda b: (_ for _ in ()).throw(AssertionError("项目为空"))
                                if not isinstance(b, list) or len(b) == 0 else None)
        if ok:
            self.project_ids = [p["id"] for p in body][:3]
        for pid in self.project_ids:
            self.api(scenario="normal", step=f"项目详情 {pid[:8]}", method="GET",
                     path=f"/projects/{pid}")
            self.api(scenario="normal", step=f"全链路timeline {pid[:8]}", method="GET",
                     path=f"/projects/{pid}/timeline",
                     check=lambda b: (_ for _ in ()).throw(AssertionError("timeline 缺 stages"))
                     if not isinstance(b, dict) or "stages" not in b else None)

    # ── 3. 新建项目（正常 + 边界 + 异常）────────────────────
    def create_project(self) -> str | None:
        payload = {
            "name": "QA-验证-昆明滇池路改善房",
            "address": "云南省昆明市官渡区滇池路 QA 苑 6 栋 301",
            "total_area": 118.0,
            "project_type": "full_renovation",
            "house_type": "平层",
            "description": "智能体A交叉验证新建项目",
            "latitude": 24.9501, "longitude": 102.7261,
            "contact_name": "张先生", "contact_phone": PHONE,
        }
        ok, st, body = self.api(scenario="normal", step="创建项目", method="POST", path="/projects",
                                payload=payload, expect=201)
        if ok:
            return body["id"]
        return None

    # ── 3b. 新项目 BOM 生成（供预算/采购链路使用）────────────
    def bom_chain(self, project_id: str) -> bool:
        # 先为项目创建户型（房间），使 BOM 自动生成可用（几何算量优先，经验法回退）
        self.api(scenario="normal", step="新项目创建户型", method="POST",
                 path="/floorplans", expect=201,
                 payload={"project_id": project_id, "name": "QA-验证户型",
                          "total_area": 118.0, "room_count": 5,
                          "room_status": {"客厅": "in_progress", "主卧": "in_progress",
                                          "次卧": "pending", "厨房": "pending",
                                          "卫生间": "pending"}}, timeout=60)
        ok, st, body = self.api(scenario="normal", step="新项目自动生成BOM", method="POST",
                                path=f"/materials/bom/generate/{project_id}", expect=201, timeout=60)
        if ok:
            return True
        # 回退：手动登记 BOM 明细项
        ok2, st2, body2 = self.api(scenario="normal", step="手动登记BOM明细", method="POST",
                                   path="/materials/bom", expect=201,
                                   payload={"project_id": project_id, "material_id": "M-TILE-01",
                                            "quantity": 82.0}, timeout=60)
        return ok2

    def project_boundaries(self) -> None:
        # 边界：空项目名
        self.api(scenario="boundary", step="创建空名项目", method="POST", path="/projects",
                 payload={"name": "", "total_area": 100}, expect=422)
        # 边界：非法面积（缺陷确认：-5 被 201 接受 → 记录后清理）
        ok, st, body = self.api(scenario="boundary", step="创建负面积项目", method="POST",
                                path="/projects",
                                payload={"name": "QA-非法面积", "total_area": -5}, expect=422)
        if not ok and isinstance(body, dict) and body.get("id"):
            self.api(scenario="boundary", step="清理负面积项目", method="DELETE",
                     path=f"/projects/{body['id']}", expect=204)
        # 异常：访问不存在的项目
        self.api(scenario="exception", step="访问不存在项目", method="GET",
                 path="/projects/00000000-0000-0000-0000-000000000000", expect=404)
        # 越权：用他人项目 ID（本地库其它用户的种子项目）— 期望 403/404
        self.api(scenario="exception", step="越权访问他人项目", method="GET",
                 path="/projects/00000000-0000-0000-0000-000000000001", expect=404)

    # ── 4. AI 设计 ─────────────────────────────────────────
    def ai_design(self, project_id: str | None) -> None:
        payload = {"message": "126㎡三居室现代简约风，全屋智能，预算35万", "project_id": project_id}
        ok, st, body = self.api(scenario="normal", step="AI 设计提案", method="POST",
                                path="/agents/design", payload=payload, timeout=150)
        if ok and isinstance(body, dict):
            self.api(scenario="normal", step="设计草图方案", method="POST",
                     path="/agents/design/proposals",
                     payload={"requirement": "客厅+餐厅一体，无主灯，中央空调"}, timeout=150)

    # ── 5. 预算链路 ────────────────────────────────────────
    def budget_chain(self, project_id: str) -> None:
        ok, st, body = self.api(scenario="normal", step="从BOM生成预算", method="POST",
                                path=f"/budgets/generate-from-bom/{project_id}", expect=201,
                                timeout=60)
        budget_id = body.get("id") if ok and isinstance(body, dict) else None
        if budget_id:
            self.api(scenario="normal", step="提交预算", method="POST",
                     path=f"/budgets/{budget_id}/submit")
            self.api(scenario="normal", step="批准预算", method="POST",
                     path=f"/budgets/{budget_id}/approve")
            self.api(scenario="normal", step="执行预算", method="POST",
                     path=f"/budgets/{budget_id}/execute")
        self.api(scenario="normal", step="预算偏差预警", method="POST", path="/budgets/variance-check",
                 payload={"total_estimated": 320000, "total_actual": 335800}, timeout=120)

    # ── 6. 采购链路（含支付意图）────────────────────────────
    def procurement_chain(self, project_id: str) -> None:
        ok, st, body = self.api(scenario="normal", step="BOM生成采购订单", method="POST",
                                path=f"/procurement/generate-from-bom/{project_id}",
                                expect=200, timeout=60)
        order_ids: list[str] = []
        if ok:
            orders = body if isinstance(body, list) else (body.get("orders") if isinstance(body, dict) else [])
            order_ids = [o.get("id") for o in orders if isinstance(o, dict) and o.get("id")]
        if not order_ids:
            ok2, st2, body2 = self.api(scenario="normal", step="查询项目采购订单", method="GET",
                                       path=f"/procurement/orders/{project_id}")
            if ok2 and isinstance(body2, list):
                order_ids = [o["id"] for o in body2 if o.get("status") != "cancelled"]
        for oid in order_ids[:2]:
            # 可验证支付意图签发 + 校验
            ok3, st3, body3 = self.api(scenario="normal", step=f"签发支付意图 {oid[:8]}",
                                       method="POST",
                                       path=f"/procurement/orders/{oid}/payment-intent",
                                       payload={}, expect=200, timeout=60)
            if ok3 and isinstance(body3, dict) and body3.get("token"):
                token = body3["token"]
                amount = body3.get("amount")
                self.api(scenario="normal", step=f"校验支付意图 {oid[:8]}", method="POST",
                         path="/procurement/payment-intents/verify",
                         payload={"token": token, "order_id": oid, "amount": amount,
                                  "actor_user_id": self.user_id}, timeout=60)
            # 确认收货
            self.api(scenario="normal", step=f"确认收货 {oid[:8]}", method="POST",
                     path=f"/procurement/orders/{oid}/delivery-confirm", payload={}, timeout=60)
        # AI 比价
        self.api(scenario="normal", step="AI 供应商推荐", method="GET",
                 path="/procurement/recommend-suppliers?category=乳胶漆", timeout=120)

    # ── 7. 施工链路 ────────────────────────────────────────
    def construction_chain(self, project_id: str) -> None:
        self.api(scenario="normal", step="AI 生成施工计划", method="POST",
                 path="/construction/plan",
                 payload={"project_id": project_id, "area": 118, "tier": "comfort"}, timeout=150)
        self.api(scenario="normal", step="施工任务列表", method="GET",
                 path=f"/construction/tasks/{project_id}")
        self.api(scenario="normal", step="质检清单", method="GET",
                 path="/construction/quality-checklist/waterproof")

    # ── 8. 质检链路 ────────────────────────────────────────
    def quality_chain(self, project_id: str) -> None:
        payload = {"project_id": project_id, "phase": "masonry", "category": "tile",
                   "description": "QA 交叉验证：卫生间墙砖空鼓待整改", "severity": "high",
                   "location": "卫生间东墙", "status": "open"}
        ok, st, body = self.api(scenario="normal", step="登记质检问题", method="POST",
                                path="/construction/quality-issues", payload=payload, expect=201)
        if ok:
            self.api(scenario="normal", step="项目质检问题列表", method="GET",
                     path=f"/construction/quality-issues/{project_id}")
        self.api(scenario="normal", step="AI 质检问题检测", method="POST",
                 path="/construction/quality-detect",
                 payload={"project_id": project_id, "phase": "masonry",
                          "inspection_results": [{"item": "墙面平整度", "result": "偏差 5mm"}]},
                 timeout=150)

    # ── 9. 结算链路 ────────────────────────────────────────
    def settlement_chain(self, project_id: str) -> None:
        self.api(scenario="normal", step="从预算生成结算单", method="POST",
                 path=f"/settlements/generate-from-budget/{project_id}", expect=201, timeout=60)
        self.api(scenario="normal", step="结算异常检测", method="POST",
                 path="/settlements/anomaly-check",
                 payload={"contract_amount": 320000, "actual_amount": 335800,
                          "change_orders": [{"title": "QA-防水升级", "amount": 2600}]},
                 timeout=150)
        self.api(scenario="normal", step="里程碑结算", method="POST",
                 path="/settlements/milestone",
                 payload={"contract_amount": 320000, "milestone_code": "M1"}, timeout=120)
        self.api(scenario="normal", step="查询项目结算单", method="GET",
                 path=f"/settlements/project/{project_id}")

    # ── 10. 智能家居 ───────────────────────────────────────
    def smart_home_chain(self, project_id: str) -> None:
        ok, st, body = self.api(scenario="normal", step="智能家居方案列表", method="GET",
                                path=f"/smart-home/schemes/project/{project_id}")
        if ok and isinstance(body, list) and body:
            sid = body[0]["id"]
            self.api(scenario="normal", step=f"方案价格计算 {sid[:8]}", method="GET",
                     path=f"/smart-home/schemes/{sid}/price")
            self.api(scenario="normal", step=f"方案AI推荐 {sid[:8]}", method="POST",
                     path=f"/smart-home/schemes/{sid}/auto-recommend", payload={}, timeout=120)

    # ── 11. 变更单 ─────────────────────────────────────────
    def change_order_chain(self, project_id: str) -> None:
        self.api(scenario="normal", step="创建变更单", method="POST", path="/change-orders",
                 payload={"project_id": project_id, "title": "QA-卫生间防水升级",
                          "description": "防水卷材升级为高分子", "type": "upgrade",
                          "amount": 2600.0}, expect=201)

    # ── 12. AI 对话（正常 + 边界 + 异常）────────────────────
    def chat_chain(self, project_id: str) -> None:
        self.api(scenario="normal", step="AI 客服对话", method="POST", path="/agents/chat",
                 payload={"message": "帮我看看装修进度到哪一步了，预算还剩多少",
                          "project_id": project_id, "agent_type": "concierge"}, timeout=150)
        # 边界：空消息
        self.api(scenario="boundary", step="AI 对话空消息", method="POST", path="/agents/chat",
                 payload={"message": ""}, expect=422)
        # 边界：超长消息
        self.api(scenario="boundary", step="AI 对话超长消息", method="POST", path="/agents/chat",
                 payload={"message": "很" * 3000}, expect=422)
        # 异常：未知 agent_type（应诚实 422 拒绝，不得 500）
        self.api(scenario="exception", step="AI 对话未知智能体", method="POST", path="/agents/chat",
                 payload={"message": "你好", "agent_type": "no_such_agent"}, expect=422, timeout=60)

    # ── 13. 资金托管 ───────────────────────────────────────
    def escrow_chain(self, project_id: str) -> None:
        # 先为项目采购订单创建担保支付，再开通存管账户
        ok, st, body = self.api(scenario="normal", step="查询项目采购订单(托管)", method="GET",
                                path=f"/procurement/orders/{project_id}")
        escrow_payment_id = None
        if ok and isinstance(body, list) and body:
            oid = body[0]["id"]
            ok2, st2, body2 = self.api(scenario="normal", step="创建担保支付", method="POST",
                                       path="/procurement-enhanced/escrow",
                                       payload={"order_id": oid}, expect=201)
            if ok2 and isinstance(body2, dict):
                escrow_payment_id = body2.get("id") or body2.get("payment_id")
        if not escrow_payment_id:
            self.record(scenario="normal", step="无担保支付可开通托管", method="-", path="-",
                        status=None, ok=True, detail="跳过存管账户开通（诚实降级）")
            return
        ok, st, body = self.api(scenario="normal", step="开通存管账户", method="POST",
                                path="/escrow/trustee-accounts", expect=201,
                                payload={"escrow_payment_id": escrow_payment_id,
                                         "account_no_masked": "6222 **** **** 8888"})
        if ok and isinstance(body, dict):
            acc = body.get("id") or body.get("account_id")
            if acc:
                self.api(scenario="normal", step=f"存管账户详情 {str(acc)[:8]}", method="GET",
                         path=f"/escrow/trustee-accounts/{acc}")
                self.api(scenario="normal", step=f"托管利息信息 {str(acc)[:8]}", method="GET",
                         path=f"/escrow/trustee-accounts/{acc}/interest")

    # ── 主流程 ─────────────────────────────────────────────
    def run(self) -> None:
        if not self.login():
            return
        self.check_auth()
        self.walk_projects()
        pid = self.create_project()
        self.project_boundaries()
        pid = pid or (self.project_ids[0] if self.project_ids else None)
        if not pid:
            self.record(scenario="normal", step="无可用项目终止链路", method="-", path="-",
                        status=None, ok=False, issue=self.issue("NO_PROJECT"))
            return
        # 新项目尽量打通 BOM→预算→采购；无房间/BOM 数据时回退到种子演示项目跑全链路
        chain_pid = pid if self.bom_chain(pid) else (self.project_ids[0] if self.project_ids else pid)
        if chain_pid != pid:
            self.record(scenario="normal", step="链路项目回退", method="-", path="-",
                        status=None, ok=True, detail=f"新项目无 BOM 数据，全链路回退演示项目 {chain_pid[:8]}")
        chains = [
            ("AI设计", lambda: self.ai_design(pid)),
            ("预算", lambda: self.budget_chain(chain_pid)),
            ("采购", lambda: self.procurement_chain(chain_pid)),
            ("施工", lambda: self.construction_chain(chain_pid)),
            ("质检", lambda: self.quality_chain(chain_pid)),
            ("结算", lambda: self.settlement_chain(chain_pid)),
            ("智能家居", lambda: self.smart_home_chain(chain_pid)),
            ("变更", lambda: self.change_order_chain(pid)),
            ("AI对话", lambda: self.chat_chain(chain_pid)),
            ("资金托管", lambda: self.escrow_chain(chain_pid)),
        ]
        # 各链路异常兜底：单链失败不阻断后续链，且确保证据始终落盘
        for label, chain in chains:
            try:
                chain()
            except Exception as e:  # noqa: BLE001
                self.record(scenario="exception", step=f"链路[{label}]异常", method="-",
                            path="-", status=None, ok=False, issue=self.issue("CHAIN_CRASH"),
                            detail=f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    a = AgentAHomeowner()
    a.run()
    path = a.save_evidence()
    print("=== 智能体A 完成 ===")
    print(a.summary())
    print(f"证据: {path}")
