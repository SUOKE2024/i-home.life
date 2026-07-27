/// 跨平台本地图片显示。
/// Web 从 image_picker 获得 blob URL，原生获得文件路径。
library;

export 'image_helper_stub.dart'
    if (dart.library.io) 'image_helper_native.dart';
