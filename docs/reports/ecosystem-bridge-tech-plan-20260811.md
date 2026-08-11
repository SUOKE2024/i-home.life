# A1 生态桥接技术方案调研报告（HomeKit / Matter / Tuya / HarmonyOS）

> 日期：2026-08-11 · 对应 backlog A1（`app/services/ecosystem_bridge.py` 唯二 stub 之最高优先）
> 状态：纯技术调研（未触外部凭据），供商务/技术决策后落地

## 0. 核心架构前提（最重要结论）

**HomeKit HAP 与 Matter 都是局域网协议**（mDNS 发现 + 链路本地通信），本项目 FastAPI 部署在阿里云
ECS 上**无法直接参与设备配对与控制**。2026 年可落地的形态必须是「云 API + 家庭侧边缘节点」两段式：

- 边缘节点（用户家庭网关/自研轻量进程/HAOS）承载两个生态的协议栈
- 云端 ECS 只做：凭据/配对码下发、设备清单与状态同步（边缘推送到云）、指令编排
- 若坚持纯云架构，则只能接「厂商自有云开放 API」（如 Tuya/IoTDA），无法直接接入 HAP/Matter

## 1. HomeKit（Apple HAP）

| 角色 | 推荐库 | 说明 |
|---|---|---|
| 服务端（Accessory/Bridge） | [HAP-python](https://github.com/ikalchev/HAP-python) v5.0.0（Apache-2.0，活跃） | 把 i-home.life 设备/场景暴露进 Apple Home；`pyhap.accessory.Bridge` 挂多个 accessory，扫码一次配对 |
| 客户端（Controller） | [aiohomekit](https://github.com/Jc2k/aiohomekit) v4.x（Apache-2.0，HA 高频维护） | 主动发现/配对/控制市售 HomeKit 设备 |

- **配对**：8 位配对码 `XXX-XX-XXX` + Setup Payload（`X-HM://` QR）；SRP + Ed25519 + ChaCha20-Poly1305（库内置）
- **关键约束**：一个 accessory 同一时刻仅一个 controller 配对（已在 Apple Home 的设备需先重置）；iCloud 远程由苹果家庭中枢中转，第三方后端无法复用
- **五方法映射**：connect=启动 AccessoryDriver（等待被配对）；get_devices=枚举 bridge accessories；send_command=set characteristic value（on/off→On，brightness→Brightness）；sync_scenes=**无标准场景原语**，需自定义 Service 或云端批量命令模拟
- **风险**：无官方 MFi 认证（不显示认证标识但可正常使用）；维护依赖社区（版本节奏慢，需锁版本）

## 2. Matter（CSA 标准）

| 角色 | 推荐方案 | 说明 |
|---|---|---|
| Controller | [python-matter-server](https://github.com/home-assistant-libs/python-matter-server) 6.x（Apache-2.0，HA Matter 集成底层） | 独立进程（systemd，WS 5580），FastAPI 内嵌 `MatterClient` 走 WebSocket RPC |
| Device（对外暴露） | Node.js [matterbridge](https://www.npmjs.com/package/matterbridge) v3.10.2（Apache-2.0，活跃） | Python 侧无成熟 Device 实现；子进程管理 matterbridge 插件 |

- **Commissioning**：QR `MT:` + Base38 / 手动 11 位码（Verhoeff）/ NFC；字段含 discriminator(12bit) + passcode(27bit)；PASE(SPAKE2+) → Attestation(DAC) → CASE 五步握手
- **Matter 1.4（2026）**：Thread 1.3.0+ / PSA Level 2 / 零接触配网（ZTC）成为新认证强制项（2026-08-01 生效）；EU 2027-01 起 CE-Matter 强制
- **五方法映射**：connect=启动 MatterServer + MatterClient WS 连接（storage path + vendor/fabric id）；get_devices=client.get_nodes()；send_command=send_command(node_id, endpoint_id, cluster_id, command_name, payload)；sync_scenes=Matter 1.3+ 标准 Scenes cluster（需 adapter 层自建）
- **风险**：chip Python 绑定仅特定平台 wheel；Thread 依赖边界路由器；WS RPC 非稳定公共 API（需锁版本）；跨 VLAN/LAN 失效

## 3. Tuya（涂鸦）— 云端可立即落地

| 方案 | 库 | 说明 |
|---|---|---|
| 云端（推荐） | [tuya-connector-python](https://github.com/tuya/tuya-connector-python)（官方，MIT） | `TuyaOpenAPI(endpoint, access_id, access_secret)` 自动签名+token 刷新 |
| 局域网增强 | [tinytuya](https://github.com/jasonacox/tinytuya)（社区高活跃，MIT） | 本地 TCP 6668 + UDP 6666/6667/7000，延迟 ~200ms；**需 local_key**，仅家庭侧网关部署可行 |

- **凭据**：`Access ID / Access Secret` + 区域 endpoint（中国 `openapi.tuyacn.com`；token 有效期 ~2h SDK 自动刷新）
- **五方法映射**：get_devices=GET /v1.0/iot-01/associated-users/devices；get_device_state=GET /v1.0/devices/{id}/status；send_command=POST /v1.0/devices/{id}/commands（command→DP code 映射表，如 turn_on→switch_led）；sync_scenes=场景 API（query_scenes/trigger_scene）
- **限额**：50 万次/天、500 次/秒；高频轮询建议走 Pulsar 订阅
- **风险**：官方 `tuya-iot-py-sdk` 停滞 4 年（不直接用，参考高层封装）；新固件可能关闭本地 API；local_key 重配网即失效

## 4. HarmonyOS（鸿蒙）— 无自助 API，改接 IoTDA

**关键判断**：HarmonyOS Connect 是 B2B 硬件伙伴生态，**2026 年不存在面向普通第三方的公开 Python SDK**
（华为官方论坛 2026-03 确认"鸿蒙智选摄像头只能对接智慧生活，无其他对外接口"）。可自助落地的替代路径：

| 路径 | 方案 | 说明 |
|---|---|---|
| 近期（推荐） | 华为云 **IoTDA**（`huaweicloudsdkiotda` v3.1.2xx，Apache-2.0，月度更新） | 设备影子/命令/消息/规则引擎；凭据为 IAM **AK/SK + project_id**（现有 `app_id/app_secret` 模型需改造） |
| 中期 | 云云对接伙伴计划（商务路径） | OAuth2.0 用户级 AT + 应用级 AT；需华为账号一键登录/隐私合规；无公开 SDK 自行实现 |
| 兜底 | Matter / 国标 GB/T 46456（2026-02 实施）桥接 | 存量鸿蒙设备收敛为标准协议设备 |

- **IoTDA 五方法映射**：get_devices=list_devices()；get_device_state=show_device_shadow()（影子 reported 区）；send_command=create_command()（同步优先，MQTT 设备）；sync_scenes=规则引擎/批量命令
- **前提**：IoTDA 只能控制**已注册设备**，存量鸿蒙智联设备无法自动纳管（需厂商配合或 Matter 桥接）
- **免费额度**：标准版免费单元 S0，单实例 100 单元、峰值 10W 并发

## 5. 落地路线建议

1. **立即可做（无商务门槛）**：`TuyaBridge` 用 `tuya-connector-python` 实现云端五方法（凭据模型零改动）
2. **近期（无商务门槛）**：`HarmonyOSBridge` 改接 IoTDA（AK/SK 凭据改造），覆盖设备发现/影子/命令
3. **中期（需边缘节点）**：Matter Controller（python-matter-server）+ HomeKit Controller（aiohomekit）部署于家庭侧网关，云端协调
4. **远期（产品化）**：HAP-python Bridge / matterbridge 对外暴露设备 → CSA 认证（注意 2026-08-01 起 Matter 1.4 强制项）与鸿蒙云云对接商务

**架构不变式**：保持 `EcosystemBridge` 抽象（connect/get_devices/get_device_state/send_command/sync_scenes），
新增适配器层做「统一指令语义 ↔ 各生态 DP/物模型」双向映射；凭据统一存 `EcosystemIntegration.config` JSON；
沿用诚实降级（凭据缺失 `invalid_credentials` / 未实现 `not_implemented`，禁止假数据伪装）。

## Sources

- HAP-python: https://github.com/ikalchev/HAP-python · https://pypi.org/project/HAP-python/
- aiohomekit: https://github.com/Jc2k/aiohomekit · HA PR #177096（v4.0.0）
- python-matter-server: https://github.com/home-assistant-libs/python-matter-server
- matterbridge: https://www.npmjs.com/package/matterbridge
- Matter 1.4 发布（Thread 1.3.0/PSA Level 2 强制）: https://www.atfxcent.com/news/Matter_1_4_Released_Thread_1_3_0_and_PSA_Level_2_Now_Mandatory.html
- tuya-connector-python: https://github.com/tuya/tuya-connector-python
- tinytuya: https://github.com/jasonacox/tinytuya
- 涂鸦限额: https://support.tuya.com/en/help/_detail/K8sdy1i4g9u0q
- 鸿蒙智联云云对接规范 v2.3: https://device.harmonyos.com/cn/docs/DevicePartner-Guides/DevicePartner-Guides/intelligent-cloud-interconnection01-0000002433655052
- 华为开发者论坛（无对外接口确认）: https://developer.huawei.com/consumer/cn/forum/topic/0203209317085897419
- huaweicloudsdkiotda: https://pypi.org/project/huaweicloudsdkiotda/
- IoTDA 产品规格: https://support.huaweicloud.com/intl/zh-cn/productdesc-iothub/iot_04_0014.html
