"""测试 ContentPublisherAgent — 产品管理、内容发布"""

import pytest


class TestContentPublisherIntent:
    """意图分类测试"""

    def test_classify_create_product(self):
        from app.agents.content_publisher import ContentPublisherAgent
        assert ContentPublisherAgent.classify_intent("我要上架一款地砖") == "create_product"
        assert ContentPublisherAgent.classify_intent("发布新品800×800瓷砖") == "create_product"

    def test_classify_update_product(self):
        from app.agents.content_publisher import ContentPublisherAgent
        assert ContentPublisherAgent.classify_intent("修改产品价格") == "update_product"
        assert ContentPublisherAgent.classify_intent("更新产品描述") == "update_product"
        assert ContentPublisherAgent.classify_intent("编辑产品信息") == "update_product"

    def test_classify_archive_product(self):
        from app.agents.content_publisher import ContentPublisherAgent
        assert ContentPublisherAgent.classify_intent("下架产品") == "archive_product"
        assert ContentPublisherAgent.classify_intent("归档产品") == "archive_product"
        assert ContentPublisherAgent.classify_intent("删除产品abc123") == "archive_product"

    def test_classify_list_products(self):
        from app.agents.content_publisher import ContentPublisherAgent
        assert ContentPublisherAgent.classify_intent("查看产品列表") == "list_my_products"
        assert ContentPublisherAgent.classify_intent("我的商品") == "list_my_products"

    def test_classify_publish_product(self):
        from app.agents.content_publisher import ContentPublisherAgent
        assert ContentPublisherAgent.classify_intent("发布产品到项目") == "publish_product"
        assert ContentPublisherAgent.classify_intent("上架到项目abc") == "publish_product"

    def test_classify_update_stock(self):
        from app.agents.content_publisher import ContentPublisherAgent
        assert ContentPublisherAgent.classify_intent("库存不足") == "update_stock"
        assert ContentPublisherAgent.classify_intent("售罄") == "update_stock"
        assert ContentPublisherAgent.classify_intent("补货") == "update_stock"


class TestProductInfoExtraction:
    """产品信息提取测试"""

    def test_extract_basic_info(self):
        from app.agents.content_publisher import ContentPublisherAgent
        info = ContentPublisherAgent.extract_product_info("800×800灰色防滑地砖，50元/㎡")
        assert info["category"] == "tile"
        assert "地砖" in info["name"]
        assert info["price_min"] == 50

    def test_extract_with_tags(self):
        from app.agents.content_publisher import ContentPublisherAgent
        info = ContentPublisherAgent.extract_product_info("欧普吸顶灯，120元/个 #简约 #客厅 #LED")
        assert info["category"] == "lighting"
        assert len(info["tags"]) == 3
        assert "简约" in info["tags"]

    def test_extract_empty(self):
        from app.agents.content_publisher import ContentPublisherAgent
        info = ContentPublisherAgent.extract_product_info("随便看看")
        assert not info["category"]
        assert info["price_min"] is None

    def test_extract_price_range(self):
        from app.agents.content_publisher import ContentPublisherAgent
        info = ContentPublisherAgent.extract_product_info("立邦乳胶漆，200-300元/桶")
        assert info["category"] == "paint"
        assert info["price_min"] == 200
        assert info["price_max"] == 300


class TestContentPublisherMock:
    """Mock 模式测试"""

    def test_handle_create_product_complete(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        reply = agent.handle_product_request("800×800灰色防滑地砖，50元/㎡ #防滑", "供应商A")
        assert "产品信息已识别" in reply
        assert "地砖" in reply

    def test_handle_create_product_incomplete(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        reply = agent.handle_product_request("我想卖点东西", "供应商A")
        assert "产品发布助手" in reply

    def test_handle_list_products(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        reply = agent.handle_product_request("查看产品列表", "供应商A")
        assert "/api/products/mine" in reply

    def test_handle_update_product(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        reply = agent.handle_product_request("修改产品价格", "供应商A")
        assert "产品更新" in reply

    def test_handle_archive_product(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        reply = agent.handle_product_request("下架产品", "供应商A")
        assert "产品下架" in reply

    def test_handle_stock_update(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        reply = agent.handle_product_request("售罄", "供应商A")
        assert "库存更新" in reply

    def test_agent_name(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        assert agent.agent_name == "content_publisher"

    def test_system_prompt_not_empty(self):
        from app.agents.content_publisher import ContentPublisherAgent
        agent = ContentPublisherAgent()
        assert len(agent.system_prompt) > 100
        assert "内容发布" in agent.system_prompt


class TestChatAPI:
    """聊天 API 集成测试"""

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, client):
        """未认证调用聊天端点应返回 401"""
        resp = await client.post(
            "/api/chat/messages",
            json={"message": "hello", "project_id": "test"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_empty_message_rejected(self, client):
        """空消息应被拒绝"""
        resp = await client.post(
            "/api/auth/register",
            json={"phone": "13900999001", "name": "ChatTest", "password": "test123456"},
        )
        assert resp.status_code == 201
        token = resp.json()["access_token"]

        resp = await client.post(
            "/api/chat/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "", "project_id": "test"},
        )
        assert resp.status_code in (400, 404, 422)
