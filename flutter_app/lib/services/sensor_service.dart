/// 索克家居 · 传感器数据采集服务
///
/// 功能：
/// - 加速度计 / 陀螺仪 / 磁力计 数据采集（sensors_plus）
/// - GPS 定位数据采集（geolocator）
/// - 统一快照输出，供 AR 测量、场景自动化地理触发等模块消费
/// - 鸿蒙平台优雅降级（PlatformException → available=false）
library;

import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';
import 'package:sensors_plus/sensors_plus.dart';

/// 传感器数据采集服务（单例）
///
/// 设计原则：
/// - 所有原生插件调用均包裹 try-catch，失败仅 debugPrint，不抛异常
/// - 未知平台（如 HarmonyOS/ohos）优雅降级，所有 available=false
/// - 单例模式，全局共享传感器流订阅
/// - 默认采样频率 60Hz（≈16.67ms 周期）
class SensorService {
  static final SensorService _instance = SensorService._();
  factory SensorService() => _instance;
  SensorService._();

  /// 60Hz 采样周期（≈16667 微秒）
  static const Duration kSampleInterval = Duration(microseconds: 16667);

  // ── 静态能力字段（try-catch 检测，鸿蒙等平台默认 false）──
  static bool accelerometerAvailable = false;
  static bool gyroscopeAvailable = false;
  static bool magnetometerAvailable = false;
  static bool gpsAvailable = false;

  // ── 当前数据缓存 ──
  AccelerometerEvent? _lastAccel;
  GyroscopeEvent? _lastGyro;
  MagnetometerEvent? _lastMag;
  Position? _lastPosition;

  // ── 流订阅 ──
  StreamSubscription<AccelerometerEvent>? _accelSub;
  StreamSubscription<GyroscopeEvent>? _gyroSub;
  StreamSubscription<MagnetometerEvent>? _magSub;

  bool _running = false;
  bool _capabilityDetected = false;

  /// 启动所有传感器监听
  ///
  /// 内部会先进行能力探测；不支持的平台/传感器会被跳过。
  Future<void> start() async {
    if (_running) return;
    _running = true;

    await _detectCapabilities();

    if (accelerometerAvailable) {
      try {
        _accelSub =
            accelerometerEventStream(samplingPeriod: kSampleInterval).listen(
          (event) => _lastAccel = event,
          onError: (Object e) {
            debugPrint('[SensorService] 加速度计流错误: $e');
            accelerometerAvailable = false;
          },
        );
      } catch (e, st) {
        debugPrint('[SensorService] 加速度计监听启动失败: $e\n$st');
        accelerometerAvailable = false;
      }
    }

    if (gyroscopeAvailable) {
      try {
        _gyroSub =
            gyroscopeEventStream(samplingPeriod: kSampleInterval).listen(
          (event) => _lastGyro = event,
          onError: (Object e) {
            debugPrint('[SensorService] 陀螺仪流错误: $e');
            gyroscopeAvailable = false;
          },
        );
      } catch (e, st) {
        debugPrint('[SensorService] 陀螺仪监听启动失败: $e\n$st');
        gyroscopeAvailable = false;
      }
    }

    if (magnetometerAvailable) {
      try {
        _magSub =
            magnetometerEventStream(samplingPeriod: kSampleInterval).listen(
          (event) => _lastMag = event,
          onError: (Object e) {
            debugPrint('[SensorService] 磁力计流错误: $e');
            magnetometerAvailable = false;
          },
        );
      } catch (e, st) {
        debugPrint('[SensorService] 磁力计监听启动失败: $e\n$st');
        magnetometerAvailable = false;
      }
    }
  }

  /// 停止所有传感器监听（保留能力标志，便于后续 start 复用）
  void stop() {
    _accelSub?.cancel();
    _gyroSub?.cancel();
    _magSub?.cancel();
    _accelSub = null;
    _gyroSub = null;
    _magSub = null;
    _running = false;
  }

  /// 释放资源（等同于 stop，便于在 dispose 生命周期调用）
  void dispose() {
    stop();
  }

