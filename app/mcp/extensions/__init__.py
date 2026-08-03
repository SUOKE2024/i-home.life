"""MCP 扩展框架（v1.3.0 对齐 MCP 2026-07-28 extensions framework）

MCP 2026-07-28 规范引入正式的扩展框架，Tasks 作为首个正式扩展。
扩展通过 MCPServer._load_extensions() 延迟注册，避免循环导入。

可用扩展：
- tasks: 异步任务扩展（tasks/create, tasks/update, tasks/get, tasks/list, tasks/cancel）

新增扩展步骤：
1. 在本目录新增 <name>.py，实现 Extension 子类
2. 在 MCPServer._load_extensions() 中注册（受 feature flag 控制）
"""


class Extension:
    """MCP 扩展基类。

    子类需实现：
    - NAME: 扩展名（用于注册）
    - VERSION: 扩展版本
    - dispatch(method, params) -> (result, error): 方法分发
    """

    NAME: str = ""
    VERSION: str = "1.0.0"

    async def dispatch(self, method: str, params: dict | None = None) -> tuple[dict | None, dict | None]:
        """分发扩展方法。

        Returns:
            (result, error) —— 成功时 result 非 None，失败时 error 非 None
        """
        raise NotImplementedError
