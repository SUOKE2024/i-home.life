# ihome_app · 索克家居 Flutter 客户端

i-home.life 平台的跨端移动客户端，基于 Flutter 实现，覆盖 iOS / Android / HarmonyOS 三端。

## 技术栈

| 项 | 版本 / 说明 |
|---|---|
| Flutter-OH | 3.35.7-ohos-0.0.3 (上游 Flutter 3.35.7) |
| Dart | ^3.9.2 |
| 状态管理 | provider ^6.1.2 |
| 网络 | http ^1.2.0 |
| 持久化 | shared_preferences ^2.3.0 / path_provider ^2.1.4 |
| 鸿蒙配套 | DevEco Studio 6.0.2+ / OpenHarmony API 23+ / Java 17 |

> 鸿蒙构建请参阅 [OHOS_UPGRADE_GUIDE.md](./OHOS_UPGRADE_GUIDE.md) 与 `scripts/check-ohos-env.sh`。

## 目录结构

```
flutter_app/
├── lib/
│   ├── main.dart              # 应用入口 (MaterialApp.dark)
│   ├── config.dart            # API 端点 / 超时配置
│   ├── pages/                 # 业务页面 (15+)
│   │   ├── login_page.dart
│   │   ├── home_page.dart
│   │   ├── dashboard_page.dart
│   │   ├── projects_page.dart
│   │   ├── project_detail_page.dart
│   │   ├── ar_scan_page.dart        # F1 AR 空间测量
│   │   ├── cad_page.dart            # 户型 CAD
│   │   ├── budget_page.dart         # F15 预算管理
│   │   ├── materials_page.dart      # 材料库
│   │   ├── construction_page.dart   # 施工管理
│   │   ├── settlement_page.dart     # 结算
│   │   ├── ai_chat_page.dart        # AI 对话
│   │   ├── design_deepening_page.dart    # 设计深化 (F18/F21/F23/F29/F30)
│   │   ├── procurement_enhanced_page.dart # 采购增强 (F33/F34)
│   │   ├── cad_element.dart          # CAD 画布元素
│   │   └── stylus_adapter.dart       # 触控笔适配
│   └── services/
│       └── api.dart           # HTTP 客户端封装 (60+ 方法)
├── android/                   # Android 原生壳
├── ios/                       # iOS 原生壳 (Xcode 工程)
├── ohos/                      # HarmonyOS 原生壳 (DevEco 工程)
├── assets/images/             # 品牌资源 (由 scripts/sync-flutter-assets.sh 同步)
├── test/widget_test.dart
├── pubspec.yaml
└── analysis_options.yaml
```

## 环境准备

```bash
# 1. Flutter-OH SDK (鸿蒙分支)
#    仓库: https://atomgit.com/openharmony-tpc/flutter_flutter
#    分支: oh-3.35.7-dev

# 2. 依赖
cd flutter_app
flutter pub get

# 3. 鸿蒙环境自检 (可选)
bash ../scripts/check-ohos-env.sh
```

## 运行

```bash
# 后端默认监听 http://10.0.2.2:8000 (Android 模拟器映射到 host 127.0.0.1:8000)
# 真机调试请修改 lib/config.dart 的 apiBaseUrl

flutter run                           # 默认设备
flutter run -d <device_id>            # 指定设备
flutter run -d ohos                   # HarmonyOS 设备 (需 DevEco Studio)
```

## 资源同步

品牌 LOGO 套件主源在仓库根 `assets/images/icons/desktop/`，本目录下为同步副本：

```bash
bash ../scripts/sync-flutter-assets.sh
```

## 静态分析

```bash
dart analyze
```

## 后端 API

客户端通过 `/api` 前缀访问 FastAPI 后端，接口文档见：
- Swagger UI: `http://<host>:8081/api/docs`
- OpenAPI JSON: `http://<host>:8081/api/openapi.json`

## 相关文档

- 项目总览: [`../README.md`](../README.md)
- PRD: [`../web/house-design-platform-prd.html`](../web/house-design-platform-prd.html)
- 鸿蒙升级指南: [`OHOS_UPGRADE_GUIDE.md`](OHOS_UPGRADE_GUIDE.md)
- 部署脚本: [`../scripts/`](../scripts/)
