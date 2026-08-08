import 'package:geolocator/geolocator.dart';

/// LBS 定位服务 — 为 Agent 空间感知提供客户端 GPS 坐标。
///
/// 闭环链路：客户端 GPS → Agent 端点 location 参数（"lng,lat"）→
/// 后端逆地理编码城市落库长期记忆 + 周边真实 POI 注入（高德）。
///
/// 诚实降级约束（对齐 CLAUDE.md）：
/// - 权限拒绝 / 定位失败 / 超时（8s）时返回 null，不伪造坐标；
///   Agent 对话正常进行，仅不注入 LBS 上下文（后端同样诚实降级为空）。
/// - 坐标只做粗精度（LBS 周边 3km 检索足够），成功一次后缓存复用，
///   避免每次对话都触发定位（耗电/延迟）。
/// - 鸿蒙等不支持平台通过 try-catch 优雅降级为 null。
class LocationService {
  LocationService._();

  static final LocationService instance = LocationService._();

  /// 缓存坐标（"lng,lat"），null 表示未获取到
  String? _location;

  /// 是否已尝试过定位（失败后不再重复请求，避免每次对话都弹权限框）
  bool _requested = false;

  /// 获取当前 GPS 坐标（"lng,lat"），失败/拒绝/超时返回 null。
  ///
  /// 首次调用发起定位并缓存；成功后再取直接返回缓存。
  Future<String?> getLocation() async {
    if (_location != null) return _location;
    if (_requested) return null;
    _requested = true;
    try {
      final permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        final requested = await Geolocator.requestPermission();
        if (requested == LocationPermission.denied ||
            requested == LocationPermission.deniedForever) {
          return null; // 诚实降级：用户拒绝授权，不传坐标
        }
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.low, // LBS 周边检索只需粗精度
          timeLimit: Duration(seconds: 8), // 超时降级，不阻塞对话
        ),
      );
      _location =
          '${pos.longitude.toStringAsFixed(6)},${pos.latitude.toStringAsFixed(6)}';
    } catch (_) {
      _location = null; // 定位失败/平台不支持（如鸿蒙）→ 诚实降级
    }
    return _location;
  }

  /// 同步读取缓存坐标（null = 未获取到）。发送消息时用此接口，不阻塞对话。
  String? getCached() => _location;

  /// 预取定位（页面 initState 调用）：异步获取并缓存，发送时直接读缓存。
  Future<void> prefetch() => getLocation();
}
