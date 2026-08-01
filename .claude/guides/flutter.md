# Flutter 多端开发规范（flutter.md）

> Flutter 跨三端：iOS / Android / HarmonyOS。所有事实基于当前代码。
> **核心约束：不使用 Dart 3.10+ 语法，保证鸿蒙端可编译**（pubspec.yaml:10）。

## 技术栈

- Flutter SDK：Android/iOS 用系统 Flutter 3.41.7，鸿蒙用 Flutter-OH 3.35.7-ohos-0.0.3
- Dart SDK：`^3.9.2`（[pubspec.yaml:12](file:///Users/netsong/Developer/i-home.life/flutter_app/pubspec.yaml)）
- 状态管理：**Provider**（`provider: ^6.1.2`）
- 网络：**http**（`http: ^1.2.0`，非 Dio）
- 持久化：**shared_preferences**（token 存储）
- 路由：Navigator（非 go_router）
- 版本：`version: 1.3.0+27`（pubspec.yaml:4，+27 是 build 号）

## 目录结构

```
flutter_app/lib/
├── config.dart              # AppConfig（版本/API base/debug 模式）
├── main.dart                # 入口，Provider 注入
├── pages/                   # 45 个页面（home/login/settings/...）
├── services/                # 服务层（api/feature_flags/notification/...）
├── models/                  # 数据模型
├── widgets/                 # 复用组件（voice_overlay/...）
├── theme/suoke_theme.dart   # 索克主题
├── http_overrides_*.dart    # HTTP 平台分文件（native/stub）
├── image_helper_*.dart      # 图片处理平台分文件
├── ws_helper_*.dart         # WebSocket 平台分文件
└── platform_info_*.dart     # 平台信息平台分文件
```

## 平台分文件模式（关键约定）

鸿蒙端不支持部分原生插件，用条件导入降级。命名约定 `xxx_native.dart` / `xxx_stub.dart`：

```dart
// 调用方（main.dart:6）
import 'http_overrides_stub.dart'
    if (dart.library.io) 'http_overrides_native.dart';
```

**新增原生能力时必须同时写 native + stub 两份**，stub 里做优雅降级（log + 跳过），禁止直接调原生 API 不处理鸿蒙情况。

不支持的插件（pubspec 注释标注）：`local_auth` / `flutter_local_notifications` / `sensors_plus` / `geolocator` —— 鸿蒙端自动降级关闭。

## 配置与构建期注入

[lib/config.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/config.dart) `AppConfig`：

```dart
static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://...');
static const String appVersion = '1.3.0';
static const bool debugMode = bool.fromEnvironment('DEBUG_MODE');
```

- 移动端构建必须注入 API_BASE_URL：`flutter build --dart-define=API_BASE_URL=https://api.i-home.life/api`
- Web 端可留空走相对路径（同源托管 + Nginx 反代）
- **生产构建严禁 `DEBUG_MODE=true`**（会跳过 TLS 校验）

## API 客户端

[lib/services/api.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/services/api.dart) `ApiClient` 单例：

- **Result 模式**：所有方法返回 `Result<T>` 而非抛异常，调用方用 `isSuccess` 判断
- Token 存储：`SharedPreferences` key `paseto_token`（与 Web 控制台共享）
- 401 触发 `onUnauthorized` 回调（跳登录页）
- 重试：`_maxRetries=3`，指数退避 `_retryBaseDelay=500ms`
- 请求头：`Authorization: Bearer {token}`
- 超时：`AppConfig.requestTimeout = 15s`

```dart
// 用法
final result = await ApiClient().get('/projects');
if (result.isSuccess) {
  final projects = result.data as List<Project>;
}
```

**禁止**直接用 `http.get`，必须走 `ApiClient` 单例（统一 token/重试/超时）。

## 入口与初始化

[lib/main.dart](file:///Users/netsong/Developer/i-home.life/flutter_app/lib/main.dart) `main()`：

1. `WidgetsFlutterBinding.ensureInitialized()`
2. `PerformanceService.instance.initialize()` —— 性能监控
3. `setupHttpOverrides(debugMode)` —— HTTP 平台配置
4. `NotificationService().initialize()` —— 通知（失败不阻塞启动，鸿蒙自动跳过）
5. `FeatureFlagsService().initialize()` —— feature flag 预加载（异步）
6. `runApp(IHomeApp())`

**所有初始化失败不得阻塞应用启动**，用 `.catchError` 兜底。

## 鸿蒙 HarmonyOS 集成

[flutter_app/ohos/entry/src/main/ets/entryability/EntryAbility.ets](file:///Users/netsong/Developer/i-home.life/flutter_app/ohos/entry/src/main/ets/entryability/EntryAbility.ets)：

```typescript
export default class EntryAbility extends FlutterAbility {
  configureFlutterEngine(flutterEngine: FlutterEngine): void {
    super.configureFlutterEngine(flutterEngine);
    GeneratedPluginRegistrant.registerWith(flutterEngine);
  }
}
```

- 继承 `FlutterAbility`（对标官方 flutter_flutter 模板 oh-3.35.7-dev）
- `Index.ets` 用 `FlutterPage` 全屏承载业务 UI
- `GeneratedPluginRegistrant.ets` 是占位，`flutter build hap` 时自动重生成
- 首次构建流程见 `scripts/ohos-ready.sh`
- DevEco Studio 6.0.2 / OpenHarmony API 23+

**禁止**手动编辑 `GeneratedPluginRegistrant.ets`（会被构建覆盖）。

## 版本号同步

Flutter 版本号在 3 处（详见 `.claude/templates/version-bump.md`）：

1. `flutter_app/pubspec.yaml` → `version: X.Y.Z+NN`
2. `flutter_app/lib/config.dart` → `appVersion = 'X.Y.Z'`（line 30）
3. `flutter_app/lib/pages/settings_page.dart` → 硬编码版本字符串（line 272）

**三处必须一致**，发版时同步改。

## 测试

- 单元/组件测试：`flutter_app/test/`（`widget_test.dart` + `pages/` + `services/` + `widgets/`）
- 集成测试：`flutter_app/integration_test/smoke_test.dart`（真机/模拟器冒烟）
- 框架：`flutter_test` + `integration_test` SDK
- lint：`flutter_lints: ^6.0.0`

```bash
flutter test                          # 全量单元/组件测试
flutter test integration_test/smoke_test.dart  # 集成冒烟
flutter analyze                       # 静态分析（0 error）
```

## 禁止事项

- ❌ 使用 Dart 3.10+ 语法（鸿蒙端 Flutter-OH 3.35.7 不支持）
- ❌ 引入 Dio（项目统一用 http）
- ❌ 引入 go_router（项目用 Navigator）
- ❌ 引入 Riverpod/Bloc/GetX（项目统一 Provider）
- ❌ 直接调原生 API 不写 stub 降级
- ❌ 手动编辑 `GeneratedPluginRegistrant.ets`
- ❌ 提交鸿蒙签名私钥（`.p12`/`.jks`，v1.2.6 教训：曾泄露到 git 历史）
- ❌ 构建产物 `flutter_app/build/` 提交到 git

## 跨端登录态共享

PASETO token 存储约定（三端一致）：

| 端 | 存储 | key |
|----|------|-----|
| Flutter | SharedPreferences | `paseto_token` |
| Web 控制台 | localStorage | `paseto_token` |
| 旧静态页 | localStorage | `paseto_token` |

Web 端同源时登录态自动共享（同 localStorage）。移动端独立存储。
