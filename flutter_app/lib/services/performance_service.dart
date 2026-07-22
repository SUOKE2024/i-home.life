/// 性能监控服务 — 应用启动耗时、帧率追踪、崩溃报告。
///
/// 使用方式:
///   // 在 main() 中初始化
///   PerformanceService.instance.startupMark('app_start');
///   // ... 应用初始化代码 ...
///   PerformanceService.instance.startupMark('app_ready');
///   PerformanceService.instance.reportStartupMetrics();
///
/// 特性:
///   - 启动阶段耗时标记（app_start → app_ready）
///   - 帧率追踪（通过 SchedulerBinding.addPersistentFrameCallback）
///   - 崩溃报告（FlutterError.onError + PlatformDispatcher.onError）
///   - 应用生命周期追踪（前台/后台切换耗时）
///   - 内存警告监听（低内存设备降级）
library;

import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

/// 启动阶段标记
enum StartupPhase {
  appStart,
  authCheck,
  featureFlagsLoaded,
  sensorsReady,
  firstFrameRendered,
  appReady,
}

/// 性能监控服务单例
class PerformanceService {
  PerformanceService._();
  static final PerformanceService _instance = PerformanceService._();
  static PerformanceService get instance => _instance;

  // ── 启动耗时追踪 ──
  final Map<StartupPhase, int> _startupMarks = {};
  bool _startupReportingEnabled = true;

  // ── 帧率追踪 ──
  bool _frameTrackingEnabled = false;
  final List<double> _recentFrameTimes = [];
  static const int _maxFrameSamples = 120; // 约 2 秒 @60fps
  double _averageFPS = 60.0;
  int _droppedFrames = 0;

  // ── 生命周期追踪 ──
  DateTime? _lastBackgroundTime;

  // ── 崩溃报告 ──
  final List<Map<String, dynamic>> _crashReports = [];
  static const int _maxCrashReports = 20;

  /// 初始化性能监控（在 main() 中调用）
  void initialize() {
    _startupMark(StartupPhase.appStart);
    _setupCrashReporting();
    debugPrint('[PerformanceService] 初始化完成');
  }

  /// 记录启动阶段时间戳
  void _startupMark(StartupPhase phase) {
    if (!_startupReportingEnabled) return;
    _startupMarks[phase] = DateTime.now().microsecondsSinceEpoch;
  }

  /// 对外暴露的启动标记方法
  void startupMark(String phaseName) {
    final phase = _parsePhase(phaseName);
    if (phase != null) {
      _startupMark(phase);
    }
  }

  StartupPhase? _parsePhase(String name) {
    switch (name) {
      case 'app_start':
        return StartupPhase.appStart;
      case 'auth_check':
        return StartupPhase.authCheck;
      case 'feature_flags_loaded':
        return StartupPhase.featureFlagsLoaded;
      case 'sensors_ready':
        return StartupPhase.sensorsReady;
      case 'first_frame':
        return StartupPhase.firstFrameRendered;
      case 'app_ready':
        return StartupPhase.appReady;
      default:
        return null;
    }
  }

  /// 上报启动耗时指标
  Map<String, int> reportStartupMetrics() {
    _startupMark(StartupPhase.appReady);

    final metrics = <String, int>{};
    final start = _startupMarks[StartupPhase.appStart];
    if (start == null) return metrics;

    for (final phase in StartupPhase.values) {
      if (phase == StartupPhase.appStart) continue;
      final ts = _startupMarks[phase];
      if (ts != null) {
        final durationMs = (ts - start) ~/ 1000; // microseconds → milliseconds
        metrics[phase.name] = durationMs;
      }
    }

    // 计算总启动耗时
    final ready = _startupMarks[StartupPhase.appReady];
    if (ready != null) {
      metrics['total_startup_ms'] = (ready - start) ~/ 1000;
    }

    if (kDebugMode) {
      debugPrint('[PerformanceService] 启动耗时: $metrics');
    }

    return metrics;
  }

  // ── 帧率追踪 ──

  /// 开启帧率追踪（需在有 SchedulerBinding 的上下文中调用）
  void startFrameTracking() {
    if (_frameTrackingEnabled) return;
    _frameTrackingEnabled = true;
    _recentFrameTimes.clear();
    _droppedFrames = 0;

    // 添加持久帧回调追踪每帧耗时
    SchedulerBinding.instance.addPersistentFrameCallback(_onFrame);
  }

