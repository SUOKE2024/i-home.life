"""智能体 B — 供应商（supplier）

用户画像：平台入驻供应商（昆明建材/整装服务商），习惯在工作台批量处理交付单，
关注报价竞争力与货款到账，会通过 B2B 交付单承接装企订单并跟踪状态机流转。

覆盖链路：登录 → 权限码 → 交付单列表 → 创建交付(正常/异步) → 状态机流转
(合法/非法迁移) → 交付详情 → 供应商列表 → AI 供应商推荐 → 担保支付可见性
穿插边界条件（非法面积/未知状态）与越权场景（访问管理端点应 403）。
"""

from agent_common import Agent

PHONE = "13700137000"


class AgentBSupplier(Agent):
    name = "agent_b_supplier"
    role = "supplier"
    phone = PHONE
    habits = "工作台批量处理，关注状态机流转与货款到账"

    # ── 认证与工作台 ────────────────────────────────────────
    def check_auth(self) -> None:
        self.api(scenario="normal", step="获取当前用户", method="GET", path="/auth/me",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("role 非 supplier"))
                 if b.get("role") != "supplier" else None)
        self.api(scenario="normal", step="供应商权限码", method="GET", path="/auth/me/permissions",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("供应商无权限码"))
                 if not isinstance(b, dict) or not b.get("permissions") else None)

    # ── B2B 交付单链路 ──────────────────────────────────────
    def delivery_chain(self) -> list[str]:
        ids: list[str] = []
        ok, st, body = self.api(scenario="normal", step="交付单列表", method="GET", path="/b2b/delivery")
        if ok and isinstance(body, list):
            ids = [d.get("delivery_order_id") for d in body if d.get("delivery_order_id")][:3]

        # 正常：创建交付单（同步模式）
        ok, st, body = self.api(
            scenario="normal", step="创建交付单(同步)", method="POST", path="/b2b/delivery",
            payload={"name": "QA-供应商B-现代简约整装", "area": 118.0, "style": "modern",
                     "budget": 350000, "requirements": "全屋智能+中央空调",
                     "rooms": "客厅,主卧,次卧,厨房,卫生间"}, expect=200)
        if ok and isinstance(body, dict):
            did = body.get("delivery_id") or body.get("delivery_order_id")
            if did:
                ids.append(did)
        # 正常：创建交付单（异步模式）
        self.api(scenario="normal", step="创建交付单(异步)", method="POST", path="/b2b/delivery",
                 payload={"name": "QA-供应商B-异步交付", "area": 88.0, "style": "nordic",
                          "budget": 200000, "async_mode": True}, expect=200)
        return ids

    def status_machine(self, delivery_id: str) -> None:
        if not delivery_id:
            return
        # 合法迁移: draft→quoted
        self.api(scenario="normal", step="状态机 draft→quoted", method="PUT",
                 path=f"/b2b/delivery/{delivery_id}/status",
                 payload={"status": "quoted"})
        # 非法迁移: quoted→in_construction（跳过 accepted，应被 422 拒绝）
        self.api(scenario="boundary", step="状态机非法跳迁 quoted→in_construction",
                 method="PUT", path=f"/b2b/delivery/{delivery_id}/status",
                 payload={"status": "in_construction"}, expect=422)
        # 非法: 未知状态值
        self.api(scenario="boundary", step="状态机未知状态", method="PUT",
                 path=f"/b2b/delivery/{delivery_id}/status",
                 payload={"status": "no_such_status"}, expect=422)
        # 合法: quoted→accepted
        self.api(scenario="normal", step="状态机 quoted→accepted", method="PUT",
                 path=f"/b2b/delivery/{delivery_id}/status",
                 payload={"status": "accepted"})
        # 交付详情回读（核对状态已落库）
        self.api(scenario="normal", step=f"交付详情 {delivery_id[:8]}", method="GET",
                 path=f"/b2b/delivery/{delivery_id}")

    # ── 边界条件 ────────────────────────────────────────────
    def boundaries(self) -> None:
        self.api(scenario="boundary", step="创建零面积交付单", method="POST", path="/b2b/delivery",
                 payload={"name": "QA-零面积", "area": 0}, expect=422)
        self.api(scenario="boundary", step="创建超大面积交付单", method="POST", path="/b2b/delivery",
                 payload={"name": "QA-超大", "area": 20000}, expect=422)
        self.api(scenario="boundary", step="查询不存在交付单", method="GET",
                 path="/b2b/delivery/00000000-0000-0000-0000-000000000000", expect=404)

    # ── 供应商业务面 ────────────────────────────────────────
    def supplier_business(self) -> None:
        self.api(scenario="normal", step="供应商列表", method="GET", path="/procurement/suppliers",
                 check=lambda b: (_ for _ in ()).throw(AssertionError("供应商列表为空"))
                 if not isinstance(b, list) or len(b) == 0 else None)
        self.api(scenario="normal", step="AI 供应商推荐", method="GET",
                 path="/procurement/recommend-suppliers?category=乳胶漆", timeout=120)
        # 越权边界：供应商创建比价报告（非项目 owner → 403）
        self.api(scenario="exception", step="供应商创建比价报告", method="POST",
                 path="/procurement-enhanced/comparisons",
                 payload={"project_id": "00000000-0000-0000-0000-000000000000", "bom_id": None},
                 expect=403)

    # ── 越权检查 ────────────────────────────────────────────
    def authz_checks(self) -> None:
        # 供应商访问管理端点 → 403
        self.api(scenario="exception", step="供应商访问管理统计", method="GET",
                 path="/admin/stats", expect=403)
        self.api(scenario="exception", step="供应商访问用户列表", method="GET",
                 path="/admin/users", expect=403)
        # 供应商访问业主项目列表（本人名下无项目 → 空列表而非 403/500）
        self.api(scenario="normal", step="供应商访问项目列表", method="GET", path="/projects")

    # ── 主流程 ─────────────────────────────────────────────
    def run(self) -> None:
        if not self.login():
            return
        self.check_auth()
        self.delivery_chain()
        self.boundaries()
        # 回读最新交付单做状态机验证
        ok, st, body = self.api(scenario="normal", step="交付单列表(回读)", method="GET",
                                path="/b2b/delivery")
        did = None
        if ok and isinstance(body, list) and body:
            did = body[0].get("delivery_order_id")
        self.status_machine(did or "")
        self.supplier_business()
        self.authz_checks()


if __name__ == "__main__":
    a = AgentBSupplier()
    a.run()
    path = a.save_evidence()
    print("=== 智能体B 完成 ===")
    print(a.summary())
    print(f"证据: {path}")
