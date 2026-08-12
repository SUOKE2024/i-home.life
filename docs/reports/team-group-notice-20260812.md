# 团队群公告：P0 设备热点联动已推送，请拉取代码并阅读文档

> 用途：直接复制到团队群（钉钉/飞书/微信）
> 生成日期：2026-08-12

---

【后端团队公告】P0 设备热点联动已推送到 main，请尽快处理

各位后端同学：

720° 漫游设备热点联动（P0）已推送远程仓库（`08e87c1..2d05b0a`，共 9 个 commit，含 4 个 P0/文档 commit）。请配合完成以下 3 件事：

**1. 拉取最新代码**
```
git pull
```
涉及生态桥接入 / 场景执行 / VR 设备图层的同学请重点确认。

**2. 必读两份文档**
- 连接池并发规范：`docs/guides/tech-note-connection-pool-concurrency-20260812.md`
  - `BridgeConnectionPool.get()` 已加 `asyncio.Lock` 互斥并发首次建连（gather 并行防重复握手）
  - 新增桥实现必须走 `pool.get()`，禁止裸 connect、禁止跨请求保存 pool
- UnboundLocalError 根因分析：`docs/reports/unboundlocal-final-results-root-cause-20260812.md`
  - 结果列表一律在 try 外初始化，防半成品字节码导致的变量未初始化问题

**3. 快速自检（2 分钟）**
```
pytest tests/test_ecosystem_bridge.py -q   # 连接池 9 个用例
```
确认 Lock 复用（并发仅 1 次 connect）与异常清理正常。

**代码纪律提醒**：无 DB 可并行、有 DB 必须串行；索引/ID 字段判断用 `is None` 而非 `not`（`depends_on: 0` falsy 陷阱）。

有问题群里 @【负责人】，或看邮件详情的完整变更表。谢谢配合！
