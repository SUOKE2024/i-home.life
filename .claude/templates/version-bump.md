# 版本号升级清单（version-bump.md）

> 吸取 v1.2.9 教训：发布时 11 处版本号未同步（散布 1.2.6/1.2.7/1.2.8/1.2.9），全链路漏改。
> 本文件列出**所有**需同步位置，发布前逐项核对，不得凭记忆。
> **2026-09-22 刷新**：补齐此前漏登的 `app/mcp/server.py` 与 `webapp/package.json`，
> 并校准全部行号（旧版行号为 v1.14.x 时期，已漂移）。

## 两套版本号体系（勿混淆）

| 体系 | 格式 | 范围 | 同步方式 |
|------|------|------|---------|
| **语义版本** | `1.3.0` (+ build号) | 跨全端（后端+MCP+Flutter+Web app+Web 控制台+CI+部署脚本+测试断言） | 手动逐处改 |
| ~~Web 缓存版本~~（已废弃） | — | 旧 `web/` 已迁移至 `webapp/`（Vite 自动 hash） | 无需同步 |

---

## 一、语义版本同步清单（**17 处**，改一处不够）

升级语义版本（如 `1.3.0` → `1.3.1`）时，**以下全部要改**：

### 后端 Python（6 处）
- [ ] `app/config.py` → `app_version: str = "X.Y.Z"`（line 32）
- [ ] `app/mcp/server.py` → `SERVER_VERSION = "X.Y.Z"`（line 74，**v1.17.1 补登**——此前长期漏登，
      但 `tests/test_v1_3_0_compliance.py` / `test_mcp_2026_07_28.py` 会断言此常量，漏改即红）
- [ ] `.env` → `APP_VERSION=X.Y.Z`（line 2）
- [ ] `.env.example` → `APP_VERSION=X.Y.Z`（line 2）
- [ ] `.env.production` → `APP_VERSION=X.Y.Z`（line 2）
- [ ] `.env.production.example` → `APP_VERSION=X.Y.Z`（line 2）

### Flutter 多端（3 处）
- [ ] `flutter_app/pubspec.yaml` → `version: X.Y.Z+NN`（line 4，+后是 build 号，每次发版递增）
- [ ] `flutter_app/lib/config.dart` → `static const String appVersion = 'X.Y.Z';`（line 32）
- [ ] `flutter_app/lib/pages/settings_page.dart` → 版本号字符串（line 284，硬编码）

### Web / 控制台（3 处）
- [ ] `webapp/public/version.json` → `"version":"X.Y.Z","build_number":"NN"`（与 pubspec build 号一致）
- [ ] `webapp/package.json` → `"version": "X.Y.Z"`（line 4，**v1.17.1 补登**——曾静默停在 `1.15.10`
      长达多个版本，因当时未列入本清单）
- [ ] `console-src/package.json` → `"version": "X.Y.Z.0"`（line 4，四位，末位固定 0）

### CI / 部署脚本（2 处，ci.yml 含 3 个 APP_VERSION）
- [ ] `.github/workflows/ci.yml` → `APP_VERSION: "X.Y.Z"`（**共 3 处**：line 44 / 228 / 454，全改）
- [ ] `scripts/deploy-production.sh` → `APP_VERSION=X.Y.Z`（line 21）

### 测试文件硬编码版本断言（3 文件 / 6 断言）
- [ ] `tests/test_v1_3_0_compliance.py` → `assert get_settings().app_version == "X.Y.Z"`（line 36）
      + `assert mcp_server.SERVER_VERSION == "X.Y.Z"`（line 42）；两处 docstring（line 35 / 40）同步
- [ ] `tests/test_v1128_suoke_borrowed.py` → `test_app_version_bumped` 内
      `assert get_settings().app_version == "X.Y.Z"`（line 476），docstring（line 474）同步
- [ ] `tests/test_mcp_2026_07_28.py` → `assert mcp_server.SERVER_VERSION == "X.Y.Z"`（line 77）

> 注：功能溯源注释（如 `# v1.17.0：F41 适老改造补贴资格预检`）**不改**——它记录特性引入版本，
> 与当前版本号无关；残留扫描时须区分「当前版本号」与「历史溯源注释」。

