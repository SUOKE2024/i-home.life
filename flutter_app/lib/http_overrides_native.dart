import 'dart:io';

/// 仅用于本地开发：跳过 TLS 证书校验，便于对接使用自签名证书的后端。
/// 生产环境必须启用完整 SSL 校验。
class _DevelopmentHttpOverrides extends HttpOverrides {
  @override
  HttpClient createHttpClient(SecurityContext? context) {
    return super.createHttpClient(context)
      ..badCertificateCallback =
          (X509Certificate cert, String host, int port) => true;
  }
}

void setupHttpOverrides(bool debugMode) {
  if (debugMode) {
    HttpOverrides.global = _DevelopmentHttpOverrides();
  }
}
