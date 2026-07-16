/// 全局应用配置。
///
/// [apiBaseUrl] 与 [debugMode] 均支持构建期注入（`--dart-define`），
/// 便于在 CI/CD 中区分环境，避免把开发地址/调试开关硬编码进产物。
class AppConfig {
  /// API 基础地址。
  ///
  /// 生产部署策略（默认空串 → 使用相对路径）：
  /// 1) Web 端与 API 同源托管：前端使用相对路径（如 `/projects`）发起请求，
  ///    由反向代理（Nginx / API 网关）将请求转发到后端，避免跨域与硬编码域名。
  /// 2) 移动端（iOS/Android）或前后端分离部署时，必须在构建期覆盖：
  ///    `flutter build --dart-define=API_BASE_URL=https://api.example.com/api`
  /// 注意：留空时仅 Web 端可正常工作（相对路径基于页面 origin 解析）；
  ///       原生端务必通过 dart-define 注入完整绝对地址。
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8766/api',
  );

  static const String appName = 'i-home.life';
  static const String appVersion = '0.1.0';
  static const Duration requestTimeout = Duration(seconds: 15);

  /// 调试模式开关。
  /// - false（默认，生产就绪）：启用完整 TLS 证书校验等安全策略。
  /// - true：仅用于本地开发，会放宽安全策略（如跳过 SSL 证书校验）。
  ///   本地开发时通过 `--dart-define=DEBUG_MODE=true` 开启。
  /// ⚠️ 生产构建严禁设置 DEBUG_MODE=true。
  static const bool debugMode = bool.fromEnvironment(
    'DEBUG_MODE',
    defaultValue: false,
  );
}
