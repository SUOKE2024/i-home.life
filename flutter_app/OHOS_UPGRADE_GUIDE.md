# Flutter 鸿蒙适配套件升级指南

## 版本信息

| 项目 | 值 |
|------|-----|
| 鸿蒙适配版本 | **Flutter-OH 3.35.7-ohos-0.0.3** |
| 上游 Flutter 版本 | 3.35.7 |
| Dart SDK 版本 | 3.9.2 |
| 升级日期 | 2026-07-08 |
| 分支 | `oh-3.35.7-dev` |
| 仓库 | https://atomgit.com/openharmony-tpc/flutter_flutter |
| 镜像仓库 | https://gitcode.com/openharmony-tpc/flutter_flutter |

> **关于版本号显示**: 由于 Flutter 内部版本解析规则,执行 `flutter --version` 时可能显示为 `3.35.8-ohos-0.0.3`,这是**正常现象**,实际对应的就是 `3.35.7-ohos-0.0.3` 发布版本,无需担心。

---

## 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| DevEco Studio | **6.0.2 Release** 及以上 | 必须版本,内置 hvigor/ohpm/node 工具链 |
| Java JDK | **17** 及以上 | DevEco Studio 自带,也可独立安装 |
| OpenHarmony API | **23** 及以上 | 对应 HarmonyOS NEXT 6.0.0(14) |
| Flutter OHOS SDK | 3.35.7-ohos-0.0.3 | 即本套件 |
| 操作系统 | macOS 12+ / Windows 10+ | 推荐 macOS |

### 环境变量

请在 `~/.zshrc` 或 `~/.bash_profile` 中配置:

```bash
# DevEco Studio 工具链
export DEVECO_SDK_HOME="/Applications/DevEco-Studio.app/Contents/sdk"
export TOOL_HOME="/Applications/DevEco-Studio.app/Contents/tools"

# PATH 中加入 ohpm / hvigor / node
export PATH="$TOOL_HOME/ohpm/bin:$PATH"
export PATH="$TOOL_HOME/hvigor/bin:$PATH"
export PATH="$TOOL_HOME/node/bin:$PATH"

# Flutter OHOS SDK (克隆后的 flutter_flutter 目录)
export PATH="$HOME/Developer/flutter_flutter/bin:$PATH"

# 国内 pub 镜像
export PUB_CACHE="$HOME/.pub-cache"
export PUB_HOSTED_URL="https://pub.flutter-io.cn"
export FLUTTER_STORAGE_BASE_URL="https://storage.flutter-io.cn"
```

配置后执行:

```bash
source ~/.zshrc
```

---

## 升级步骤

### 1. 克隆 Flutter OHOS SDK

```bash
# 选择一个目录存放 (不要放在项目内,避免污染仓库)
cd ~/Developer

# 从 atomgit 克隆 (国内推荐)
git clone -b oh-3.35.7-dev https://atomgit.com/openharmony-tpc/flutter_flutter.git

# 或从 gitcode 镜像克隆
# git clone -b oh-3.35.7-dev https://gitcode.com/openharmony-tpc/flutter_flutter.git

cd flutter_flutter
git checkout oh-3.35.7-dev
git pull --rebase
```

> **注意**: 分支名是 `oh-3.35.7-dev`,克隆后请确认 `git branch` 显示的分支正确。

### 2. 检查 Flutter 环境

```bash
# 确保使用的是 OHOS 版本而非官方 Flutter
which flutter
# 应输出: ~/Developer/flutter_flutter/bin/flutter

flutter --version
# 应输出类似:
# Flutter 3.35.8-ohos-0.0.3 • channel unknown • unknown source
# (注意: 显示 3.35.8 是正常现象,见上方说明)

flutter doctor -v
# 应看到 [✓] Flutter / [✓] HarmonyOS 等条目
```

### 3. 验证 DevEco Studio 版本

```bash
# 检查 DevEco Studio 是否为 6.0.2+
ls -la /Applications/DevEco-Studio.app/Contents/
# 或在 DevEco Studio 启动后: Help → About
```

### 4. 验证 Java 版本

```bash
java -version
# 应输出 openjdk version "17.x.x" 或更高
```

### 5. 更新项目依赖

```bash
cd /Users/netsong/Developer/i-home.life/flutter_app

# 拉取 pub 依赖
flutter pub get

# 若遇到证书问题,可临时关闭 SSL 校验
# ohpm install --strict_ssl false (在 ohos/ 目录下)
```

### 6. 构建 HAP

```bash
# 方式 A: 命令行 (推荐 DevEco Studio 命令行)
cd /Users/netsong/Developer/i-home.life/flutter_app
flutter build hap --release

# 方式 B: DevEco Studio IDE
# 1. 打开 DevEco Studio
# 2. File → Open → flutter_app/ohos/
# 3. 等待索引完成
# 4. Build → Build HAP(s)
```

### 7. 安装到 MatePad

```bash
# 查找构建产物
HAP=$(find flutter_app/build -name "*.hap" | head -1)

# 通过 hdc 安装
hdc install "$HAP"

# 或使用项目部署脚本
bash scripts/deploy-ohos.sh
```

