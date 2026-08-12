# 索克家居 v1.13.x 发布前 QA 缺陷跟踪表

**测试日期**: 2026-08-12 | **被测版本**: 后端 1.13.1 / webapp 1.13.1 / Flutter 1.13.3+43 | **环境**: 本地开发库 + 生产 i-home.life

## 缺陷清单

| ID | 模块 | 严重度 | 描述 | 发现方式 | 状态 | 修复/结论 | 回归验证 |
|----|------|--------|------|----------|------|-----------|----------|
| BUG-001 | 演示数据-智能家居 | 中 | 云栖雅苑演示项目智能家居方案 4 个（预期 3）、设备 10 个（预期 8），存在外部测试残留方案（客厅/xiaomi/zigbee/draft，2 设备） | verify_demo_projects 全景验证 FAIL 2/44 | ✅ 已修复 | 删除残留方案及关联设备（data/ihome.db） | 全景验证 PASS 44/44 |
| BUG-002 | 测试数据残留 | 低 | bench-api.py 压测注册的 bench 用户（13925987918）残留本地库 | 性能基准后检查 | ✅ 已清理 | 删除 bench 测试用户 | 数据核对无残留 |
| OBS-001 | E2E-静态资源 | 信息 | E2E 8 项失败：7 项静态文件（index.html/version.json/favicon.png/logo.png/robots.txt/sitemap.xml/assets/）HTTP 404 | e2e_test.py（本地 8000）19/27 | ✅ 生产确认正常 | 本地 uvicorn 不服务 webapp/dist；生产 Nginx 全部 200（/assets/ 403 为目录拒绝列表预期） | 生产 curl 核验 |
| OBS-002 | 健康检查 | 信息 | GET /api/health/detail 返回 503（degraded）：磁盘 free 10.09% 预警 + 本地 Redis/Vault 未配置 | e2e_test.py | ✅ 生产确认正常 | 诚实降级路径生效；生产 Redis/db/disk 全 ok（free 51.06%） | 生产 health/detail 核验 |
| OBS-003 | 性能-OpenAPI | 低 | OpenAPI 规范生成 P90=6372ms（P50=47ms），动态生成拖慢首次拉取 | bench-api.py 性能基准 | ✅ 已解决 | lifespan 启动时预热 `app.openapi()` 缓存（预序列化+预压缩 bytes，490 路由首次生成约 2-6s 移至启动期，运行期首请求零延迟命中缓存）；新增 tests/test_openapi.py 3 用例 | openapi 测试 3 passed + 预热路径验证（1.92s 生成/594 paths） |

## 测试执行进度

| 测试项 | 工具/方式 | 结果 | 状态 |
|--------|-----------|------|------|
| 功能测试-全量 | pytest 全量（约 2200+ 用例） | 回归依据：当日 r2 **2230 passed**；发布验证期外部独占测试资源（3+ 套全量并发 + SIGTERM 终止新进程），无法干净重跑 | ✅（以 r2 + 子集） |
| 功能测试-全景 | verify_demo_projects.py | **PASS 44/44** | ✅ |
| 功能测试-E2E | e2e_test.py（本地） | 19/27（8 项本地环境差异，见 OBS-001/002） | ✅ |
| 安全测试 | 12 个安全专项文件 | **154 passed（5:49）**：路径遍历/SQL 注入/XSS/WebAuthn/限流/MCP 安全/治理审计/IDOR | ✅ |
| 性能测试 | bench-api.py（10 并发 × 50 请求/端点） | 核心 API P50 13-26ms；429 限流预期生效；OBS-003 | ✅ |
| 兼容性-webapp | npm run build | ✓ 构建成功 13.88s | ✅ |
| 兼容性-console | npm run build（console-src） | ✓ 构建成功 9.75s（产物 webapp/dist/console/） | ✅ |
| 兼容性-Flutter | flutter analyze | No issues found（53.1s） | ✅ |
| 测试数据清理 | bench 用户/残留方案 | BUG-001/002 已清理 | ✅ |
