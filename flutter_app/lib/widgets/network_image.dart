/// 跨平台网络图片组件。
///
/// - iOS/Android：cached_network_image（磁盘缓存，离线友好）
/// - Web / OHOS：Image.network 降级（cached_network_image 未官方支持 OHOS，
///   见 pubspec.yaml 注释；Web 端无磁盘缓存但功能等价）
///
/// API 与 CachedNetworkImage 对齐（imageUrl/fit/width/height/placeholder/errorWidget），
/// 调用方替换 `CachedNetworkImage(` → `SuokeNetworkImage(` 即可。
library;

export 'network_image_stub.dart'
    if (dart.library.io) 'network_image_native.dart';
