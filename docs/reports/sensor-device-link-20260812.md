# 设备链路全量诊断修复与验证总结报告

> 日期：2026-08-12
> 范围：摄像头 / 麦克风语音 / 传感器 / 穿戴健康监测 / 场景触发 五条设备链路
> 结论：两条断链已修复（传感器假数据+不落库、穿戴健康零接入），场景触发已真实闭环

---

## 1. 诊断结论（全景）

| 链路 | 后端 | Flutter 端 | 结论 |
|---|---|---|---|
| 摄像头拍照识别 | `app/api/camera_scan.py`（AI 识别+诚实降级） | api.dart 有方法 | ✅ 完整 |
| 麦克风实时语音 | `app/api/voice_realtime.py`（WS 真双工+降级） | voice_realtime_service.dart 完整 | ⚠️ `/voice/process` 绕过 LLM 分类 |
| 传感器 | `app/api/sensor_snapshot.py` **硬编码假数据 + 不落库** | sensor_service.dart 只采集、**从未上传** | ❌ 断链+假数据 |
| 穿戴健康监测 | `app/api/health.py` API 完整 | api.dart **无任何方法** | ❌ 断链 |
| 场景触发 | check_sensor_triggers 逻辑完整但被喂假数据 | - | ⚠️ 触发失真 |

**红线问题**：`sensor_snapshot.py` 曾用加速度计 z 轴伪造 temperature、硬编码 `humidity=0`/`occupancy=True` 触发场景，违反「诚实降级：禁止用硬编码假数据伪装真实能力」。

## 2. 修复内容

### 后端（8 处）

| 文件 | 修复 |
|---|---|
| `app/models/sensor_snapshot.py`（新增） | `sensor_snapshots` 表：真实读数落库（三轴传感器×4 组 + GPS×4 + 环境量×3） |
| `alembic/versions/e2f3a4b5c6d7_*.py`（新增） | 建表迁移（幂等） |
| `alembic/versions/f3a4b5c6d7e8_*.py`（新增） | 补环境量列 temperature/humidity/light_lux（幂等，SQLite batch mode） |
| `app/api/sensor_snapshot.py` | 移除全部硬编码假环境数据；真实落库；ambient_data 仅含真实上报数据（环境量/GPS）；关键节点日志 |
| `app/services/scene_automation_service.py` | `_match_sensor_condition` 空匹配误触发修复（键全缺失返回 False）；逐键匹配 debug 日志 |
| `app/api/voice.py` | `/voice/process` 接通 `_route_intent`（LLM 语义分类优先，此前仅关键词） |
| `app/schemas/sensor_snapshot.py` | 新增环境量字段（environment 传感器真实上报通道） |
| `app/config.py` | **补 `sensor_snapshot_enabled` 字段**（边缘审查发现：此前 Settings 无此字段，`_require_feature` 靠 getattr 兜底默认 True，flag 形同虚设） |

### Flutter（3 处）

| 文件 | 接入 |
|---|---|
| `flutter_app/lib/services/api.dart` | 新增 `uploadSensorSnapshot` + 6 个 health-monitor 方法 |
| `flutter_app/lib/pages/smart_home_page.dart` | 打开页面即上传真实传感器快照；AppBar 新增「健康监测上报」入口（心率/血氧/跌倒/睡眠/活动量） |
| `flutter_app/lib/services/sensor_service.dart` | （既有）采集真实读数，available 标志诚实降级 |

### 关键节点日志（排查数据异常用）

- 上传端：`sensor_snapshot_received → sensor_snapshot_raw(debug) → sensor_snapshot_persisted(含 temp/humidity/lux) → sensor_trigger_check_start/done/skipped`
- 匹配端：`sensor_trigger_scan → sensor_trigger_match → sensor_condition_pass/fail/result(debug) → sensor_trigger_hit`

## 3. Migration 应用与表结构验证

- 当前数据库：`alembic current = f3a4b5c6d7e8 (head)`（含两条迁移）
- `sensor_snapshots` 表 **27 列**：id / user_id / device_id / platform / 加速度计×4 / 陀螺仪×4 / 磁力计×5 / GPS×5 / sampled_at / created_at / **temperature / humidity / light_lux**
- 索引：`ix_sensor_snapshots_user_id`、`ix_sensor_snapshots_device_id`
- `check_schema_drift`：✅ Schema 已对齐
- 空库验证：临时 SQLite 全链 upgrade head 成功

## 4. 实跑验证结果（temperature 触发）

模拟快照（temperature=30.5，harmonyos 环境传感器上报）走真实 API 链路：

```
[1/5] 注册用户 OK
[2/5] 项目 + 高温联动场景创建 OK
[3/5] 上传含 temperature=30.5 快照 status=201 body={'received': True, 'sensors_count': 4}
[4/5] sensor_snapshots 落库记录数 = 1
  temperature=30.5 humidity=55.0 light_lux=320.0
[5/5] scene_behavior_logs 记录数 = 1
  action_type=sensor_trigger  ambient_data={'temperature': 30.5, ...}
  ✅ 场景正确触发：temperature=30.5 > 28 命中高温联动
```

关键日志链：

```
sensor_snapshot_received: platform=harmonyos accel=True gyro=True mag=True gps=True
sensor_snapshot_raw: accel={'x':0.01,'y':0.02,'z':9.81} gps={'latitude':31.23,...}
sensor_snapshot_persisted: temp=30.5 humidity=55.0 lux=320.0 sampled_at=2026-08-12 16:00:00
sensor_trigger_check_start: ambient_data={'temperature': 30.5, 'humidity': 55.0, 'light_lux': 320.0, 'latitude': 31.23, ...}
sensor_trigger_scan: candidate_scenes=1
sensor_condition_pass: key=temperature actual=30.5 expected={'gt': 28}
sensor_condition_result: matched_keys=1 total_keys=1 matched=True
sensor_trigger_match: scene_name=高温联动验证 matched=True
sensor_trigger_hit: actions=1 action_status=pending
sensor_triggers_executed: triggered_count=1
sensor_trigger_check_done: triggered=1
```

**负向验证**（防假数据回潮）：仅加速度计快照不伪造温度触发；GPS-only 快照键全缺失不空匹配误触发 —— 均有测试覆盖。

## 5. 测试与质量门禁

- 新增测试：
  - `tests/test_sensor_snapshot.py` +9：落库断言 / 假数据移除 / GPS-only 不误触发 / 环境量触发 / **flag 关闭 503 / 无效时间戳回退 / temperature=0 合法值参与匹配 / 完全空快照不触发**
  - `tests/test_scene_automation.py` +9：空匹配误触发修复 + **`_match_sensor_condition` 边缘单测（部分键匹配 / 标量条件 / gt+lt 范围比较符 / eq 比较符 / 空 condition / 空 ambient_data）**
- 边缘情况审查发现并修复 1 个真实缺口：`sensor_snapshot_enabled` 未在 Settings 定义（flag 形同虚设）
- 相关模块回归：sensor_snapshot / scene_automation / voice×4 / health×3 / smart_home / matter / camera —— **219 个测试全部通过**
- flake8：0 issues（含修复 config.py 既有 E501 超长行）；mypy：0 issues；flutter analyze：0 issues
- 相关测试用例状态：**全部通过（PASS）**

## 6. 部署提醒

- 生产执行 `alembic upgrade head`（两条迁移，幂等）
- 穿戴健康上报入口在 Flutter「智能家居管理」页 AppBar（需先选择智能方案）
- 环境量（temperature/humidity/light_lux）仅由环境传感器/生态桥接真实上报，手机端不上报不参与匹配