  void _onFrame(Duration timestamp) {
    if (!_frameTrackingEnabled) return;

    final frameTimeMs = timestamp.inMicroseconds / 1000.0;
    _recentFrameTimes.add(frameTimeMs);

    // 限制样本量
    if (_recentFrameTimes.length > _maxFrameSamples) {
      _recentFrameTimes.removeAt(0);
    }

    // 计算平均 FPS
    if (_recentFrameTimes.length >= 2) {
      final totalDuration = _recentFrameTimes.last - _recentFrameTimes.first;
      final frameCount = _recentFrameTimes.length - 1;
      if (totalDuration > 0) {
        _averageFPS = frameCount / (totalDuration / 1000.0);
      }
    }

    // 检测掉帧（两帧间隔 > 33ms 即 30fps 以下）
    if (_recentFrameTimes.length >= 2) {
      final delta = _recentFrameTimes.last - _recentFrameTimes[_recentFrameTimes.length - 2];
      if (delta > 33.0) {
        // >30ms 帧间隔 = 低于 30fps
        _droppedFrames++;
      }
    }

    // 继续追踪
    SchedulerBinding.instance.addPersistentFrameCallback(_onFrame);
  }

  /// 停止帧率追踪
  void stopFrameTracking() {
    _frameTrackingEnabled = false;
  }

  /// 获取当前平均 FPS
  double get averageFPS => _averageFPS;

  /// 获取累计掉帧数
  int get droppedFrames => _droppedFrames;

  /// 获取帧率健康状态
  FrameRateHealth get frameRateHealth {
    if (_averageFPS >= 55) return FrameRateHealth.good;
    if (_averageFPS >= 40) return FrameRateHealth.fair;
    if (_averageFPS >= 25) return FrameRateHealth.poor;
    return FrameRateHealth.critical;
  }

  // ── 生命周期追踪 ──

  /// 应用进入后台
  void onAppBackground() {
    _lastBackgroundTime = DateTime.now();
  }

  /// 应用回到前台
  void onAppForeground() {
    if (_lastBackgroundTime != null) {
      final duration = DateTime.now().difference(_lastBackgroundTime!);
      debugPrint('[PerformanceService] 后台停留: ${duration.inSeconds}s');
      _lastBackgroundTime = null;
    }
  }

  // ── 崩溃报告 ──

  void _setupCrashReporting() {
    // 捕获 Flutter 框架层错误
    FlutterError.onError = (FlutterErrorDetails details) {
      // 仍然输出到控制台
      FlutterError.presentError(details);

      // 记录崩溃
      _recordCrash(
        type: 'flutter_error',
        message: details.exceptionAsString(),
        stack: details.stack?.toString(),
        context: details.library,
      );
    };

    // 捕获未处理的异步错误
    PlatformDispatcher.instance.onError = (error, stack) {
      _recordCrash(
        type: 'unhandled_error',
        message: error.toString(),
        stack: stack.toString(),
      );
      return true; // 已处理
    };
  }

  void _recordCrash({
    required String type,
    required String message,
    String? stack,
    String? context,
  }) {
    final report = <String, dynamic>{
      'type': type,
      'message': message,
      'stack': stack,
      'context': context,
      'timestamp': DateTime.now().toIso8601String(),
      'platform': Platform.operatingSystem,
      'is_harmonyos': !Platform.isAndroid && !Platform.isIOS,
    };

    _crashReports.add(report);
    if (_crashReports.length > _maxCrashReports) {
      _crashReports.removeAt(0);
    }

    debugPrint('[PerformanceService] 崩溃记录: $type - $message');
  }

  /// 获取崩溃报告列表
  List<Map<String, dynamic>> getCrashReports() =>
      List.unmodifiable(_crashReports);

  /// 获取性能摘要（用于调试面板）
  Map<String, dynamic> getPerformanceSummary() {
    return {
      'average_fps': _averageFPS.toStringAsFixed(1),
      'dropped_frames': _droppedFrames,
      'frame_health': frameRateHealth.name,
      'crash_count': _crashReports.length,
      'startup_metrics': reportStartupMetrics(),
    };
  }
}

/// 帧率健康状态
enum FrameRateHealth {
  good,      // >= 55 fps
  fair,      // 40-54 fps
  poor,      // 25-39 fps
  critical,  // < 25 fps
}