---

## 二、Web 缓存版本同步（已废弃：web/ → webapp/）

> 2026-08-08 起旧 `web/` 静态多页迁移至 `webapp/`（Vite+React，构建产物自动 hash，无需手动 `?v=` / `sw.js` CACHE_VERSION）。本节仅作历史回滚参考；`scripts/bump-version.sh` 在 `web/` 目录不存在时直接提示退出。

---

## 三、build 号规则（Flutter）

- `pubspec.yaml` 的 `version: X.Y.Z+NN`，`NN` 是 build 号
- 每次 Flutter 发版 build 号 +1（如 `1.3.0+27` → `1.3.0+28` 修bug，或 `1.3.1+28` 升级）
- `webapp/public/version.json` 的 `build_number` 必须与 `pubspec.yaml` 的 `+NN` 一致
- 应用商店（App Store / 华为 AGC）按 build 号区分构建

---

## 四、发布前验证命令

```bash
# 0. 设定本次版本（替换 X.Y.Z / PREV）
NEW=X.Y.Z; PREV=1.17.0

# 1. 核验版本号一致性（应全部输出新版本号）
grep -rn "$NEW" app/config.py app/mcp/server.py \
  .env .env.example .env.production .env.production.example \
  .github/workflows/ci.yml scripts/deploy-production.sh \
  flutter_app/pubspec.yaml flutter_app/lib/config.dart \
  flutter_app/lib/pages/settings_page.dart \
  webapp/public/version.json webapp/package.json console-src/package.json \
  tests/test_v1_3_0_compliance.py tests/test_v1128_suoke_borrowed.py tests/test_mcp_2026_07_28.py

# 2. 检查旧版本号残留（排除历史溯源注释：grep 结果中带 "v$PREV：" 的注释行不改）
grep -rn "$PREV" app/ .github/ scripts/ flutter_app/lib flutter_app/pubspec.yaml \
  webapp/public webapp/package.json console-src/package.json tests/ 2>/dev/null | grep -v __pycache__

# 3. build 号一致性（pubspec +NN 与 version.json build_number 必须相同）
grep -n "version:" flutter_app/pubspec.yaml; cat webapp/public/version.json

# 4. 前端单测（webapp，Vitest + jsdom）
cd webapp && npm ci && npm test && npm run build && cd ..

# 5. 全量测试不得回退，并同步基线（新增测试后必须校准）
pytest
python scripts/check_test_baseline.py --update   # 以实测通过数更新 scripts/test_baseline.json
python scripts/check_test_baseline.py            # 复跑核对（passed>=基线）
# 同步 CLAUDE.md / CHANGELOG.md / README.md 中记录的基线数字

# 6. pre-commit 全量（含 release 前手动跑测试基线门禁）
pre-commit run --all-files
pre-commit run --hook-stage manual test-baseline   # 全量 pytest 基线门禁（约 30 分钟，故不随每次 commit 触发）
```

---

## 五、历史教训（勿重蹈）

- **v1.17.1（2026-09-22）**：清单**漏登** `app/mcp/server.py`（`SERVER_VERSION`）与
  `webapp/package.json`——后者静默停在 `1.15.10` 多个版本无人察觉；且清单行号整体漂移
  （ci.yml 记 40/182/387 实为 44/228/454、config.dart 记 30 实为 32、settings_page 记 272 实为 284）。
  **对策**：本清单已补齐位置 + 校准行号；后续若新增版本承载文件（如新的端/新的 package.json），
  必须在同一 PR 内补登本清单。
- **v1.2.9**：11 处版本号未同步（config.py / .env / .env.example / .env.production / pubspec / config.dart / settings_page.dart / version.json / sw.js CACHE_VERSION / web 资源 v= / deploy-production.sh / ci.yml 多处 / console-src package.json）
- **v1.2.6**：CI ×3 处 APP_VERSION 漏改
- **v1.2.5**：全项目版本号统一至 1.2.5 才修复
- **v1.2.4**：pubspec 与 config.dart 不一致

**根因**：凭记忆改版本号，遗漏分散位置。**对策**：每次发布走本 checklist，逐项打勾。