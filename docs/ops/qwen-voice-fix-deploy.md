# Qwen-Audio 音色配置修复与生产部署操作手册

> 适用版本：v1.13.1
> 更新日期：2026-08-12
> 背景：Qwen-Audio-3.0-Realtime 服务端在 `QWEN_AUDIO_VOICE=cherry` 时返回 `Unsupported voice: 'cherry'`，导致实时语音会话无法正常输出。本手册记录修复方式与部署流程。

## 1. 问题现象

实时语音 WebSocket 会话建立后，发送任何文本/音频指令立即返回：

```json
{"type": "error", "message": "Unsupported voice: 'cherry'. Supported voices: longanqian, longanlingxin, ..."}
```

根因：`cherry` 是旧版 Qwen3-TTS 音色，不在 Qwen-Audio-3.0-Realtime 支持列表中。

## 2. 修复内容

将默认音色从 `cherry` 改为 `longanxiaoxin`（受支持音色之一），涉及 3 个文件：

| 文件 | 修改 |
|------|------|
| `app/config.py` | `qwen_audio_voice` 默认值 `"cherry"` → `"longanxiaoxin"` |
| `.env.example` | `QWEN_AUDIO_VOICE=cherry` → `QWEN_AUDIO_VOICE=longanxiaoxin` |
| `.env.production` | 新增 `QWEN_AUDIO_VOICE=longanxiaoxin` |

`.env.production` 显式声明音色，避免依赖代码默认值（更明确、可独立调整）。

## 3. 生产部署流程

### 3.1 前置检查

```bash
# SSH 连通性 + 服务状态
ssh root@118.31.223.213 "systemctl is-active ihome"
```

### 3.2 部署后端（含 .env.production 同步）

```bash
cd /Users/netsong/Developer/i-home.life
bash scripts/deploy-remote.sh backend
```

脚本会：
1. rsync 后端代码到 `/opt/ihome`（排除 .env*、flutter_app、web 等）
2. 推送 `.env.production` → 服务器 `/opt/ihome/.env`
3. 远程安装依赖、重启 `ihome` systemd 服务

### 3.3 部署验证

```bash
# 1. 健康检查
curl -s https://i-home.life/health
# 期望: {"status":"ok","app":"索克家居","version":"1.13.1",...}

# 2. 服务器音色配置已生效
ssh root@118.31.223.213 "grep QWEN_AUDIO_VOICE /opt/ihome/.env"
# 期望: QWEN_AUDIO_VOICE=longanxiaoxin

# 3. 服务运行中
ssh root@118.31.223.213 "systemctl status ihome --no-pager | head -5"
```

## 4. 语音流程回归验证

使用模拟脚本走通「帮我设计厨房 → 方案B加中岛」完整链路：

```bash
cd /Users/netsong/Developer/i-home.life
source .venv/bin/activate
python scripts/simulate_voice_proposal_flow.py https://i-home.life
```

通过标准：
- 第一步收到 `proposal_generated`（3 套方案）
- 第二步收到 `proposal_updated`（方案 B 修订成功）
- **全程无 `Unsupported voice` 错误**，且有 `audio_delta` 音频帧输出（证明 TTS 音色生效）

## 5. 回滚

如音色调整后出现问题，恢复原配置：

1. 本地：`git checkout app/config.py .env.example`（还原默认值）
2. 生产：`.env.production` 删除或改回 `QWEN_AUDIO_VOICE`，重新执行 `bash scripts/deploy-remote.sh backend`

## 6. 注意事项

- 音色列表以 Qwen-Audio-3.0-Realtime 服务端返回为准（错误消息中会列出全部支持的 voices）
- 修改 `.env.production` 后**必须重新部署**才会同步到服务器 `.env`（deploy-remote.sh backend 会推送）
- 部署后验证语音时若遇网络超时，先检查 `flutter_app/lib/config.dart` 的 `API_BASE_URL`（生产应为 `https://i-home.life/api`）
