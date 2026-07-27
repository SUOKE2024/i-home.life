/// 跨平台信息抽象层。
/// 通过条件导入在 Web 和原生平台之间切换，避免直接导入 dart:io。
library;

export 'platform_info_stub.dart'
    if (dart.library.io) 'platform_info_native.dart';
