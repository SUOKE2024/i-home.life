import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:ihome_app/services/api.dart';
import 'package:ihome_app/services/project_context.dart';

/// 初始化测试环境：mock SharedPreferences + 清理 ApiClient 单例状态。
void setupTestEnv() {
  SharedPreferences.setMockInitialValues({});
  ApiClient().onUnauthorized = null;
}

/// Mock connectivity_plus 的 check 方法（方法通道）。
///
/// 仅 mock [checkConnectivity] 使用的 `dev.fluttercommunity.plus/connectivity` 通道；
/// 事件通道 `dev.fluttercommunity.plus/connectivity_status` 由 EventChannel 自行接管，
/// 其 `listen` 调用会失败并被 EventChannel 内部 catch → FlutterError.reportError，
/// 测试中通过 [tester.takeException] 清除即可。
void mockConnectivityCheck() {
  const channel = MethodChannel('dev.fluttercommunity.plus/connectivity');
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(channel, (MethodCall call) async {
    switch (call.method) {
      case 'check':
        return ['wifi'];
      default:
        return null;
    }
  });
}

/// 创建按 URL path 匹配响应的 mock http client。
///
/// [responses] 的 key 是 URL path 的子串，value 是对应的响应。
/// 未匹配的请求返回 [defaultResponse]（默认空列表 200）。
http.Client createMockHttpClient(
  Map<String, http.Response> responses, {
  http.Response? defaultResponse,
}) {
  return MockClient((request) async {
    final path = request.url.path;
    for (final entry in responses.entries) {
      if (path.contains(entry.key)) {
        return entry.value;
      }
    }
    return defaultResponse ?? http.Response('[]', 200);
  });
}

/// 辅助：快速创建 JSON 200 响应。
http.Response jsonResponse(dynamic data, {int status = 200}) {
  return http.Response.bytes(
    utf8.encode(jsonEncode(data)),
    status,
    headers: {'content-type': 'application/json; charset=utf-8'},
  );
}

/// 创建测试用 MaterialApp，包含 [ProjectContext] Provider。
Widget createTestApp(Widget home, {ProjectContext? projectContext}) {
  return ChangeNotifierProvider<ProjectContext>(
    create: (_) => projectContext ?? ProjectContext(),
    child: MaterialApp(home: home),
  );
}
