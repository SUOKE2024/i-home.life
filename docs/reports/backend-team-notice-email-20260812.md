# 变更通知邮件草稿：P0 设备热点联动入库 + 连接池规范 + 根因修复

> 用途：发送给后端团队
> 生成日期：2026-08-12
> 复制标题与正文至邮件客户端即可发送；【】内为待填信息。

---

## 主题

【通知】P0 设备热点联动已入库（3 commits）· 连接池并发规范同步 · UnboundLocalError 根因修复

## 收件人

后端团队

## 正文

各位好，

720° 漫游设备热点联动（P0）已完成工程落地并入库，本次同步三件事，请关注：

### 一、变更概览（3 个 commit，工作区已全部入库）

| Commit | 内容 | 文件数 |
|---|---|---|
| `4522f9c` feat(p0) | 设备命令/场景执行/设备图层 3 端点 + 传感器快照真实落库 + 两阶段并行执行 + BridgeConnectionPool + 前端/Flutter 接入 | 43 |
| `47faa04` docs | P0 报告/规范/排障文档归档（性能总结、覆盖率 v2、技术分享完整版） | 20 |
| `c1289a1` chore | 历史未提交改动入库（Agent 自进化/语音 fallback/demo 脚本） | 29 |

### 二、需要团队同步阅读的两份文档

1. **连接池并发规范**：`docs/guides/tech-note-connection-pool-concurrency-20260812.md`
   - `BridgeConnectionPool.get()` 用 `asyncio.Lock` 互斥**并发首次建连**（gather 并行时防 N 次重复握手）
   - Lock 只串行化握手、不串行化命令执行；`close_all()` 收尾无需加锁
   - 异常处理矩阵：connect 失败不入池 / send 异常标 failed / stub 桥静默（诚实降级）
   - **接入约束**：新增桥实现必须走 `pool.get()`，禁止裸 connect；禁止跨请求保存 pool
2. **UnboundLocalError 根因分析**：`docs/reports/unboundlocal-final-results-root-cause-20260812.md`
   - 现象：7 个场景执行用例同时 `UnboundLocalError: final_results`
   - 根因：测试期间 `scene_automation_service.py` 被并发写入，pytest 读到半成品字节码
   - 修复：`results` 初始化提前到 try 外 + `asyncio.gather(..., return_exceptions=True)` + `isinstance` 过滤
   - 已全量验证 50 passed，flake8/mypy 0 issues

### 三、团队执行约定（写入代码时请遵守）

1. **结果列表一律在 try 外初始化**——`try/finally + 结果组装` 模式防 UnboundLocalError 复发
2. **并行边界**：无 DB 可并行、有 DB 必须串行（共享 AsyncSession 并行会 ISCE 冲突）
3. **可选字段判断**：索引/ID/哨兵值用 `is None`，禁止 `not`（`depends_on: 0` falsy 陷阱）
4. **桥实现要求**：connect 失败抛具体异常类型；内部有状态时自行加 Lock

### 四、行动项

- 涉及生态桥接入的同学：按规范文档第 4 节集成，跑 `tests/test_ecosystem_bridge.py` 9 个用例确认
- 合并/开发其他功能前：先 `git pull` 拉取以上 3 个 commit，避免基于旧代码开发

【如有问题，回复本邮件或找【负责人】沟通】

---

后端团队
2026-08-12
