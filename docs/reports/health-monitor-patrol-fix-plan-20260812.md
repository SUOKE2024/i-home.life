# health_monitor 巡检报错修复方案

> 报错：`health_check_project_error: project=50cffb0e... error=Multiple rows were found when one or none was required`
> 发现时间：2026-08-12（生产日志巡检）
> 状态：已修复 + 回归测试通过

## 一、问题现象

生产日志 `journalctl -u ihome` 每轮巡检出现：

```
health_check_project_error: project=50cffb0e-c66b-464b-9fa5-c9a32f2215a9
error=Multiple rows were found when one or none was required
```

仅在巡检**演示项目**（云栖雅苑 · 智能整装）时出现，重启前后均复现（09:58 与 10:36）。

## 二、根因分析

**触发点**：`app/services/health_monitor.py` `_trigger_alerts` 去重逻辑（修复前第 360-368 行）：

```python
existing = await db.execute(
    select(ProgressAlert).where(
        ProgressAlert.project_id == project.id,
        ProgressAlert.alert_type == "health_check",
        ProgressAlert.status == "active",
    )
)
if existing.scalar_one_or_none():
    continue
```

**根因**：
1. `progress_alerts` 表对 `(project_id, alert_type, status)` **无唯一约束**（[progress_alert.py](file:///Users/netsong/Developer/i-home.life/app/models/progress_alert.py#L18-L31) 仅 `id` 主键 + 单列索引）
2. 生产实测该项目存在 **2 条** `(50cffb0e, health_check, active)` 记录（来源：演示种子数据多次注入/历史遗留）
3. `scalar_one_or_none()` 语义要求结果 ≤1 行，遇 2 行抛 `MultipleResultsFound`，异常被外层 [run_check](file:///Users/netsong/Developer/i-home.life/app/services/health_monitor.py#L241-L254) 的 try/except 捕获后仅记录日志，**该项目的本轮预警被整体中断**

**为何本地测试未暴露**：现有测试仅覆盖 `HealthRuleEngine`（纯计算），无 `_trigger_alerts` 的 DB 去重路径测试；且本地 SQLite 每次建库无重复数据。

## 三、修复方案

**思路**：去重的本质是「存在即跳过」，无需唯一性假设。用 `limit(1)` 取首行判定即可。

**修复**（[health_monitor.py](file:///Users/netsong/Developer/i-home.life/app/services/health_monitor.py#L359-L373)）：

```python
# 检查是否已有同类活跃预警（去重）
# 注意：progress_alerts 表对 (project_id, alert_type, status) 无唯一约束，
# 同组合可能存在多条 active 记录（如历史数据/并发巡检），
# scalar_one_or_none() 遇多条会抛 MultipleResultsFound（生产曾致巡检 500）。
# 此处只需「存在即跳过」，用 limit(1) 取首行判定。
from sqlalchemy import select
existing = await db.execute(
    select(ProgressAlert.id).where(
        ProgressAlert.project_id == project.id,
        ProgressAlert.alert_type == "health_check",
        ProgressAlert.status == "active",
    ).limit(1)
)
if existing.scalar() is not None:
    continue
```

**方案选型说明**：
- `select(id).limit(1)` + `scalar()`：不加载整行、不假设唯一，任何行数均安全 ✅（采纳）
- 备选 1：`scalars().first()`：等价可行，但 `limit(1)` 语义更显式
- 备选 2：加 `(project_id, alert_type, status)` 部分唯一索引：可防数据继续膨胀，但属 DB 迁移、且「同项目同类型多条 active」在业务上可能合理（不同 phase），**不采用**
- 备选 3：软删除/归档：与预警业务语义不符，**不采用**

## 四、回归测试

新增 [test_health_monitor_patrol.py](file:///Users/netsong/Developer/i-home.life/tests/test_health_monitor_patrol.py)（3 用例，全部通过）：

| 用例 | 场景 | 断言 |
|------|------|------|
| `test_trigger_alerts_with_duplicate_active_alerts_no_crash` | 预置 2 条同组合 active | 不抛错 + 数量保持 2（不重复创建） |
| `test_trigger_alerts_creates_when_none_active` | 无 active 预警 | 正常创建 1 条 |
| `test_trigger_alerts_skips_when_single_active_exists` | 已有 1 条 active | 跳过，数量保持 1 |

验证：`tests/test_health_monitor_patrol.py` + `tests/test_v1129_gap_filling.py` 共 **54 passed**，flake8/mypy 0 issues。

## 五、生产数据处置建议（可选项）

生产项目 50cffb0e 存在 2 条重复 active 预警。修复后**功能不受影响**（去重跳过），但可执行以下清理消除冗余：

```sql
-- 保留最新一条，其余同组合 active 置为 resolved（谨慎，需先确认业务无引用）
-- 建议通过应用层脚本处理而非裸 SQL，走 resolved 而非 DELETE（保审计）
```

**暂不执行**：该数据无功能危害，且涉及生产写操作需业务确认；已记录为遗留项。

## 六、同类隐患排查

本次只修了 `_trigger_alerts` 一处。全库搜索 `scalar_one_or_none()` 在「查询条件无唯一约束」场景的使用，是后续扩展项（建议纳入常规代码审查点）。
