/// 穿戴设备（BLE 手表/手环）接入服务（2026-08-27）
///
/// 基于 flutter_blue_plus 实现真实 BLE 直连：
/// - 扫描 → 连接 → 发现服务 → 订阅心率（Heart Rate 0x180D/0x2A37）与电量（0x180F/0x2A19）
/// - 心率/电量实时读数，供健康监测上报（health-monitor/records，device_id=BLE MAC）
/// - 鸿蒙等不支持的平台优雅降级（能力探测失败 → isAvailable=false，不崩溃）
///
/// 局限（诚实标注）：血氧/跌倒等多依赖厂商私有特征，本服务仅覆盖标准服务；
/// 厂商扩展特征接入需在 [parseCustomCharacteristic] 扩展。
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

/// BLE 穿戴设备连接状态
enum WearableConnState { disconnected, connecting, connected, unavailable }

class WearableBleService {
  static final WearableBleService _instance = WearableBleService._();
  factory WearableBleService() => _instance;
  WearableBleService._();

  // 标准 BLE 服务/特征 UUID（16-bit 展开为完整 128-bit）
  static final Guid _heartRateService = Guid('0000180d-0000-1000-8000-00805f9b34fb');
  static final Guid _heartRateChar = Guid('00002a37-0000-1000-8000-00805f9b34fb');
  static final Guid _batteryService = Guid('0000180f-0000-1000-8000-00805f9b34fb');
  static final Guid _batteryChar = Guid('00002a19-0000-1000-8000-00805f9b34fb');

  bool _available = true;
  BluetoothDevice? _device;
  StreamSubscription<List<ScanResult>>? _scanSub;
  StreamSubscription<List<int>>? _hrSub;
  StreamSubscription<List<int>>? _batterySub;
  int? _heartRate;
  int? _batteryLevel;
  String _deviceName = '';

  bool get isAvailable => _available;
  bool get isConnected => _device != null && _device!.isConnected;
  BluetoothDevice? get device => _device;
  String get deviceName => _deviceName;
  int? get heartRate => _heartRate;
  int? get batteryLevel => _batteryLevel;

  /// 平台能力探测（鸿蒙/无 BLE 平台优雅降级）
  Future<bool> init() async {
    try {
      await FlutterBluePlus.adapterState.first.timeout(const Duration(seconds: 3));
      _available = true;
      debugPrint('[WearableBleService] BLE 可用');
    } catch (e) {
      debugPrint('[WearableBleService] 平台不支持 BLE，降级: $e');
      _available = false;
    }
    return _available;
  }

  /// 扫描 BLE 设备（默认 10s），返回 [{name, id, rssi}]；不支持平台返回空。
  Future<List<Map<String, Object?>>> scan({
    Duration timeout = const Duration(seconds: 10),
  }) async {
    if (!_available) return [];
    unawaited(_scanSub?.cancel());
    _scanSub = null;
    final seen = <String, Map<String, Object?>>{};
    _scanSub = FlutterBluePlus.scanResults.listen((scanResults) {
      for (final r in scanResults) {
        seen[r.device.remoteId.str] = {
          'name': r.device.platformName.isNotEmpty
              ? r.device.platformName
              : r.device.remoteId.str,
          'id': r.device.remoteId.str,
          'rssi': r.rssi,
        };
      }
    }, onError: (Object e) {
      debugPrint('[WearableBleService] 扫描错误: $e');
    });
    try {
      await FlutterBluePlus.startScan(timeout: timeout);
    } catch (e) {
      debugPrint('[WearableBleService] startScan 失败: $e');
    }
    await Future<void>.delayed(const Duration(milliseconds: 200));
    return seen.values.toList();
  }

  Future<void> stopScan() async {
    unawaited(_scanSub?.cancel());
    _scanSub = null;
    try {
      await FlutterBluePlus.stopScan();
    } catch (_) {}
  }

  /// 连接设备并订阅心率/电量特征。返回连接是否成功（失败不抛异常）。
  Future<bool> connect(String deviceId) async {
    if (!_available) return false;
    await disconnect();
    try {
      _device = BluetoothDevice.fromId(deviceId);
      _deviceName = _device!.platformName.isNotEmpty
          ? _device!.platformName
          : deviceId;
      await _device!.connect(
        license: License.nonprofit, // 个人/非营利免费档（商业使用需付费许可）
        timeout: const Duration(seconds: 15),
      );
      await _device!.discoverServices();
      _subscribeHeartRate();
      _subscribeBattery();
      debugPrint('[WearableBleService] 已连接: $_deviceName');
      return true;
    } catch (e) {
      debugPrint('[WearableBleService] 连接失败: $e');
      _device = null;
      return false;
    }
  }

  Future<void> disconnect() async {
    unawaited(_hrSub?.cancel());
    unawaited(_batterySub?.cancel());
    _hrSub = null;
    _batterySub = null;
    _heartRate = null;
    final dev = _device;
    _device = null;
    if (dev != null && dev.isConnected) {
      try {
        await dev.disconnect();
      } catch (_) {}
    }
  }

  void _subscribeHeartRate() {
    final device = _device;
    if (device == null) return;
    final hr = device.servicesList
        .where((s) => s.uuid == _heartRateService)
        .expand((s) => s.characteristics)
        .where((c) => c.uuid == _heartRateChar)
        .toList();
    if (hr.isEmpty) {
      debugPrint('[WearableBleService] 设备无标准心率服务（0x180D）');
      return;
    }
    final characteristic = hr.first;
    _hrSub = characteristic.onValueReceived.listen((data) {
      final bpm = _parseHeartRate(data);
      if (bpm != null) {
        _heartRate = bpm;
        debugPrint('[WearableBleService] 心率: $bpm bpm');
      }
    }, onError: (Object e) {
      debugPrint('[WearableBleService] 心率订阅错误: $e');
    });
    unawaited(characteristic.setNotifyValue(true));
  }

  void _subscribeBattery() {
    final device = _device;
    if (device == null) return;
    final batt = device.servicesList
        .where((s) => s.uuid == _batteryService)
        .expand((s) => s.characteristics)
        .where((c) => c.uuid == _batteryChar)
        .toList();
    if (batt.isEmpty) return;
    final characteristic = batt.first;
    _batterySub = characteristic.onValueReceived.listen((data) {
      if (data.isNotEmpty) {
        _batteryLevel = data.first;
      }
    }, onError: (_) {});
    unawaited(characteristic.setNotifyValue(true));
  }

  /// 解析心率测量特征数据（BLE 标准：首字节 flags，其后 8-bit 或 16-bit 心率）。
  @visibleForTesting
  static int? parseHeartRate(List<int> data) => _parseHeartRate(data);

  static int? _parseHeartRate(List<int> data) {
    if (data.isEmpty) return null;
    final flags = data[0];
    final is16Bit = (flags & 0x01) != 0;
    if (is16Bit && data.length >= 3) {
      return (data[1] | (data[2] << 8));
    }
    if (data.length >= 2) {
      return data[1];
    }
    return null;
  }
}
