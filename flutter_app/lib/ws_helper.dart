/// 跨平台 WebSocket 帮助函数。
/// 通过条件导入在 Web (dart:html) 和原生 (dart:io) 之间切换。
library;

export 'ws_helper_stub.dart'
    if (dart.library.io) 'ws_helper_native.dart';
