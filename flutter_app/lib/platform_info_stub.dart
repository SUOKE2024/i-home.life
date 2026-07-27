/// Web 平台信息 stub。
/// dart:io 在 Web 上不可用，提供 Web 替代值。
import 'package:flutter/foundation.dart' show kIsWeb;

class AppPlatform {
  static const bool isAndroid = false;
  static const bool isIOS = false;
  static bool get isWeb => kIsWeb;
  static const String operatingSystem = 'web';
  static const String operatingSystemVersion = 'web';
}