  /// 获取当前位置（GPS）
  ///
  /// 返回 null 表示获取失败（无权限 / 平台不支持 / 超时）。
  /// 成功时返回的 Map 结构与 [getSnapshot] 中的 'gps' 字段一致。
  Future<Map<String, dynamic>?> getCurrentLocation() async {
    if (!gpsAvailable) {
      // 用户可能刚授权，重新探测一次
      await _detectGpsCapability();
      if (!gpsAvailable) return null;
    }

    try {
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        debugPrint('[SensorService] 定位服务未开启');
        return null;
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        debugPrint('[SensorService] 定位权限被拒绝');
        return null;
      }

      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 10),
        ),
      );
      _lastPosition = position;
      return _positionToMap(position);
    } on PlatformException catch (e) {
      debugPrint('[SensorService] 获取定位 PlatformException: ${e.code} ${e.message}');
      gpsAvailable = false;
      return null;
    } catch (e, st) {
      debugPrint('[SensorService] 获取定位失败: $e\n$st');
      return null;
    }
  }

  /// 返回各传感器可用性
  Map<String, bool> getCapabilities() {
    return {
      'accelerometer': accelerometerAvailable,
      'gyroscope': gyroscopeAvailable,
      'magnetometer': magnetometerAvailable,
      'gps': gpsAvailable,
    };
  }

  /// 返回当前所有传感器数据快照
  ///
  /// 结构：
  /// ```
  /// {
  ///   'accelerometer': {'x','y','z','available'},
  ///   'gyroscope':     {'x','y','z','available'},
  ///   'magnetometer':  {'x','y','z','heading_deg','available'},
  ///   'gps':           {'latitude','longitude','accuracy','altitude?','available'},
  ///   'timestamp':     ISO8601 字符串,
  /// }
  /// ```
  Map<String, dynamic> getSnapshot() {
    return {
      'accelerometer': {
        'x': _lastAccel?.x ?? 0.0,
        'y': _lastAccel?.y ?? 0.0,
        'z': _lastAccel?.z ?? 0.0,
        'available': accelerometerAvailable,
      },
      'gyroscope': {
        'x': _lastGyro?.x ?? 0.0,
        'y': _lastGyro?.y ?? 0.0,
        'z': _lastGyro?.z ?? 0.0,
        'available': gyroscopeAvailable,
      },
      'magnetometer': {
        'x': _lastMag?.x ?? 0.0,
        'y': _lastMag?.y ?? 0.0,
        'z': _lastMag?.z ?? 0.0,
        'heading_deg': _computeHeading(_lastMag),
        'available': magnetometerAvailable,
      },
      'gps': _lastPosition != null
          ? _positionToMap(_lastPosition!)
          : {
              'latitude': 0.0,
              'longitude': 0.0,
              'accuracy': 0.0,
              'altitude': null,
              'available': gpsAvailable,
            },
      'timestamp': DateTime.now().toIso8601String(),
    };
  }

  // ────────────────────────── 内部方法 ──────────────────────────

  /// 一次性探测所有传感器能力
  ///
  /// 鸿蒙等未知平台调用 sensors_plus / geolocator 会抛 PlatformException，
  /// 此处统一捕获并将对应 available 置为 false，确保应用不崩溃。
  Future<void> _detectCapabilities() async {
    if (_capabilityDetected) return;
    _capabilityDetected = true;

    // 仅 Android/iOS 支持传感器/定位插件，其他平台（HarmonyOS/ohos/Web）直接降级
    if (!Platform.isAndroid && !Platform.isIOS) {
      debugPrint('[SensorService] 当前平台不支持传感器/定位插件，全部降级 '
          '(platform=${Platform.operatingSystem})');
      accelerometerAvailable = false;
      gyroscopeAvailable = false;
      magnetometerAvailable = false;
      gpsAvailable = false;
      return;
    }

    await _detectSensorCapabilities();
    await _detectGpsCapability();
  }

  /// 探测加速度计 / 陀螺仪 / 磁力计可用性
  Future<void> _detectSensorCapabilities() async {
    // 加速度计
    try {
      final sub =
          accelerometerEventStream(samplingPeriod: kSampleInterval).listen((_) {});
      await Future<void>.delayed(const Duration(milliseconds: 300));
      await sub.cancel();
      accelerometerAvailable = true;
    } catch (e) {
      accelerometerAvailable = false;
      debugPrint('[SensorService] 加速度计不可用: $e');
    }

    // 陀螺仪
    try {
      final sub =
          gyroscopeEventStream(samplingPeriod: kSampleInterval).listen((_) {});
      await Future<void>.delayed(const Duration(milliseconds: 300));
      await sub.cancel();
      gyroscopeAvailable = true;
    } catch (e) {
      gyroscopeAvailable = false;
      debugPrint('[SensorService] 陀螺仪不可用: $e');
    }

    // 磁力计
    try {
      final sub =
          magnetometerEventStream(samplingPeriod: kSampleInterval).listen((_) {});
      await Future<void>.delayed(const Duration(milliseconds: 300));
      await sub.cancel();
      magnetometerAvailable = true;
    } catch (e) {
      magnetometerAvailable = false;
      debugPrint('[SensorService] 磁力计不可用: $e');
    }
  }

  /// 探测 GPS 可用性（仅检查定位服务是否开启，不强制请求权限）
  Future<void> _detectGpsCapability() async {
    try {
      final enabled = await Geolocator.isLocationServiceEnabled();
      gpsAvailable = enabled;
    } on PlatformException catch (e) {
      gpsAvailable = false;
      debugPrint('[SensorService] GPS 探测 PlatformException: ${e.code} ${e.message}');
    } catch (e) {
      gpsAvailable = false;
      debugPrint('[SensorService] GPS 不可用: $e');
    }
  }

  /// 由磁力计数据估算航向角（度，[0, 360)）
  ///
  /// 基础公式：heading = atan2(y, x) → 弧度转角度 → 归一化到 [0, 360)。
  /// 未做倾角补偿，仅作为简易方位参考；精确航向需结合加速度计做倾斜补偿。
  double _computeHeading(MagnetometerEvent? mag) {
    if (mag == null) return 0.0;
    double heading = math.atan2(mag.y, mag.x) * (180.0 / math.pi);
    if (heading < 0) heading += 360.0;
    return heading;
  }

  /// 将 geolocator Position 转为统一 Map 结构
  Map<String, dynamic> _positionToMap(Position position) {
    return {
      'latitude': position.latitude,
      'longitude': position.longitude,
      'accuracy': position.accuracy,
      'altitude': position.altitude,
      'available': true,
    };
  }
}
