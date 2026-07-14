# 索克家居 · 生产部署指南

## 前置条件
- 服务器：Linux (Ubuntu 20.04+ / CentOS 8+)
- Python 3.11+
- Nginx 1.20+
- PostgreSQL 15+（或 SQLite 用于测试）

## 部署步骤

### 1. 克隆仓库
```bash
git clone <repo-url> /opt/ihome
cd /opt/ihome
```

### 2. 配置环境变量
```bash
cp .env.example .env.production
# 编辑 .env.production，填入真实配置：
#   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ihome
#   SECRET_KEY=<64位随机字符串>
#   DEEPSEEK_API_KEY=<可选>
#   GLM_API_KEY=<可选>
```

### 3. 安装 Python 依赖
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. 部署前检查
```bash
bash scripts/deploy-check.sh
```

### 5. 全量部署
```bash
bash scripts/deploy-production.sh
```

### 6. 仅 Web 部署（更新前端）
```bash
bash scripts/quick-deploy-web.sh
```

### 7. 验证部署
```bash
bash scripts/e2e-pages.sh http://localhost:8766
curl http://localhost:8081/api/health
```

### 8. 管理命令
```bash
# 查看服务状态
launchctl list | grep ihome    # macOS
systemctl status ihome         # Linux

# 重启服务
launchctl stop com.ihome.life; launchctl start com.ihome.life   # macOS
systemctl restart ihome                                           # Linux

# 查看日志
tail -f /opt/ihome/data/server.log
```

## HTTPS 配置
```bash
sudo certbot --nginx -d i-home.life -d www.i-home.life
```

## 故障排除
- WebSocket 连接失败：确认 nginx 配置包含 /ws/ location 块
- 静态资源 404：确认 nginx root 指向正确的 web/ 目录
- API 502：确认 FastAPI 服务正在运行（端口 8000）
- 跨域错误：确认 .env.production 中配置了正确的 CORS 白名单
