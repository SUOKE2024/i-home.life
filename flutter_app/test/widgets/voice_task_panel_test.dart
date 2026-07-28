import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/widgets/voice_task_panel.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// 语音任务面板（VoiceTaskPanel）组件测试。
///
/// 覆盖评估报告 P2 项：新增组件零测试。
/// 注意：面板内置 3s 轮询 Timer，测试中不能使用 pumpAndSettle
/// （periodic timer 永不 settle），统一用 pump + 短时长推进。
void main() {
  setUp(() {
    setupTestEnv();
    mockConnectivityCheck();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  /// 推进帧并 flush 异步（不使用 pumpAndSettle，避免轮询 Timer 卡死）
  Future<void> settle(WidgetTester tester) async {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
  }

  testWidgets('渲染 - 头部与启动栏，空任务时显示空态提示', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'voice/orchestrate/tasks': jsonResponse({'tasks': []}),
    });

    await tester.pumpWidget(createTestApp(
      const Scaffold(body: VoiceTaskPanel(projectId: 'p1')),
    ));
    await settle(tester);

    expect(find.text('语音任务'), findsOneWidget);
    expect(find.text('启动'), findsOneWidget);
    expect(find.text('暂无语音任务，输入指令启动第一个后台任务'), findsOneWidget);
  });

  testWidgets('flag 未启用(503) - 显示诚实提示并隐藏启动栏', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'voice/orchestrate/tasks': jsonResponse(
        {'detail': 'voice_agent_orchestration_enabled=False'},
        status: 503,
      ),
    });

    await tester.pumpWidget(createTestApp(
      const Scaffold(body: VoiceTaskPanel()),
    ));
    await settle(tester);

    expect(
      find.text('语音智能体编排未启用（voice_agent_orchestration_enabled）'),
      findsOneWidget,
    );
    // 启动栏隐藏
    expect(find.text('启动'), findsNothing);
  });

  testWidgets('任务列表 - 渲染运行中/已完成任务及状态标签', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'voice/orchestrate/tasks': jsonResponse({
        'tasks': [
          {
            'seq': 1,
            'intent': 'design',
            'command': '帮我设计客厅',
            'status': 'running',
            'reply': '',
            'error': '',
          },
          {
            'seq': 2,
            'intent': 'budget',
            'command': '做份预算',
            'status': 'done',
            'reply': '预算已生成',
            'error': '',
          },
        ],
      }),
    });

    await tester.pumpWidget(createTestApp(
      const Scaffold(body: VoiceTaskPanel(projectId: 'p1')),
    ));
    await settle(tester);

    expect(find.text('#1 设计方案'), findsOneWidget);
    expect(find.text('#2 预算分析'), findsOneWidget);
    expect(find.text('进行中'), findsOneWidget);
    expect(find.text('已完成'), findsOneWidget);
    // 仅运行中任务显示取消入口
    expect(find.text('取消'), findsOneWidget);
    expect(find.text('预算已生成'), findsOneWidget);
  });

  testWidgets('启动任务 - 提交指令后展示后端回复', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      // 注意顺序：tasks 路径必须先匹配，避免被 /voice/orchestrate 前缀吞掉
      'voice/orchestrate/tasks': jsonResponse({'tasks': []}),
      'voice/orchestrate': jsonResponse({'reply': '已启动 2 个任务'}),
    });

    await tester.pumpWidget(createTestApp(
      const Scaffold(body: VoiceTaskPanel(projectId: 'p1')),
    ));
    await settle(tester);

    await tester.enterText(
      find.byType(TextField),
      '帮我设计客厅，同时做份预算',
    );
    await tester.tap(find.text('启动'));
    await settle(tester);

    expect(find.text('已启动 2 个任务'), findsOneWidget);
  });

  testWidgets('启动失败 - 非 503 错误展示失败原因', (tester) async {
    HttpOverrides.global = MockHttpOverrides({
      'voice/orchestrate/tasks': jsonResponse({'tasks': []}),
      'voice/orchestrate': jsonResponse({'detail': '服务器开小差'}, status: 500),
    });

    await tester.pumpWidget(createTestApp(
      const Scaffold(body: VoiceTaskPanel(projectId: 'p1')),
    ));
    await settle(tester);

    await tester.enterText(find.byType(TextField), '做份预算');
    await tester.tap(find.text('启动'));
    await settle(tester);

    expect(find.textContaining('启动失败'), findsOneWidget);
  });
}
