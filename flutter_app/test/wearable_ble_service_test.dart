import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/services/wearable_ble_service.dart';

/// 穿戴设备 BLE 服务单测（2026-08-27）
///
/// 覆盖纯逻辑：心率测量特征解析（BLE 标准 Heart Rate Measurement 格式：
/// 首字节 flags，bit0=1 时心率 16-bit，否则 8-bit）。
void main() {
  group('WearableBleService.parseHeartRate', () {
    test('8-bit 心率（flags=0）', () {
      // flags=0（无格式/传感器触点），心率 72
      expect(WearableBleService.parseHeartRate([0x00, 0x48]), 72);
    });

    test('8-bit 心率（flags 含其他位仍走 8-bit）', () {
      // flags=0x06（能量消耗字段存在），心率 90
      expect(WearableBleService.parseHeartRate([0x06, 0x5A, 0x00]), 90);
    });

    test('16-bit 心率（flags bit0=1）', () {
      // flags=0x01（16-bit），心率 0x00E8 = 232
      expect(WearableBleService.parseHeartRate([0x01, 0xE8, 0x00]), 232);
    });

    test('空数据返回 null（不 crash）', () {
      expect(WearableBleService.parseHeartRate([]), isNull);
    });

    test('数据不足返回 null（flags 存在但无心率字节）', () {
      expect(WearableBleService.parseHeartRate([0x00]), isNull);
    });
  });
}
