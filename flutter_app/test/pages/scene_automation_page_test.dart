import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/scene_automation_page.dart';
import 'package:ihome_app/services/api.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// 场景编辑页（F32）契约测试。
///
/// 锁定与后端的契约：
/// - 场景列表 GET /api/scene-automation/scenes/project/{project_id}
/// - 生态列表 GET /api/scene-automation/ecosystems/project/{project_id}
/// - 生态响应字段 ecosystem / auth_status / device_count（无 name/type/status）
/// - scene_type 合法语义 manual/scheduled/triggered/geo（「起床/睡眠」属 scene_name）
/// - 加载失败为诚实错误态，不伪装成「暂无数据」空列表
void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  Map<String, dynamic> sceneJson({
    String id = 'scene-1',
    String name = '起床模式',
    String type = 'scheduled',
  }) =>
      {
        'id': id,
        'project_id': 'proj-1',
        'scheme_id': null,
        'scene_name': name,
        'scene_type': type,
        'trigger_condition': {'type': 'time', 'cron': '0 7 * * *'},
        'actions': [],
        'enabled': true,
        'priority': 0,
        'created_at': '2026-09-23T08:00:00',
        'updated_at': '2026-09-23T08:00:00',
      };

  Map<String, dynamic> ecoJson({
    String ecosystem = 'mijia',
    String authStatus = 'connected',
    int deviceCount = 3,
  }) =>
      {
        'id': 'eco-1',
        'project_id': 'proj-1',
        'ecosystem': ecosystem,
        'auth_status': authStatus,
        'device_count': deviceCount,
        'last_synced_at': null,
        'config': null,
        'notes': null,
        'created_at': '2026-09-23T08:00:00',
        'updated_at': '2026-09-23T08:00:00',
      };

  testWidgets('场景列表 - 走 /scenes/project/{id} 契约路径并渲染 scene_name', (tester) async {
    final overrides = MockHttpOverrides({
      'scene-automation/scenes/project': jsonResponse([sceneJson()]),
      'scene-automation/ecosystems/project': jsonResponse([ecoJson()]),
    });
    HttpOverrides.global = overrides;

    await tester.pumpWidget(
        createTestApp(const SceneAutomationPage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    final paths = overrides.requests.map((r) => r.path).toList();
    expect(paths, contains('/api/scene-automation/scenes/project/proj-1'));
    expect(find.text('起床模式'), findsOneWidget);
    // scene_type 显示为合法语义的中文标签
    expect(find.text('定时触发'), findsOneWidget);
    expect(find.text('暂无场景'), findsNothing);
  });

  testWidgets('生态对接 - 走 /ecosystems/project/{id} 并读 ecosystem/auth_status 字段',
      (tester) async {
    final overrides = MockHttpOverrides({
      'scene-automation/scenes/project': jsonResponse([sceneJson()]),
      'scene-automation/ecosystems/project': jsonResponse([ecoJson()]),
    });
    HttpOverrides.global = overrides;

    await tester.pumpWidget(
        createTestApp(const SceneAutomationPage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    // 契约路径：生态列表必须走 /ecosystems/project/{id}（旧代码走 /ecosystems → 404/405）
    expect(overrides.requests.map((r) => r.path),
        contains('/api/scene-automation/ecosystems/project/proj-1'));

    await tester.tap(find.text('生态对接'));
    await tester.pumpAndSettle();

    // 生态卡片读 ecosystem（非 name），授权状态读 auth_status（非 status）
    expect(find.text('mijia'), findsOneWidget);
    expect(find.textContaining('授权状态：已连接'), findsOneWidget);
    expect(find.textContaining('已接入 3 台设备'), findsOneWidget);
    expect(find.text('未命名'), findsNothing);
    expect(find.text('暂无生态对接'), findsNothing);
  });

  testWidgets('加载失败 - 场景列表显示诚实错误态而非空列表', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'scene-automation/scenes/project':
          jsonResponse({'detail': '项目不存在'}, status: 404),
      'scene-automation/ecosystems/project': jsonResponse([]),
    });

    await tester.pumpWidget(
        createTestApp(const SceneAutomationPage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    expect(find.textContaining('加载场景失败'), findsOneWidget);
    expect(find.text('项目不存在'), findsNothing); // 详情已并入错误文案
    expect(find.text('暂无场景'), findsNothing);
    expect(find.text('重试'), findsOneWidget);
  });

  testWidgets('生态对接加载失败 - 生态 Tab 显示错误态而非「暂无生态对接」', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'scene-automation/scenes/project': jsonResponse([sceneJson()]),
      'scene-automation/ecosystems/project':
          jsonResponse({'detail': '服务异常'}, status: 500),
    });

    await tester.pumpWidget(
        createTestApp(const SceneAutomationPage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    await tester.tap(find.text('生态对接'));
    await tester.pumpAndSettle();

    expect(find.textContaining('加载生态对接失败'), findsOneWidget);
    expect(find.textContaining('服务异常'), findsOneWidget);
    expect(find.text('暂无生态对接'), findsNothing);
  });

  testWidgets('新建场景 - 请求体为 scene_name + 合法 scene_type（不含 wake_up 等非法语义）',
      (tester) async {
    const legalTypes = ['manual', 'scheduled', 'triggered', 'geo'];
    final overrides = MockHttpOverrides({
      'scene-automation/scenes/project': jsonResponse([]),
      'scene-automation/ecosystems/project': jsonResponse([]),
      'scene-automation/scenes': jsonResponse(sceneJson(), status: 201),
    });
    HttpOverrides.global = overrides;

    await tester.pumpWidget(
        createTestApp(const SceneAutomationPage(projectId: 'proj-1')));
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.add).first); // 新建场景（AppBar / 空态按钮同源）
    await tester.pumpAndSettle();

    final createRequest = overrides.requestByMethod('POST')!;
    expect(createRequest.path, '/api/scene-automation/scenes');
    final body = createRequest.json!;
    expect(body['project_id'], 'proj-1');
    expect(body['scene_name'], isNotEmpty);
    expect(legalTypes, contains(body['scene_type']));
    expect(body.containsKey('name'), isFalse);
  });

  testWidgets('API 契约 - sceneSync 请求体必带 ecosystem', (tester) async {
    final overrides = MockHttpOverrides({
      'scene-automation/scenes/scene-1/sync': jsonResponse({
        'scene_id': 'scene-1',
        'ecosystem': 'mijia',
        'synced': true,
        'message': 'ok',
      }),
    });
    HttpOverrides.global = overrides;

    final result = await ApiClient().sceneSync('scene-1', 'mijia');

    expect(result.isSuccess, isTrue);
    expect(overrides.lastRequestMethod, 'POST');
    expect(overrides.lastRequestUrl!.path,
        '/api/scene-automation/scenes/scene-1/sync');
    expect(overrides.lastRequestJson, {'ecosystem': 'mijia'});
  });
}
