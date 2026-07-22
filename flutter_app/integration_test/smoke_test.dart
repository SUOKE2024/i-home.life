// F5: 集成测试冒烟用例 — 验证应用启动 + 登录页核心元素渲染
//
// 运行方式:
//   flutter test integration_test/smoke_test.dart                    # 桌面端
//   flutter test integration_test/smoke_test.dart -d <device-id>      # 真机/模拟器
//
// 设计目标:
//   - 不依赖后端网络（AuthGate 无 token 时落入 LoginPage）
//   - 验证关键 UI 元素存在，确保应用未因重构/依赖升级而白屏
//   - 验证登录按钮可点击，确保交互链路畅通
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:ihome_app/main.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('应用启动后渲染登录页核心元素', (WidgetTester tester) async {
    // 启动应用 — 无 token 时 AuthGate 落入 LoginPage
    await tester.pumpWidget(const IHomeApp());

    // 等待 AuthGate 异步 _checkAuth 完成 + LoginPage 渲染
    await tester.pumpAndSettle(const Duration(seconds: 3));

    // 1. 品牌标题渲染
    expect(find.text('i-home.life'), findsOneWidget,
        reason: '登录页应显示品牌标题 i-home.life');

    // 2. 副标题渲染
    expect(find.text('索克家居 · AI 智能装修平台'), findsOneWidget,
        reason: '登录页应显示副标题');

    // 3. 手机号输入框存在
    expect(find.byWidgetPredicate((widget) {
          if (widget is TextField) {
            final label = widget.decoration?.labelText;
            return label == '手机号';
          }
          return false;
        }), findsOneWidget, reason: '应存在手机号输入框');

    // 4. 密码输入框存在
    expect(find.byWidgetPredicate((widget) {
          if (widget is TextField) {
            final label = widget.decoration?.labelText;
            return label == '密码';
          }
          return false;
        }), findsOneWidget, reason: '应存在密码输入框');

    // 5. 登录按钮存在且可点击
    final loginButton = find.text('登 录');
    expect(loginButton, findsOneWidget, reason: '应存在登录按钮');
    expect(tester.widget<ElevatedButton>(find.ancestor(
      of: loginButton,
      matching: find.byType(ElevatedButton),
    ).first).enabled, isTrue, reason: '登录按钮应处于可点击状态');
  });

  testWidgets('输入框可接收文本输入', (WidgetTester tester) async {
    await tester.pumpWidget(const IHomeApp());
    await tester.pumpAndSettle(const Duration(seconds: 3));

    // 定位手机号输入框并输入
    final phoneField = find.byWidgetPredicate((widget) {
      if (widget is TextField) {
        return widget.decoration?.labelText == '手机号';
      }
      return false;
    });
    await tester.enterText(phoneField, '13800138000');

    // 验证输入已写入
    expect(find.text('13800138000'), findsOneWidget,
        reason: '手机号输入框应显示已输入的文本');
  });
}
