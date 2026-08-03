import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/pages/ar_scan_page.dart';

import '../test_helper.dart';
import '../mock_http.dart';

/// F1 AR 空间测量页冒烟测试 (v1.2.x 补充 — 此前该功能零测试覆盖)
///
/// 注意: 页面包含 repeat 动画控制器, 不能使用 pumpAndSettle,
/// 统一使用固定时长 pump。
void main() {
  setUp(() {
    setupTestEnv();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  testWidgets('页面渲染 - 首次进入展示使用引导覆盖层', (tester) async {
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const ARScanPage(projectId: 'test-id')),
    );
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 200));

    // 首次引导覆盖层 (P2-7: 首次展示)
    expect(find.text('站在房间角落'), findsOneWidget);
    expect(find.text('下一步'), findsOneWidget);
    // 覆盖层下方的页面 AppBar 标题
    expect(find.text('AR 空间测量'), findsWidgets);
  });

  testWidgets('引导关闭 - 点击「开始使用」后进入设备检测步骤', (tester) async {
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const ARScanPage(projectId: 'test-id')),
    );
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 200));

    // 逐条翻页: 下一步 ×3 → 开始使用
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.text('下一步'));
      await tester.pump(const Duration(milliseconds: 250));
    }
    expect(find.text('开始使用'), findsOneWidget);

    await tester.tap(find.text('开始使用'));
    await tester.pump(const Duration(milliseconds: 250));

    // 覆盖层已关闭, 引导文案消失
    expect(find.text('站在房间角落'), findsNothing);
  });

  // v1.2.10 P1 回归测试：步骤指示器必须渲染当前步骤的文字标签，
  // 修复前 steps 数组声明但从未渲染，7 个圆点无可读文字，无法扫读当前步骤。
  testWidgets('步骤指示器 - 渲染当前步骤文字标签', (tester) async {
    HttpOverrides.global = MockHttpOverrides({});

    await tester.pumpWidget(
      createTestApp(const ARScanPage(projectId: 'test-id')),
    );
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 200));

    // 关闭 coaching overlay
    for (var i = 0; i < 3; i++) {
      await tester.tap(find.text('下一步'));
      await tester.pump(const Duration(milliseconds: 250));
    }
    await tester.tap(find.text('开始使用'));
    await tester.pump(const Duration(milliseconds: 250));

    // 默认进入 deviceCheck 步骤, 指示器应渲染其文字标签
    expect(find.text('设备检测'), findsOneWidget);
  });
}
