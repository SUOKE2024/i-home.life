# 版本号升级清单（version-bump.md）

> 吸取 v1.2.9 教训：发布时 11 处版本号未同步（散布 1.2.6/1.2.7/1.2.8/1.2.9），全链路漏改。
> 本文件列出**所有**需同步位置，发布前逐项核对，不得凭记忆。

## 两套版本号体系（勿混淆）

| 体系 | 格式 | 范围 | 同步方式 |
|------|------|------|---------|
| **语义版本** | `1.3.0` (+ build号) | 跨全端（后端+Flutter+Web控制台+CI+部署脚本） | 手动逐处改 |
| ~~Web 缓存版本~~（已废弃） | — | 旧 `web/` 已迁移至 `webapp/`（Vite 自动 hash） | 无需同步 |

---

## 一、语义版本同步清单（12 处，改一处不够）

升级语义版本（如 `1.3.0` → `1.3.1`）时，**以下全部要改**：

### 后端 Python（5 处）
- [ ] `app/config.py` → `app_version: str = "X.Y.Z"`（line 32）
- [ ] `.env` → `APP_VERSION=X.Y.Z`（line 2）
- [ ] `.env.example` → `APP_VERSION=X.Y.Z`（line 2）
- [ ] `.env.production` → `APP_VERSION=X.Y.Z`（line 2）
- [ ] `.env.production.example` → `APP_VERSION=X.Y.Z`（line 2）

### Flutter 多端（3 处）
- [ ] `flutter_app/pubspec.yaml` → `version: X.Y.Z+NN`（line 4，+后是 build 号，每次发版递增）
- [ ] `flutter_app/lib/config.dart` → `static const String appVersion = 'X.Y.Z';`（line 30）
- [ ] `flutter_app/lib/pages/settings_page.dart` → 版本号字符串（line 272，硬编码）

### Web / 控制台（2 处）
- [ ] `webapp/public/version.json` → `"version":"X.Y.Z","build_number":"NN"`（与 pubspec build 号一致）
- [ ] `console-src/package.json` → `"version": "X.Y.Z.0"`（line 4，四位，末位固定 0）

### CI / 部署脚本（2 处，ci.yml 含 3 个 APP_VERSION）
- [ ] `.github/workflows/ci.yml` → `APP_VERSION: "X.Y.Z"`（**共 3 处**：line 40 / 182 / 387，全改）
- [ ] `scripts/deploy-production.sh` → `APP_VERSION=X.Y.Z`（line 21）

### 测试文件硬编码版本断言（v1.4.0 补登，v1.2.9 教训延伸）
- [ ] `tests/test_v1_3_0_compliance.py` → `assert app_version == "X.Y.Z"` + `assert SERVER_VERSION == "X.Y.Z"`（函数名也含版本号，同步改）
- [ ] `tests/test_mcp_2026_07_28.py` → `assert mcp_server.SERVER_VERSION == "X.Y.Z"`
- [ ] `tests/test_v1128_suoke_borrowed.py` → `test_app_version_bumped` 内 `assert get_settings().app_version == "X.Y.Z"`（docstring 也含版本号）

---

## 二、Web 缓存版本同步（已废弃：web/ → webapp/）

> 2026-08-08 起旧 `web/` 静态多页迁移至 `webapp/`（Vite+React，构建产物自动 hash，无需手动 `?v=` / `sw.js` CACHE_VERSION）。本节仅作历史回滚参考；`scripts/bump-version.sh` 在 `web/` 目录不存在时直接提示退出。

---

## 三、build 号规则（Flutter）

- `pubspec.yaml` 的 `version: X.Y.Z+NN`，`NN` 是 build 号
- 每次 Flutter 发版 build 号 +1（如 `1.3.0+27` → `1.3.0+28` 修bug，或 `1.3.1+28` 升级）
- `version.json` 的 `build_number` 必须与 `pubspec.yaml` 的 `+NN` 一致
- 应用商店（App Store / 华为 AGC）按 build 号区分构建

---

## 四、发布前验证命令

```bash
# 1. 核验版本号一致性（应全部输出新版本号，无残留旧号）
grep -rn "1\.3\.0" app/config.py .env .env.example .env.production .env.production.example \
  flutter_app/pubspec.yaml flutter_app/lib/config.dart \
  flutter_app/lib/pages/settings_page.dart \
  webapp/public/version.json console-src/package.json \
  .github/workflows/ci.yml scripts/deploy-production.sh

# 2. 检查是否有旧版本号残留（替换 X.Y.Z 为上一版本）
grep -rn "1\.2\.9" app/config.py .env* flutter_app/ webapp/public/version.json console-src/ \
  .github/ scripts/ 2>/dev/null

# 3. Web 缓存版本（已废弃：web/ → webapp/，Vite 自动 hash，无需校验）

# 4. 跑全量测试不得回退
pytest

# 5. pre-commit 全量
pre-commit run --all-files
```

---

## 五、历史教训（勿重蹈）

- **v1.2.9**：11 处版本号未同步（config.py / .env / .env.example / .env.production / pubspec / config.dart / settings_page.dart / version.json / sw.js CACHE_VERSION / web 资源 v= / deploy-production.sh / ci.yml 多处 / console-src package.json）
- **v1.2.6**：CI ×3 处 APP_VERSION 漏改
- **v1.2.5**：全项目版本号统一至 1.2.5 才修复
- **v1.2.4**：pubspec 与 config.dart 不一致

**根因**：凭记忆改版本号，遗漏分散位置。**对策**：每次发布走本 checklist，逐项打勾。