---

## 配套工具链说明

### hvigor 配置

项目约定 hvigor 指向 DevEco Studio 本地安装路径,不在 `oh-package.json5` 的 devDependencies 中引用远程 `@ohos/hvigor`。

配置文件: `flutter_app/ohos/hvigor/hvigor-config.json5`

```json5
{
  "modelVersion": "5.0.0",
  "dependencies": {
    "@ohos/hvigor-ohos-plugin": "file:/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor-ohos-plugin",
    "@ohos/hvigor": "file:/Applications/DevEco-Studio.app/Contents/tools/hvigor/hvigor"
  }
}
```

### ohpm 安装

如遇 SSL 证书问题,使用:

```bash
cd flutter_app/ohos
ohpm install --strict_ssl false
```

---

## 本次升级关键变更点

| 文件 | 变更 |
|------|------|
| `flutter_app/pubspec.yaml` | `environment.sdk` 从 `^3.11.5` 改为 `^3.9.2`,添加鸿蒙版本元注释 |
| `flutter_app/ohos/build-profile.json5` | `targetSdkVersion` / `compatibleSdkVersion` 从 `5.0.0(12)` 升至 `6.0.0(14)` |
| `flutter_app/ohos/AppScope/app.json5` | `versionCode` 从 `1000000` 升至 `1001000`,添加 `minAPIVersion: 23` |
| `flutter_app/ohos/entry/oh-package.json5` | 添加 `modelVersion: "5.0.0"` |
| `flutter_app/ohos/entry/src/main/ets/pages/Index.ets` | 显示 3.35.7-ohos-0.0.3 版本信息 |

---

## 新特性列表 (3.35.7-ohos-0.0.3)

1. **SensitiveContentChannel 适配**: 支持敏感内容通道,保护用户隐私数据
2. **外接纹理可见区域监控**: 优化纹理渲染性能,仅在可见区域进行绘制
3. **点击状态栏自动回到顶部**: 符合原生交互习惯
4. **Impeller Vulkan 后端**: 支持 dirty region=0 时跳过渲染,显著降低功耗
5. **毕昇编译器替换并优化**: 提升编译效率与运行时性能
6. **软键盘修复**: 解决软键盘弹出/收起时的闪烁与错位
7. **PlatformView 输入框修复**: 修复混合栈下输入框焦点异常
8. **剪贴板修复**: 解决跨应用剪贴板读写失败

---

## 已知问题与规避方案

### 1. 版本号显示 3.35.8-ohos-0.0.3

**现象**: `flutter --version` 显示 `3.35.8-ohos-0.0.3` 而非 `3.35.7-ohos-0.0.3`。

**原因**: Flutter 内部版本解析规则,将 patch+1 后展示。

**规避**: 无需处理,这是正常现象,实际功能与 3.35.7-ohos-0.0.3 一致。

### 2. `flutter build hap` 命令行失败

**现象**: 直接执行 `flutter build hap` 报错。

**原因**: OHOS SDK 版本与 Dart SDK 差异较大时,命令行工具链可能无法正确解析。

**规避**: 使用 DevEco Studio 打开 `flutter_app/ohos/` 进行编译,或使用 `devecostudio --build` 命令。

### 3. ohpm install SSL 证书错误

**现象**: `ohpm install` 报 SSL 证书验证失败。

**规避**:

```bash
cd flutter_app/ohos
ohpm install --strict_ssl false
```

### 4. DevEco Studio 版本不匹配

**现象**: 构建时报 API 版本不兼容。

**规避**: 升级 DevEco Studio 至 6.0.2 Release 及以上,确保 `OpenHarmony API 23+` SDK 已下载。

---

## 验证清单

升级完成后,请逐项验证:

- [ ] `flutter --version` 输出包含 `ohos-0.0.3`
- [ ] `flutter doctor -v` 显示 HarmonyOS 工具链就绪
- [ ] `java -version` 显示 17 及以上
- [ ] DevEco Studio 版本 ≥ 6.0.2
- [ ] `flutter_app/pubspec.yaml` 中 `sdk: ^3.9.2`
- [ ] `flutter_app/ohos/build-profile.json5` 中 `targetSdkVersion: "6.0.0(14)"`
- [ ] `flutter pub get` 成功
- [ ] HAP 构建成功 (DevEco Studio 或命令行)
- [ ] HAP 安装到 MatePad 并能正常启动
- [ ] `bash scripts/check-ohos-env.sh` 输出全部通过

---

## 相关链接

- **官方仓库**: https://atomgit.com/openharmony-tpc/flutter_flutter
- **镜像仓库**: https://gitcode.com/openharmony-tpc/flutter_flutter
- **DevEco Studio 下载**: https://developer.huawei.com/consumer/cn/deveco-studio/
- **OpenHarmony 文档**: https://docs.openharmony.cn/
- **pub 国内镜像**: https://pub.flutter-io.cn

---

*本指南由 i-home.life 项目维护,最后更新于 2026-07-08*
