import 'api.dart';

/// 功能开关服务（单例）。
///
/// 应用启动时从后端拉取功能开关配置并缓存在内存中，
/// 通过类型安全的 getter 访问各开关状态，默认返回 `false`（安全兜底）。
class FeatureFlagsService {
  static final FeatureFlagsService _instance = FeatureFlagsService._();
  factory FeatureFlagsService() => _instance;
  FeatureFlagsService._();

  Map<String, bool> _flags = {};

  /// 是否已完成首次加载（避免未初始化时的误判）。
  bool _initialized = false;
  bool get isInitialized => _initialized;

  // ── 功能开关 getter ──

  bool get isFilamentEnabled => _flags['filament'] ?? false;
  bool get isOpenCascadeEnabled => _flags['open_cascade'] ?? false;
  bool get isMCPEnabled => _flags['mcp'] ?? false;
  bool get isAIRenderEnabled => _flags['ai_render'] ?? false;
  bool get isVoiceEmotionRoutingEnabled =>
      _flags['voice_emotion_routing'] ?? false;

  /// 通过 key 直接查询（用于尚未定义专用 getter 的开关）。
  bool isEnabled(String key) => _flags[key] ?? false;

  // ── 加载 ──

  /// 从后端拉取功能开关并缓存。调用失败时保持现有缓存不变。
  Future<void> initialize() async {
    await _fetch();
  }

  /// 强制重新拉取功能开关。
  Future<void> reload() async {
    await _fetch();
  }

  // ── 内部 ──

  Future<void> _fetch() async {
    final result = await ApiClient().getFeatureFlags();
    if (!result.isSuccess || result.data == null) return;
    final data = result.data;
    if (data is Map<String, dynamic>) {
      final parsed = <String, bool>{};
      for (final entry in data.entries) {
        parsed[entry.key] = entry.value == true;
      }
      _flags = parsed;
    }
    _initialized = true;
  }
}
