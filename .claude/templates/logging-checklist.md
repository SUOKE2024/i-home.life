<!--
日志埋点 Checklist 模板
来源：docs/guides/backend-logging-standards.md（后端日志埋点规范 v1.0）
用途：新增日志埋点时复制本节到任务说明/PR 描述中逐项对照。
完整规范（命名/分级/清单/排查示例）见 docs/guides/backend-logging-standards.md
-->

## 日志埋点 Checklist

新增/修改日志时逐项确认（□ 未完成 / ☑ 已完成）：

- [ ] 事件名符合 `<模块>_<动作>_<状态>` snake_case（全小写）
- [ ] 含关联键（user_id / scene_id / device_id / snapshot_id），可跨事件串联
- [ ] 终态事件含结果摘要（`status` / `status_summary` / `note`）
- [ ] 降级/未接入路径有诚实标注（`action_status=pending` + 原因，禁止伪装成功）
- [ ] 无 PII（明文手机号/口令/地址），一律用内部 UUID
- [ ] 主链路 info ≤ 6 条/请求，明细进 debug
- [ ] 异常用 warning/exception，含业务上下文（对象 id + error）

## 埋点自检清单（新增链路时）

- [ ] 主链路事件序列可完整重放：`received → dispatch → done`
- [ ] 每个状态流转有对应日志（pending → success/failed）
- [ ] 明细数据（原始读数/逐键匹配/上下文）在 debug 级
- [ ] 有终态聚合日志（如 `status_summary` 各状态计数）
- [ ] 补充了排查示例（如何用 grep 定位该类问题）
