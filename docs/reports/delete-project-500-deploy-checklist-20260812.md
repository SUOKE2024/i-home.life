# 生产 DELETE /projects 500 修复部署检查清单

> 适用版本：v1.13.1 → v1.13.1（代码修复，无版本号变更）
> 修复内容：`app/services/project_service.py` `delete_project` 生产 PostgreSQL FK 级联删除
> 验证日期：2026-08-12

## 背景

`lifecycle_orchestration_enabled=True`（v1.13.2 默认开启）时项目创建经 EventBus 自动建预算
（`budgets.project_id` FK → `projects.id`，无 ON DELETE CASCADE），而 `delete_project` 仅删除
projects 行。生产 PostgreSQL 严格 FK 约束下 DELETE 返回 500；SQLite 测试默认不强制 FK 故本地未暴露。

## 前置检查（部署前）

- [ ] 本地代码已通过质量门禁：
  - [ ] 全量 pytest：2156 passed / 2 skipped / 4 xfailed（`.venv/bin/python`）
  - [ ] 新增回归测试 `test_delete_project_cascades_related_data_with_fk` 通过（28/28）
  - [ ] flake8 0 issues（max-line-length=120, max-complexity=15）
  - [ ] mypy 0 issues
- [ ] 修复代码包含 `_cascade_delete_related`（git diff 可查）
- [ ] `scripts/test_baseline.json` 与 CLAUDE.md 基线同步（2156/2/4）
- [ ] 确认远程服务可达：`bash scripts/deploy-remote.sh status`（记录修复前版本号 v1.13.1）

## 部署执行

- [ ] 执行 `bash scripts/deploy-remote.sh backend`（仅推后端代码 + 重启 uvicorn）
- [ ] rsync 无报错（观察 sent/received bytes）
- [ ] 输出「✅ 后端已重启」
- [ ] 确认远程代码生效：
  - [ ] `ssh root@118.31.223.213 "grep -c '_cascade_delete_related' /opt/ihome/app/services/project_service.py"` ≥ 1
  - [ ] `systemctl status ihome` Active: running（注意重启时间戳更新）
  - [ ] `curl https://i-home.life/health` 返回 status ok + version 1.13.1

## 生产 E2E 验证（部署后）

- [ ] 运行 `python scripts/e2e_test.py`（脚本已同步修复：materials/categories list 兼容 + webapp 静态资源检查）
- [ ] **关键项**：`[8] 清理 DELETE /projects/:id -> 200/204` 必须 OK（修复前为 HTTP 500）
- [ ] 全量通过率 ≥ 前次基线（本修复后实测 29/29 = 100%）
- [ ] 其他关键链路抽查：
  - [ ] `[2] PASETO 认证`：login/me/invalid token 均 OK
  - [ ] `[4] Agent 真实 LLM`：designer/concierge/budget/settlement 均 OK
  - [ ] `[7] 健康检查详情`：database ok、secret_manager enabled

## 修复后回归

- [ ] 删除带预算/户型/预算行的项目返回 204 且关联数据级联清空（本地回归测试覆盖）
- [ ] 越权删除仍返回 403（`test_delete_other_user_project_returns_403`）
- [ ] 项目删除触发 `project.deleted` WS 广播（`test_project_delete_triggers_broadcast`）

## 回滚方案

- [ ] 回滚命令：`bash scripts/deploy-remote.sh backend`（推送上一 commit 代码后重启）
- [ ] 或 `bash scripts/rollback.sh <上一版本>`（如涉及版本变更）
- [ ] 回滚后重跑 E2E 确认 DELETE 行为恢复（注意：回滚将重新引入 FK 500，属已知回归）

## 结果记录

| 项目 | 值 |
|------|-----|
| 部署时间 | 2026-08-12 10:36 CST |
| 生产版本 | v1.13.1（代码修复） |
| 远程 `_cascade_delete_related` 命中 | 2 |
| E2E 通过率 | 29/29 (100%) |
| DELETE /projects/:id | 200/204 ✅（修复前 500） |
