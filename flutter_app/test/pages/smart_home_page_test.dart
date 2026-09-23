import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/smart_home_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// 智能家居页（F31）契约测试。
///
/// 锁定与后端的契约：
/// - 新建方案 POST /api/smart-home/schemes：project_id/room_name/room_type/protocol
///   （无 name/protocol_type/description 字段）
/// - 添加设备 POST /api/smart-home/schemes/{id}/devices：device_name/device_type/room_name
///   （device_type 取 backend DEVICE_TYPES 枚举原值）
/// - 响应读取字段 room_name/protocol/device_name/device_type
/// - 422 校验失败时透出后端 detail
void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  /// 页面持有 30s 周期传感器上报定时器，测试结束前卸载页面并推进假时钟，
  /// 避免残留 Timer 导致测试失败。
  Future<void> unmountPage(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(milliseconds: 100));
  }

  Map<String, dynamic> schemeJson({
    String id = 'scheme-1',
    String roomName = '客厅',
    String protocol = 'zigbee',
  }) =>
      {
        'id': id,
        'project_id': 'proj-1',
        'room_name': roomName,
        'room_type': 'living_room',
        'protocol': protocol,
        'hub_brand': 'xiaomi',
        'device_count': 0,
        'total_price': 0,
        'status': 'draft',
        'notes': null,
        'created_at': '2026-09-23T08:00:00',
        'updated_at': '2026-09-23T08:00:00',
      };

  Map<String, dynamic> deviceJson() => {
        'id': 'dev-1',
        'scheme_id': 'scheme-1',
        'device_type': 'light',
        'device_name': '客厅主灯',
        'brand': null,
        'model': null,
        'room_name': '客厅',
        'protocol': 'zigbee',
        'control_mode': 'manual',
        'price': 0.0,
        'wiring_required': false,
        'status': 'online',
        'created_at': '2026-09-23T08:00:00',
        'updated_at': '2026-09-23T08:00:00',
      };

  testWidgets('方案列表 - 按 room_name/protocol 字段渲染（非 name/protocol_type）',
      (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'smart-home/schemes/project': jsonResponse([schemeJson()]),
    });

    await tester.pumpWidget(
        createTestApp(const SmartHomePage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    expect(find.text('客厅'), findsOneWidget);
    expect(find.text('zigbee'), findsOneWidget);
    expect(find.text('未命名方案'), findsNothing);
    await unmountPage(tester);
  });

  testWidgets('创建方案 - 请求体对齐 room_name/room_type/protocol（不含 name/protocol_type/description）',
      (tester) async {
    final overrides = MockHttpOverrides({
      'smart-home/schemes/project': jsonResponse([schemeJson()]),
      'schemes': jsonResponse(schemeJson(), status: 201),
    });
    HttpOverrides.global = overrides;

    await tester.pumpWidget(
        createTestApp(const SmartHomePage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    await tester.tap(find.text('创建方案'));
    await tester.pumpAndSettle();

    // 对话框首个输入项为「房间名称」
    expect(find.text('房间名称（如：客厅）'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '主卧');
    await tester.tap(find.text('创建'));
    await tester.pumpAndSettle();

    final createRequest = overrides.requests
        .firstWhere((r) => r.method == 'POST' && r.path.endsWith('/schemes'));
    expect(createRequest.path, '/api/smart-home/schemes');
    final body = createRequest.json!;
    expect(body['project_id'], 'proj-1');
    expect(body['room_name'], '主卧');
    expect(body['room_type'], 'living_room'); // 后端受限枚举原值
    expect(body['protocol'], 'zigbee'); // 小写枚举原值
    expect(body.containsKey('name'), isFalse);
    expect(body.containsKey('protocol_type'), isFalse);
    expect(body.containsKey('description'), isFalse);
    await unmountPage(tester);
  });

  testWidgets('添加设备 - 请求体对齐 device_name/device_type/room_name', (tester) async {
    final overrides = MockHttpOverrides({
      'smart-home/schemes/project': jsonResponse([schemeJson()]),
      'devices': jsonResponse([deviceJson()]),
    });
    HttpOverrides.global = overrides;

    await tester.pumpWidget(
        createTestApp(const SmartHomePage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    // 选中方案 → 自动切到「设备管理」Tab，设备卡片读 device_name/device_type/room_name
    await tester.tap(find.text('选为当前'));
    await tester.pumpAndSettle();
    expect(find.text('客厅主灯'), findsOneWidget);
    expect(find.text('类型：light'), findsOneWidget);
    expect(find.text('位置：客厅'), findsOneWidget);

    await tester.tap(find.text('添加设备'));
    await tester.pumpAndSettle();
    expect(find.text('设备名称'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '玄关灯');
    await tester.enterText(find.byType(TextField).last, '玄关');
    await tester.tap(find.text('添加'));
    await tester.pumpAndSettle();

    final addRequest = overrides
        .requests
        .firstWhere((r) => r.method == 'POST' && r.path.endsWith('/devices'));
    expect(addRequest.path, '/api/smart-home/schemes/scheme-1/devices');
    final body = addRequest.json!;
    expect(body['device_name'], '玄关灯');
    expect(body['device_type'], 'light'); // DEVICE_TYPES 枚举原值
    expect(body['room_name'], '玄关');
    expect(body.containsKey('name'), isFalse);
    expect(body.containsKey('type'), isFalse);
    expect(body.containsKey('location'), isFalse);
    await unmountPage(tester);
  });

  testWidgets('创建方案 422 - 后端 detail 透出到错误提示', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'smart-home/schemes/project': jsonResponse([schemeJson()]),
      'api/smart-home/schemes': jsonResponse({
        'detail': [
          {
            'loc': ['body', 'room_name'],
            'msg': 'Field required',
            'type': 'missing',
          }
        ],
      }, status: 422),
    });

    await tester.pumpWidget(
        createTestApp(const SmartHomePage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    await tester.tap(find.text('创建方案'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, '主卧');
    await tester.tap(find.text('创建'));
    await tester.pumpAndSettle();

    // 422 的 detail 是对象数组，需展开为「字段: 说明」而非抛类型错误
    expect(find.textContaining('创建失败'), findsOneWidget);
    expect(find.textContaining('room_name: Field required'), findsOneWidget);
    await unmountPage(tester);
  });
}
