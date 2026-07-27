/// 原生平台信息（iOS / Android / HarmonyOS）。
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;

class AppPlatform {
  static bool get isAndroid => !kIsWeb && Platform.isAndroid;
  static bool get isIOS => !kIsWeb && Platform.isIOS;
  static bool get isWeb => kIsWeb;
  static String get operatingSystem => Platform.operatingSystem;
  static String get operatingSystemVersion => Platform.operatingSystemVersion;
}
