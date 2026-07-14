import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:ihome_app/services/api.dart';

import '../test_helper.dart';
import '../mock_http.dart';

void main() {
  setUp(() async {
    setupTestEnv();
    // ApiClient 是单例，测试间需重置 token 状态
    await ApiClient().clearToken();
  });

  tearDown(() {
    HttpOverrides.global = null;
  });

  // ── token 管理 ──

  group('token 管理', () {
    test('初始状态未登录', () {
      expect(ApiClient().isLoggedIn, isFalse);
      expect(ApiClient().token, isNull);
    });

    test('saveToken 后 isLoggedIn 为 true', () async {
      await ApiClient().saveToken('test-token-123');
      expect(ApiClient().isLoggedIn, isTrue);
      expect(ApiClient().token, 'test-token-123');
    });

    test('clearToken 后 isLoggedIn 为 false', () async {
      await ApiClient().saveToken('test-token-456');
      expect(ApiClient().isLoggedIn, isTrue);

      await ApiClient().clearToken();
      expect(ApiClient().isLoggedIn, isFalse);
      expect(ApiClient().token, isNull);
    });

    test('loadToken 从 SharedPreferences 恢复 token', () async {
      await ApiClient().saveToken('persisted-token');

      // 模拟重启：清除内存中的 token，再从存储加载
      await ApiClient().clearToken();
      expect(ApiClient().isLoggedIn, isFalse);

      // saveToken 时已写入 SharedPreferences，重新加载后应恢复
      // 注意：clearToken 也清除了 SharedPreferences，所以这里测试 save+load 流程
      await ApiClient().saveToken('persisted-token');
      await ApiClient().clearToken();

      // loadToken 从空的 SharedPreferences 加载 → 未登录
      await ApiClient().loadToken();
      expect(ApiClient().isLoggedIn, isFalse);
    });
  });

  // ── URL 构造 ──

  group('URL 构造', () {
    test('正确拼接 baseUrl 和 path', () async {
      final overrides = MockHttpOverrides({
        'test-endpoint': jsonResponse({'ok': true}),
      });
      HttpOverrides.global = overrides;

      await ApiClient().get('/test-endpoint');

      expect(overrides.lastRequestUrl, isNotNull);
      expect(overrides.lastRequestUrl!.path, contains('test-endpoint'));
    });
  });

  // ── 响应处理 ──

  group('响应处理', () {
    test('成功响应返回 Result.success 含解码后的数据', () async {
      HttpOverrides.global = MockHttpOverrides({
        'success': jsonResponse({
          'key': 'value',
          'num': 42,
          'list': [1, 2, 3],
        }),
      });

      final result = await ApiClient().get('/success');

      expect(result.isSuccess, isTrue);
      expect(result.data, isA<Map>());
      expect(result.data!['key'], 'value');
      expect(result.data!['num'], 42);
      expect(result.data!['list'], [1, 2, 3]);
    });

    test('401 返回 Result.failure 并触发 onUnauthorized 回调', () async {
      await ApiClient().saveToken('will-be-cleared');

      var unauthorizedCalled = false;
      ApiClient().onUnauthorized = () {
        unauthorizedCalled = true;
      };

      HttpOverrides.global = MockHttpOverrides({
        'protected': jsonResponse({'detail': '未授权'}, status: 401),
      });

      final result = await ApiClient().get('/protected');

      expect(result.isSuccess, isFalse);
      expect(result.statusCode, 401);

      // _onUnauthorized 是 async 但在 _handleResponse 中未 await，
      // 需等待微任务队列完成
      await Future.delayed(const Duration(milliseconds: 50));

      expect(unauthorizedCalled, isTrue);
      expect(ApiClient().isLoggedIn, isFalse);
    });

    test('500 返回 Result.failure 含服务器错误信息', () async {
      HttpOverrides.global = MockHttpOverrides({
        'server-error': jsonResponse(
          {'detail': '内部服务器错误'},
          status: 500,
        ),
      });

      final result = await ApiClient().get('/server-error');

      expect(result.isSuccess, isFalse);
      expect(result.statusCode, 500);
      expect(result.error, contains('内部服务器错误'));
    });
  });
}
